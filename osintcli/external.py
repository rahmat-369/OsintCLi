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

PINS={"user-scanner":"b85d470b48f7fb9d5ccff85080a882bf70049ed7","sherlock":"e40a45ec2a074b90703b3b4b842c8a3adbd6ada3","maigret":"eaf820666d15bfd545129f3223e2261c27191e74","exiftool":"2200871d9cef988051d2a99d67df3bda6cbb30a8"}

def executable(name,config):
    own=config.data/"tools"/name/"bin"/name
    if own.is_file() and os.access(own,os.X_OK):return str(own.resolve())
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
        try:
            p=subprocess.Popen(command,cwd=cwd,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        except FileNotFoundError as error:
            raise AppError("TOOL_LAUNCH","Executable atau interpreter tool hilang; buat ulang virtual environment lalu ulangi install-tools.sh.") from error
        except PermissionError as error:
            raise AppError("TOOL_PERMISSION","Tool tidak dapat dieksekusi; periksa izin instalasi.") from error
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
        if name=="user-scanner":
            result=work/"result.json"
            args=[command,"-u",ctx.value,"-m","github,tiktok","--all","--no-nsfw","-C","2","-t",str(max(30,ctx.config["timeout_seconds"])),"-f","json","-o",str(result)]
            run_process(args,d,ctx.stop)
            if not result.is_file() or result.stat().st_size>2_000_000:raise AppError("TOOL_OUTPUT","User Scanner tidak menghasilkan JSON yang valid.")
            yield from parse_user_scanner(result.read_text())
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


def parse_user_scanner(text):
    from .adapters import failed
    from .fusion import relationship, canonical_link
    try:data=json.loads(text)
    except ValueError:raise AppError("UPSTREAM_SCHEMA","JSON User Scanner tidak valid.")
    if isinstance(data,dict):data=data.get("results")
    if not isinstance(data,list):raise AppError("UPSTREAM_SCHEMA","User Scanner harus menghasilkan daftar hasil.")
    for r in data:
        if not isinstance(r,dict) or r.get("status") not in ("Found","Not Found","Error","Skipped"):
            raise AppError("UPSTREAM_SCHEMA","Skema status User Scanner berubah.")
        url=r.get("url") or "local:user-scanner";site=str(r.get("site_name") or "User Scanner")
        if r["status"]=="Found":
            extra=r.get("extra") or {}
            yield item("profile",extra,url,title=site,status="CANDIDATE",raw=r,reason="User Scanner melaporkan Found; metadata adalah klaim sumber, bukan bukti kepemilikan akun.")
            for key,value in extra.items():
                if isinstance(value,str) and value.startswith(("https://","http://")) and not any(x in key for x in ("avatar","image","photo")):
                    try:child=canonical_link(value)
                    except AppError:continue
                    yield relationship(url,child,url,1)
        elif r["status"]=="Not Found":
            yield item("profile_check",url,url,title=site,status="UNVERIFIED",raw=r,reason="User Scanner melaporkan Not Found; bukan bukti akun tidak pernah ada.")
        else:
            rec=failed(url,AppError("UPSTREAM_CHECK",site+": "+str(r.get("reason") or r["status"])))
            rec["raw"]=r;yield rec
