import argparse
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
from . import __version__
from .core import Config,AppError,target
from .db import Store
from .engine import run,scope_for,demo,ProcessLock
from .external import executable,PINS
from .reports import export
from .ui import UI
from .ai import build_prompt,narrate,request_args


def doctor(config):
    rows={"version":__version__,"python":sys.version.split()[0],"platform":sys.platform,"data":str(config.data),"config":str(config.path),"core":"READY","reports":{},"tools":{}}
    for name in ("reportlab","PIL","pypdf","arabic_reshaper","bidi","docx"):
        rows["reports"][name]="READY" if importlib.util.find_spec(name) else "UNAVAILABLE"
    for name in PINS:
        path=executable(name,config)
        rows["tools"][name]={"status":"INSTALLED (live compatibility must be checked)" if path else "OPTIONAL / UNAVAILABLE","path":path,"audited_commit":PINS[name]}
    rows["network"]="Not tested by doctor; use scan for a selected public target."
    rows["network"]={"transport":config["http_transport"],"live_test":"Gunakan scan untuk menguji sumber."}
    return rows


def choose_case(ui,db):
    cases=db.cases()
    if not cases:ui.put("Belum ada kasus.");return None
    for c in cases[:30]:ui.put(f"{c['id']} / {c['state']}\n{c['target']}")
    cid=ui.ask("Case ID (Enter: terbaru / 0: kembali)")
    if cid=="0":return None
    cid=cid or cases[0]["id"];db.case(cid);return cid


def scan_flow(ui,config,kind="auto"):
    value=ui.ask("Target (0: kembali)")
    if value=="0":return
    kind,value=target(value,kind)
    names=scope_for(kind)
    if kind=="username":
        choice=ui.ask("Engine: 1 Fusion / 2 Sherlock / 3 Maigret / 4 User Scanner / 5 builtin / 0 kembali")
        if choice=="0":return
        if choice not in ("","1","2","3","4","5"):raise AppError("INPUT","Pilihan tidak valid.")
        names=[{"2":"sherlock","3":"maigret","4":"user-scanner","5":"username"}.get(choice,"fusion")]
    if "fusion" in names:
        mode=ui.ask("Mode: quick / standard [default] / deep / 0 kembali")
        if mode=="0":return
        config.set("fusion_mode",mode or "standard")
    if kind=="domain" and ui.confirm("Tambahkan HTTP/TLS langsung ke website?"):names += ["web","tls"]
    if kind=="metadata":
        ui.put("Metadata bisa mengandung GPS/identitas. File diproses lokal.")
        if executable("exiftool",config) and ui.confirm("Tambahkan ExifTool lokal?"):names += ["exiftool"]
    ui.heading("Scope preview");ui.put(value);ui.put("Modul: "+", ".join(names));ui.put("Fusion: "+config["fusion_mode"]+" / batas "+str(config["fusion_max_nodes"])+" halaman" if "fusion" in names else "Scope modul terpilih.")
    if not ui.confirm("Target berizin/publik dan scope sesuai. Jalankan?"):return
    ui.put("Mengambil sumber... Ctrl+C: hentikan.")
    start=time.monotonic()
    cid=run(config,value,kind,names,lambda i,total,n,s,c:ui.put(f"[{i}/{total}] {n}: {s}\n{c} evidence baru / {time.monotonic()-start:.1f}s"))
    db=Store(config);ui.put("Case: "+cid+" / "+db.case(cid)["state"])
    ui.evidence(db.evidence(cid))


def ai_flow(ui,config,db):
    cid=choose_case(ui,db)
    if not cid:return
    limit=int(ui.ask("Jumlah evidence dibagikan [1]") or "1")
    prompt=build_prompt(db,cid,limit)
    ui.heading("Preview data keluar");ui.put(prompt)
    ui.put("Tujuan: "+config["endpoint"])
    ui.put("GET menyimpan prompt pada URL/log provider. File mentah tidak dikirim.")
    request_args(config,prompt)
    if not ui.confirm("Kirim subset ini ke provider eksternal?"):return
    try:nid=narrate(db,cid,prompt,consent=True)
    except AppError as e:
        ui.put(f"AI unavailable [{e.code}]: {e}");ui.put("Laporan tanpa AI tetap bisa dibuat.");return
    text=db.narrative(cid)["text"];ui.heading("Draft AI - periksa fakta");ui.put(text)
    if ui.confirm("Sudah memeriksa narasi dan menyetujui untuk laporan?"):db.review(nid);ui.put("Narasi ditandai reviewed.")
    else:ui.put("Draft disimpan, tidak dimasukkan ke laporan.")


def report_flow(ui,config,db):
    cid=choose_case(ui,db)
    if not cid:return
    formats=ui.ask("Format: pdf,docx,json,csv,html,png [semua] / 0 kembali")
    if formats=="0":return
    formats=[x.strip() for x in formats.split(",")] if formats else ["pdf","docx","json","csv","html","png"]
    summary=ui.confirm("Laporan ringkasan (maks 15 evidence)?") if any(f in formats for f in ("pdf","docx")) else False
    ai=bool(db.narrative(cid,True)) and ui.confirm("Sertakan narasi AI yang sudah reviewed?")
    out=ui.ask("Folder output (Enter/lokal: folder laporan / android / path / 0 kembali)")
    if out=="0":return
    if out=="lokal":out=""
    if out=="android":
        p=Path.home()/"storage/downloads"
        if not p.is_dir() or not os.access(p,os.W_OK):raise AppError("STORAGE","Jalankan termux-setup-storage, izinkan akses, lalu ulangi export.")
        out=str(p/"OsintCLI"/cid)
    for path in export(db,cid,formats,out or None,ai,summary):ui.path(path,"Tersimpan: ")


def interactive(config,ui):
    db=Store(config)
    with ProcessLock(config):db.recover()
    ui.startup(config,db)
    while True:
        ui.menu()
        try:
            choice=ui.ask("Pilih nomor")
            if choice in ("0","00"):return 0
            n=int(choice)
            if 1<=n<=6:scan_flow(ui,config,{1:"auto",2:"username",3:"domain",4:"ip",5:"email",6:"metadata"}[n])
            elif n==7:
                cid=choose_case(ui,db)
                if cid:
                    action=ui.ask("1 evidence / 2 resume / 3 hapus / 4 hubungan / 5 review / 0 kembali")
                    if action=="1":ui.evidence(db.evidence(cid))
                    elif action=="4":show_graph(ui,db,cid)
                    elif action=="5":review_flow(ui,db,cid)
                    elif action=="2":
                        run(config,"",resume=cid,progress=lambda i,t,n,s,c:ui.put(f"[{i}/{t}] {n}: {s}"));ui.put("Status: "+db.case(cid)["state"])
                    elif action=="3" and ui.confirm("Hapus kasus dan laporan lokalnya?"):
                        with ProcessLock(config):db.delete(cid)
                        ui.put("Kasus dihapus. Salinan export eksternal tidak dihapus.")
            elif n==8:ai_flow(ui,config,db)
            elif n==9:report_flow(ui,config,db)
            elif n==10:
                ui.put(json.dumps(doctor(config),indent=2,ensure_ascii=False))
                ui.put("Tools: bash scripts/install-tools.sh user-scanner|sherlock|maigret|exiftool")
                key=ui.ask("Nama setting untuk edit (0: kembali)")
                if key!="0":
                    if key not in config.values:raise AppError("CONFIG","Nama setting tidak dikenal.")
                    ui.put("Saat ini: "+str(config[key]));config.set(key,ui.ask("Nilai baru"));ui.put("Disimpan.")
            elif n in (11,12):scan_flow(ui,config,"profile" if n==11 else "phone")
            else:ui.put("Pilih 00-12.")
        except (ValueError,AppError) as e:ui.put(f"Gagal: {e}")
        except KeyboardInterrupt:ui.put("Dibatalkan. Kembali ke menu.")
        except EOFError:return 0


def show_graph(ui,db,cid):
    edges=db.graph(cid)
    if not edges:ui.put("Belum ada hubungan publik dalam kasus ini.")
    for edge in edges:
        ui.heading(edge["evidence_id"]+" / "+edge["review"]["decision"])
        ui.put(edge["from"]+"\n→ "+edge["to"])
        ui.put(edge["relation"]+" / depth "+str(edge["depth"]))
        ui.put("Sumber: "+edge["source_url"])
        if edge["review"].get("note"):ui.put("Catatan: "+edge["review"]["note"])


def review_flow(ui,db,cid):
    ui.evidence([r for r in db.evidence(cid) if r["entity_type"] in ("profile","relationship")])
    eid=ui.ask("Evidence ID (0 kembali)")
    if eid=="0":return
    choice=ui.ask("1 terima / 2 tolak / 3 pending / 0 kembali")
    if choice=="0":return
    decision={"1":"accepted","2":"rejected","3":"pending"}.get(choice)
    if not decision:raise AppError("REVIEW","Pilihan tidak valid.")
    note=ui.ask("Catatan alasan review")
    db.review_evidence(cid,eid,decision,note)
    ui.put("Review disimpan. Penerimaan adalah penilaian Anda, bukan verifikasi identitas otomatis.")


def parser():
    p=argparse.ArgumentParser(description="OSINTCLI by R_HMT — numbered terminal + public-source evidence")
    p.add_argument("--version",action="version",version=__version__)
    p.add_argument("--data-dir");p.add_argument("--config-dir");p.add_argument("--width",type=int)
    s=p.add_subparsers(dest="command")
    s.add_parser("menu");s.add_parser("doctor")
    a=s.add_parser("scan",help="Preview and run a public/authorized target")
    a.add_argument("target");a.add_argument("--kind",choices=["auto","domain","ip","email","username","metadata","profile","phone"],default="auto")
    a.add_argument("--mode",choices=["quick","standard","deep"])
    a.add_argument("--max-nodes",type=int)
    a.add_argument("--modules",help="Comma-separated selected adapters")
    a.add_argument("--yes",action="store_true",help="Confirm displayed scope and target authorization")
    a=s.add_parser("resume");a.add_argument("case_id");a.add_argument("--yes",action="store_true")
    s.add_parser("history")
    a=s.add_parser("show");a.add_argument("case_id");a.add_argument("--json",action="store_true")
    a=s.add_parser("delete");a.add_argument("case_id");a.add_argument("--yes",action="store_true")
    a=s.add_parser("report");a.add_argument("case_id");a.add_argument("--formats",default="pdf,docx,json,csv,html,png");a.add_argument("--out");a.add_argument("--include-ai",action="store_true");a.add_argument("--summary",action="store_true")
    a=s.add_parser("demo",help="Create a labelled offline fixture case")
    a.add_argument("--count",type=int,default=12);a.add_argument("--report",action="store_true");a.add_argument("--out")
    a=s.add_parser("config");a.add_argument("key",nargs="?");a.add_argument("value",nargs="?")
    a=s.add_parser("ai");a.add_argument("case_id");a.add_argument("--limit",type=int,default=1);a.add_argument("--include-sensitive",action="store_true");a.add_argument("--send",action="store_true");a.add_argument("--yes",action="store_true",help="Explicit consent to displayed evidence leaving device")
    a=s.add_parser("review");a.add_argument("case_id");a.add_argument("--approve",action="store_true")
    a=s.add_parser("graph");a.add_argument("case_id");a.add_argument("--json",action="store_true")
    a=s.add_parser("evidence-review");a.add_argument("case_id");a.add_argument("evidence_id");a.add_argument("decision",choices=["accepted","rejected","pending"]);a.add_argument("--note",required=True)
    return p


def main(argv=None):
    args=parser().parse_args(argv);ui=UI(args.width)
    try:
        config=Config(args.data_dir,args.config_dir);db=Store(config)
        cmd=args.command
        if cmd in (None,"menu"):
            if not sys.stdin.isatty():ui.banner();ui.menu();ui.put("Non-interactive: gunakan --help atau scan/demo.");return 0
            return interactive(config,ui)
        if cmd=="doctor":print(json.dumps(doctor(config),indent=2,ensure_ascii=False))
        elif cmd=="scan":
            if args.mode:config.set("fusion_mode",args.mode)
            if args.max_nodes is not None:config.set("fusion_max_nodes",args.max_nodes)
            kind,value=target(args.target,args.kind);names=scope_for(kind,args.modules.split(",") if args.modules else None)
            ui.put("Target: "+value+"\nScope: "+", ".join(names)+"\nMode: "+config["fusion_mode"]+" / Ctrl+C: cancel")
            if not args.yes:ui.put("Preview saja. Tambahkan --yes untuk menjalankan scope berizin ini.");return 0
            start=time.monotonic()
            cid=run(config,value,kind,names,lambda i,t,n,s,c:ui.put(f"[{i}/{t}] {n}: {s} / {c} new / {time.monotonic()-start:.1f}s"))
            ui.put("CASE_ID="+cid);ui.put("STATE="+db.case(cid)["state"])
            return 0 if db.case(cid)["state"]=="DONE" else 2
        elif cmd=="resume":
            case=db.case(args.case_id);ui.put("Scope: "+", ".join(case["scope"]))
            if not args.yes:ui.put("Tambahkan --yes untuk melanjutkan job gagal/interrupted.");return 0
            cid=run(config,"",resume=args.case_id,progress=lambda i,t,n,s,c:ui.put(f"[{i}/{t}] {n}: {s}"))
            ui.put("STATE="+db.case(cid)["state"]);return 0 if db.case(cid)["state"]=="DONE" else 2
        elif cmd=="history":
            for c in db.cases():ui.put(c["id"]+" / "+c["state"]+" / "+c["target"])
        elif cmd=="show":
            rows=db.evidence(args.case_id,raw=args.json)
            if args.json:print(json.dumps(rows,ensure_ascii=False,indent=2))
            else:ui.evidence(rows,paginate=False)
        elif cmd=="delete":
            db.case(args.case_id)
            if not args.yes:ui.put("Tambahkan --yes untuk hapus kasus/laporan lokal. Salinan eksternal tetap ada.");return 0
            with ProcessLock(config):db.delete(args.case_id)
            ui.put("Kasus dihapus.")
        elif cmd=="report":
            for path in export(db,args.case_id,args.formats.split(","),args.out,args.include_ai,args.summary):ui.path(path)
        elif cmd=="demo":
            if not 0<=args.count<=1000:raise AppError("INPUT","Demo count harus 0-1000.")
            with ProcessLock(config):cid=demo(config,args.count)
            ui.put("OFFLINE FIXTURE / CASE_ID="+cid)
            if args.report:
                for path in export(db,cid,out=args.out):ui.path(path)
        elif cmd=="config":
            if args.key is None:print(json.dumps(config.values,indent=2,ensure_ascii=False))
            elif args.value is None:
                if args.key not in config.values:raise AppError("CONFIG","Setting tidak dikenal.")
                ui.put(str(config[args.key]))
            else:config.set(args.key,args.value);ui.put("Disimpan.")
        elif cmd=="ai":
            prompt=build_prompt(db,args.case_id,args.limit,args.include_sensitive)
            ui.put("EXTERNAL AI PREVIEW\n"+prompt);ui.put("Provider: "+config["endpoint"]+"\nGET prompt dapat tersimpan di log provider.")
            request_args(config,prompt)
            if not args.send:ui.put("Belum dikirim. Gunakan --send --yes setelah meninjau preview.");return 0
            nid=narrate(db,args.case_id,prompt,consent=args.yes)
            ui.put("NARRATIVE_ID="+nid);ui.put(db.narrative(args.case_id)["text"]);ui.put("Tinjau dengan review CASE_ID sebelum masuk laporan.")
        elif cmd=="graph":
            if args.json:print(json.dumps(db.graph(args.case_id),ensure_ascii=False,indent=2))
            else:show_graph(ui,db,args.case_id)
        elif cmd=="evidence-review":
            db.review_evidence(args.case_id,args.evidence_id,args.decision,args.note);ui.put("Review disimpan; bukti asli tetap tersimpan.")
        elif cmd=="review":
            narrative=db.narrative(args.case_id)
            if not narrative:raise AppError("NARRATIVE","Tidak ada narasi untuk dataset terbaru.")
            ui.put(narrative["text"])
            if args.approve:db.review(narrative["id"]);ui.put("Reviewed.")
            else:ui.put("Tambahkan --approve setelah memeriksa fakta.")
        return 0
    except KeyboardInterrupt:ui.put("Dibatalkan.");return 130
    except (AppError,ValueError,OSError) as e:
        ui.put(f"ERROR [{getattr(e,'code','LOCAL')}] {e if isinstance(e,AppError) else 'Operasi lokal gagal; periksa input, izin, atau ruang penyimpanan.'}")
        return 2
