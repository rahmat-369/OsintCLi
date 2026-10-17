"""Explicit external process boundaries; no shell and no upstream code vendored."""
import csv
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
from .core import AppError
from .adapters import item

PINS={"sherlock":"e40a45ec2a074b90703b3b4b842c8a3adbd6ada3","maigret":"eaf820666d15bfd545129f3223e2261c27191e74","exiftool":"2200871d9cef988051d2a99d67df3bda6cbb30a8"}

def executable(name,config):
    own=config.data/"tools"/name/"bin"/name
    if own.is_file() and os.access(own,os.X_OK):return str(own)
    return shutil.which(name)

def parse_sherlock(text):
    reader=csv.DictReader(io.StringIO(text))
    if not {"name","url_user","exists"}.issubset(reader.fieldnames or []):raise AppError("UPSTREAM_SCHEMA","Skema CSV Sherlock berubah.")
    for r in reader:
        state=r["exists"].strip().lower()
        if state=="claimed":
            yield item("profile",r["url_user"],r["url_user"],title=r["name"],status="CANDIDATE",raw=r,reason="Sherlock melaporkan Claimed; tinjauan manual diperlukan, bukan bukti identitas.")
        elif state=="available":
            yield item("profile_check","Tool melaporkan Available pada waktu pemeriksaan.",r["url_user"],title=r["name"],status="UNVERIFIED",raw=r,reason="Hasil negatif tool belum diverifikasi; bukan bukti akun tidak pernah ada.")
        elif state not in ("available",):
            from .adapters import failed
            record=failed(r["url_user"],AppError("UPSTREAM_CHECK",f"Sherlock: {state or 'unknown'}; {r.get('error_reason','')}"))
            record["raw"]=r
            yield record

def parse_maigret_csv(text):
    for record in parse_sherlock(text):
        for key in ("verification_reason","value"):
            if isinstance(record.get(key),str):record[key]=record[key].replace("Sherlock","Maigret")
        yield record

def parse_maigret(text):
    try:data=json.loads(text)
    except ValueError:raise AppError("UPSTREAM_SCHEMA","JSON Maigret tidak valid.")
    if not isinstance(data,dict):raise AppError("UPSTREAM_SCHEMA","Maigret harus menghasilkan mapping situs.")
    for site,r in data.items():
        if not isinstance(r,dict) or not isinstance(r.get("status"),dict):raise AppError("UPSTREAM_SCHEMA","Skema Maigret berubah.")
        if str(r["status"].get("status","")).lower()=="claimed":
            url=r.get("url_user") or r["status"].get("site_url_user")
            if not isinstance(url,str) or not url.startswith(("http://","https://")):raise AppError("UPSTREAM_SCHEMA","URL profil Maigret tidak valid.")
            yield item("profile",url,url,title=site,status="CANDIDATE",raw=r,reason="Maigret melaporkan Claimed; kepemilikan profil belum diverifikasi.")

def run_process(command,cwd,stop,timeout=100):
    # Bound runtime and output, terminate complete subprocess group on Ctrl+C.
    env=os.environ.copy()
    for key in list(env):
        if key.startswith(("NEXRAY_","OPENAI_","ANTHROPIC_")):env.pop(key)
    with tempfile.TemporaryFile() as output:
        p=subprocess.Popen(command,cwd=cwd,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        try:
            start=time.monotonic()
            while p.poll() is None:
                if stop.wait(0.1):raise AppError("CANCELLED","Proses tool dibatalkan.")
                if time.monotonic()-start>timeout:raise AppError("TOOL_TIMEOUT","Tool melewati batas 100 detik.")
                if os.fstat(output.fileno()).st_size>2_000_000:raise AppError("TOOL_OUTPUT","Output tool terlalu besar.")
            output.seek(0);text=output.read(2_000_001).decode("utf-8",errors="replace")
            if p.returncode:raise AppError("TOOL_EXIT",f"Tool berhenti dengan kode {p.returncode}; cek instalasi/versi melalui doctor.")
            return text
        finally:
            if p.poll() is None:
                try:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=2)
                except (ProcessLookupError,subprocess.TimeoutExpired):
                    try:os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    p.wait()

def external(ctx,name):
    command=executable(name,ctx.config)
    if not command:raise AppError("UNAVAILABLE",f"{name} belum dipasang. Jalankan bash scripts/install-tools.sh {name}.")
    with tempfile.TemporaryDirectory(prefix="osintcli-tool-") as d:
        work=Path(d)
        if name=="exiftool":
            if Path(ctx.value).stat().st_size>ctx.config["max_file_mb"]*1024*1024:raise AppError("FILE_SIZE","File terlalu besar.")
            output=run_process([command,"-json","-G","--",ctx.value],d,ctx.stop)
            try:rows=json.loads(output)
            except ValueError:raise AppError("UPSTREAM_SCHEMA","ExifTool tidak menghasilkan JSON.")
            if not isinstance(rows,list) or not rows or not isinstance(rows[0],dict):raise AppError("UPSTREAM_SCHEMA","Skema ExifTool berubah.")
            for key,value in rows[0].items():
                if key in ("SourceFile","File:Directory"):continue
                if key.endswith(":Error"):raise AppError("EXIFTOOL",str(value))
                yield item("exif",value,"local:ExifTool",title=key,reason="Metadata lokal bisa sensitif/dimodifikasi; tidak membuktikan identitas.")
            return
        if name=="sherlock":
            args=[command,ctx.value,"--csv","--folderoutput",str(work),"--timeout","12","--no-color","--local"]
            for site in ("GitHub","GitLab","Reddit"):args += ["--site",site]
            run_process(args,d,ctx.stop)
            paths=list(work.glob("*.csv"));parser=parse_sherlock
        else:
            (work/"settings.json").write_text(json.dumps({"cloudflare_bypass":{"enabled":False},"cookie_jar_file":None,"proxy_url":None,"tor_proxy_url":None,"i2p_proxy_url":None,"domain_search":False,"info_extracting":False,"recursive_search":False,"pdf_report":False,"html_report":False,"graph_report":False,"web_interface_port":0}))
            args=[command,ctx.value,"--csv","--folderoutput",str(work),"--timeout","12","--retries","0","--max-connections","3","--no-recursion","--no-extracting","--no-autoupdate","--no-progressbar"]
            for site in ("GitHub","GitLab","Reddit"):args += ["--site",site]
            run_process(args,d,ctx.stop)
            paths=list(work.glob("*.csv"));parser=parse_maigret_csv
        if not paths:raise AppError("TOOL_OUTPUT","Tool selesai tanpa file hasil yang diharapkan.")
        count=0
        for p in paths:
            if p.stat().st_size>2_000_000:raise AppError("TOOL_OUTPUT","File hasil terlalu besar.")
            for record in parser(p.read_text(encoding="utf-8")):
                count+=1;yield record
        if count==0:yield item("source_observation","Tool tidak melaporkan kandidat. Hasil kosong tidak membuktikan akun tidak ada; blokir atau galat sumber masih mungkin.","local:"+name,status="UNVERIFIED")
