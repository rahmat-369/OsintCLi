#!/usr/bin/env python3
"""Live V2 CLI verification, separate from synthetic regression tests."""
import argparse,json,os,re,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from osintcli.core import Config
from osintcli.db import Store
p=argparse.ArgumentParser();p.add_argument('--out',default='output/live-v2');p.add_argument('--transport',choices=['direct','proxy'],default='direct');p.add_argument('--include-tools',action='store_true');p.add_argument('--only',help='Comma-separated labels');a=p.parse_args()
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);cfg=Config(out/'data',out/'config');cfg.set('http_transport',a.transport);cfg.set('timeout_seconds',12);cfg.set('retries',0)
cfg.set('proxy_allowed_hosts',cfg['proxy_allowed_hosts']+',github.blog,example.com,www.iana.org,www.youtube.com')
env={**os.environ,'PYTHONPATH':str(ROOT),'OSINTCLI_DATA_DIR':str(cfg.data),'OSINTCLI_CONFIG_DIR':str(cfg.directory)}
# Reuse installed optional engine without copying credentials or altering DB.
base=Config();tool=base.data/'tools/user-scanner/bin'
if tool.exists():env['PATH']=str(tool)+os.pathsep+env.get('PATH','')
checks=[('fusion-positive','octocat',['--kind','username','--mode','standard','--max-nodes','8']),('fusion-negative','osintcliqz9x726',['--kind','username','--mode','standard','--max-nodes','5']),('profile-pivot','https://github.com/octocat',['--kind','profile','--mode','deep','--max-nodes','4']),('phone-format','+6281234567890',['--kind','phone'])]
if a.include_tools:checks.append(('user-scanner','octocat',['--kind','username','--modules','user-scanner']))
if a.only:checks=[x for x in checks if x[0] in a.only.split(',')]
if not checks:p.error("No matching checks")
results=[]
for label,value,flags in checks:
 print('LIVE:',label,flush=True)
 r=subprocess.run([sys.executable,'-m','osintcli','--width','120','scan',value,*flags,'--yes'],cwd=ROOT,env=env,text=True,capture_output=True,timeout=240)
 (out/(label+'.log')).write_text(r.stdout+r.stderr)
 m=re.search(r'CASE_ID=([a-f0-9]{12})',r.stdout)
 row={'label':label,'exit_code':r.returncode,'completed_at':datetime.now(timezone.utc).isoformat()}
 if m:
  db=Store(cfg);cid=m[1];evidence=db.evidence(cid,True)
  row.update(case_id=cid,state=db.case(cid)['state'],records=len(evidence),profiles=[{'title':e['title'],'source':e['source_url']} for e in evidence if e['entity_type']=='profile'],relationships=len(db.graph(cid)),errors=[{'source':e['source_url'],'code':e['error_code']} for e in evidence if e['status']=='FAILED_SOURCE'])
  row['functional_checks']={'case_saved':True,'github_positive':any(e['entity_type']=='profile' and 'github' in e['title'].lower() for e in evidence) if label in ('fusion-positive','profile-pivot','user-scanner') else None,'negative_not_candidate':not any(e['entity_type']=='profile' for e in evidence) if label=='fusion-negative' else None,'phone_only_format':all(e['entity_type']=='phone_format' for e in evidence) if label=='phone-format' else None}
  formats='pdf,docx,json,csv,html,png' if label=='profile-pivot' else 'json'
  exp=subprocess.run([sys.executable,'-m','osintcli','report',cid,'--formats',formats,'--out',str(out/label)],cwd=ROOT,env=env,text=True,capture_output=True,timeout=90)
  (out/(label+'-export.log')).write_text(exp.stdout+exp.stderr);row['export_exit']=exp.returncode
 else:row['failure']='CLI did not return a case ID'
 results.append(row);print(json.dumps(row),flush=True)
 (out/'summary.json').write_text(json.dumps(results,indent=2))
raise SystemExit(0 if all(r.get('state')=='DONE' and r.get('export_exit')==0 for r in results) else 2)
