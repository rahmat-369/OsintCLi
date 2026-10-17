from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import fcntl
import signal
import threading
from .core import AppError, target, now
from .db import Store
from .net import Client
from .adapters import ADAPTERS, DEFAULT_SCOPE, ALLOWED, failed
from .external import external, PINS, executable
from . import __version__
from .fusion import fusion, phone
ADAPTERS.update(fusion=fusion, phone=phone)
DEFAULT_SCOPE.update(username=["fusion"], profile=["fusion"], phone=["phone"])
ALLOWED["username"].update({"fusion","user-scanner"})
ALLOWED.update(profile={"fusion"}, phone={"phone"})

@dataclass
class Context:
    value: str
    kind: str
    config: object
    client: object
    stop: object

class ProcessLock:
    def __init__(self,config):self.path=config.data/"run.lock"
    def __enter__(self):
        self.file=open(self.path,"a+")
        try:fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.file.close();raise AppError("BUSY","Proses OsintCLI lain sedang memakai data ini.")
        return self
    def __exit__(self,*args):self.file.close()

def scope_for(kind,modules=None):
    names=modules or DEFAULT_SCOPE[kind]
    if not names or any(x not in ALLOWED[kind] for x in names):raise AppError("SCOPE","Modul tidak sesuai jenis target.")
    if sum(x in names for x in ("username","sherlock","maigret","fusion","user-scanner"))>1:raise AppError("SCOPE","Pilih satu engine username untuk menghindari kueri duplikat.")
    return list(dict.fromkeys(names))

def run(config,value,kind="auto",modules=None,progress=None,resume=None,client=None):
    db=Store(config);stop=threading.Event()
    if resume:
        case=db.case(resume);kind,value=target(case["target"],case["kind"]);names=scope_for(kind,case["scope"])
    else:
        kind,value=target(value,kind);names=scope_for(kind,modules)
    with ProcessLock(config):
        db.recover()
        if resume and "fusion" in names:
            scopes=[r["raw"] for r in db.evidence(resume,True) if r["entity_type"]=="collection_scope"]
            if scopes:
                from copy import copy
                config=copy(config);config.values=config.values.copy()
                config.values.update(fusion_mode=scopes[0]["mode"],fusion_max_nodes=scopes[0]["max_pages"])
        cid=resume or db.create(value,kind,names)
        if resume:
            latest={j["adapter"]:j["state"] for j in db.jobs(cid)}
            names=[n for n in names if latest.get(n) not in ("DONE",)]
        db.state(cid,"RUNNING")
        ctx=Context(value,kind,config,client or Client(config,stop),stop)
        def work(name):
            version="builtin-"+__version__
            if name in PINS:
                manifest=config.data/"tools"/name/"audited-commit.txt"
                version="pinned:"+manifest.read_text().strip() if manifest.exists() else "external / version unverified"
            jid=db.start_job(cid,name,version)
            count=0;bad=False
            try:
                if stop.is_set():raise AppError("CANCELLED","Dibatalkan.")
                generator=ADAPTERS[name](ctx) if name in ADAPTERS else external(ctx,name)
                for r in generator:
                    if stop.is_set():raise AppError("CANCELLED","Dibatalkan.")
                    bad |= r.get("status")=="FAILED_SOURCE"
                    count+=db.add(cid,name,r)
                state="PARTIAL" if bad else "DONE";db.end_job(jid,state)
            except Exception as error:
                code=getattr(error,"code","ADAPTER_ERROR")
                # Do not leak provider request URLs, local paths or tokens in tracebacks.
                message=str(error) if isinstance(error,AppError) else "Adapter gagal membaca sumber/format data."
                state="CANCELLED" if code=="CANCELLED" else "FAILED"
                db.end_job(jid,state,code,message)
                if state!="CANCELLED":db.add(cid,name,failed(name,AppError(code,message)))
            return name,state,count
        old=None
        if threading.current_thread() is threading.main_thread():
            old=signal.signal(signal.SIGINT,lambda *_:stop.set())
        try:
            with ThreadPoolExecutor(max_workers=config["max_workers"]) as pool:
                futures=[pool.submit(work,name) for name in names]
                for index,f in enumerate(as_completed(futures),1):
                    name,state,count=f.result()
                    if progress:progress(index,len(names),name,state,count)
        finally:
            if old is not None:signal.signal(signal.SIGINT,old)
            latest={j["adapter"]:j["state"] for j in db.jobs(cid)}
            state="CANCELLED" if stop.is_set() else ("DONE" if latest and all(s=="DONE" for s in latest.values()) else "PARTIAL")
            db.state(cid,state)
        return cid

def demo(config,count=12):
    db=Store(config)
    cid=db.create("example.com (OFFLINE FIXTURE)","domain",["demo"])
    jid=db.start_job(cid,"demo")
    for n in range(count):
        from .adapters import item
        db.add(cid,"demo",item("dns" if n%3 else "profile",f"fixture-{n}.example.com",f"https://example.com/evidence/{n}",title="Fixture observasi",status="VERIFIED" if n%3 else "CANDIDATE",reason="Data sintetis untuk pengujian; bukan hasil pencarian nyata."))
    db.end_job(jid,"DONE");db.state(cid,"DONE");return cid
