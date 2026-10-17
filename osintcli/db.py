import json
from contextlib import contextmanager
import sqlite3
import uuid
from .core import now, canonical, digest, AppError

SCHEMA = '''
CREATE TABLE cases(id TEXT PRIMARY KEY, target TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL, state TEXT NOT NULL, scope TEXT NOT NULL);
CREATE TABLE jobs(id TEXT PRIMARY KEY, case_id TEXT REFERENCES cases(id) ON DELETE CASCADE, adapter TEXT, state TEXT, started_at TEXT, ended_at TEXT, error_code TEXT, message TEXT, version TEXT);
CREATE TABLE evidence(id TEXT PRIMARY KEY, case_id TEXT REFERENCES cases(id) ON DELETE CASCADE, entity_type TEXT, normalized_value TEXT, title TEXT, source_url TEXT, source_name TEXT, adapter_id TEXT, collected_at TEXT, scope_id TEXT, status TEXT, verification_reason TEXT, confidence_basis TEXT, digest TEXT, error_code TEXT, UNIQUE(case_id,digest));
CREATE TABLE raw_evidence(evidence_id TEXT PRIMARY KEY REFERENCES evidence(id) ON DELETE CASCADE, raw_json TEXT NOT NULL);
CREATE TABLE narratives(id TEXT PRIMARY KEY, case_id TEXT REFERENCES cases(id) ON DELETE CASCADE, created_at TEXT, provider TEXT, instructions TEXT, prompt_digest TEXT, text TEXT, reviewed INTEGER DEFAULT 0, dataset_digest TEXT);
PRAGMA user_version=1;
'''

class Store:
    def __init__(self, config):
        self.config = config
        self.path = config.data/"osintcli.db"
        with self.connect() as c:
            v=c.execute("PRAGMA user_version").fetchone()[0]
            if v>1: raise AppError("DB_VERSION", "Database lebih baru dari aplikasi.")
            if v<1:
                if self.path.exists() and self.path.stat().st_size:
                    with sqlite3.connect(str(self.path)+".backup") as b: c.backup(b)
                c.executescript(SCHEMA)
            c.execute("PRAGMA journal_mode=WAL")
        self.path.chmod(0o600)

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=15)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            with c:
                yield c
        finally:
            c.close()

    def create(self, value, kind, scope):
        cid=uuid.uuid4().hex[:12]
        with self.connect() as c: c.execute("INSERT INTO cases VALUES(?,?,?,?,?,?)",(cid,value,kind,now(),"QUEUED",canonical(scope)))
        return cid

    def case(self, cid):
        with self.connect() as c: r=c.execute("SELECT * FROM cases WHERE id=?",(cid,)).fetchone()
        if not r: raise AppError("CASE", "Case tidak ditemukan.")
        d=dict(r);d["scope"]=json.loads(d["scope"]); return d

    def cases(self):
        with self.connect() as c: return [dict(x) for x in c.execute("SELECT * FROM cases ORDER BY created_at DESC,rowid DESC")]

    def state(self, cid, state):
        with self.connect() as c:c.execute("UPDATE cases SET state=? WHERE id=?",(state,cid))

    def recover(self):
        # Called only while holding the process lock. Never interrupt another CLI.
        with self.connect() as c:
            c.execute("UPDATE jobs SET state='INTERRUPTED',ended_at=? WHERE state IN ('RUNNING','QUEUED')",(now(),))
            c.execute("UPDATE cases SET state='INTERRUPTED' WHERE state='RUNNING'")

    def start_job(self,cid,adapter,version="builtin-1.0.0"):
        jid=uuid.uuid4().hex
        with self.connect() as c:c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",(jid,cid,adapter,"RUNNING",now(),None,None,None,version))
        return jid

    def end_job(self,jid,state,code=None,message=None):
        with self.connect() as c:c.execute("UPDATE jobs SET state=?,ended_at=?,error_code=?,message=? WHERE id=?",(state,now(),code,message,jid))

    def jobs(self,cid):
        with self.connect() as c:return [dict(r) for r in c.execute("SELECT * FROM jobs WHERE case_id=? ORDER BY started_at,rowid",(cid,))]

    def add(self,cid,adapter,item):
        ts=now(); eid=uuid.uuid4().hex[:16]
        item={"entity_type":"observation","status":"UNVERIFIED","source_url":"","source_name":adapter,"verification_reason":"Observasi sumber publik, bukan verifikasi identitas.","confidence_basis":"Aturan adapter; tinjau sumber.","error_code":None,**item}
        value=item.get("value","")
        if not isinstance(value,str): value=canonical(value)
        fingerprint=digest({k:v for k,v in {**item,"value":value}.items() if k!="raw"})
        with self.connect() as c:
            r=c.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,cid,item["entity_type"],value,item.get("title",item["entity_type"]),item["source_url"],item["source_name"],adapter,ts,cid,item["status"],item["verification_reason"],item["confidence_basis"],fingerprint,item["error_code"]))
            if r.rowcount:c.execute("INSERT INTO raw_evidence VALUES(?,?)",(eid,canonical(item.get("raw",value))))
        return bool(r.rowcount)

    def evidence(self,cid,raw=False):
        self.case(cid)
        with self.connect() as c:
            rows=[dict(r) for r in c.execute("SELECT * FROM evidence WHERE case_id=? ORDER BY collected_at,id",(cid,))]
            if raw:
                for r in rows:r["raw"]=json.loads(c.execute("SELECT raw_json FROM raw_evidence WHERE evidence_id=?",(r["id"],)).fetchone()[0])
        return rows

    def dataset_digest(self,cid): return digest(self.evidence(cid,raw=True))

    def delete(self,cid):
        self.case(cid)
        with self.connect() as c:c.execute("DELETE FROM cases WHERE id=?",(cid,))
        import shutil
        shutil.rmtree(self.config.data/"cases"/cid,ignore_errors=True)
        shutil.rmtree(self.config.data/"reports"/cid,ignore_errors=True)

    def save_narrative(self,cid,provider,instructions,prompt,text):
        nid=uuid.uuid4().hex[:12]
        with self.connect() as c:c.execute("INSERT INTO narratives VALUES(?,?,?,?,?,?,?,?,?)",(nid,cid,now(),provider,instructions,digest(prompt),text,0,self.dataset_digest(cid)))
        return nid

    def review(self,nid):
        with self.connect() as c:
            if not c.execute("SELECT id FROM narratives WHERE id=?",(nid,)).fetchone():raise AppError("NARRATIVE","Narasi tidak ditemukan.")
            c.execute("UPDATE narratives SET reviewed=1 WHERE id=?",(nid,))

    def narrative(self,cid,reviewed=False):
        with self.connect() as c:
            q="SELECT * FROM narratives WHERE case_id=?"+(" AND reviewed=1" if reviewed else "")+" ORDER BY created_at DESC,rowid DESC LIMIT 1"
            r=c.execute(q,(cid,)).fetchone()
        if r and r["dataset_digest"]==self.dataset_digest(cid):return dict(r)
        return None
