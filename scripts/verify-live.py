#!/usr/bin/env python3
"""Real CLI → online source → SQLite → export verification; no mocked transport.

Targets: IANA example.com, Cloudflare 1.1.1.1, public GitHub octocat.
The PNG is a controlled local fixture, clearly distinguished from online evidence.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from osintcli import __version__
from osintcli.core import Config,now
from osintcli.db import Store
from osintcli.net import Client
from osintcli.external import executable

p=argparse.ArgumentParser()
p.add_argument('--out',default='live-verification')
p.add_argument('--transport',choices=['direct','proxy'],default='direct')
p.add_argument('--include-tools',action='store_true')
p.add_argument('--only',help='Comma-separated check labels to run')
a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
base=Config();config=Config(out/'data',out/'config')
config.set('http_transport',a.transport)
config.set('timeout_seconds',20);config.set('retries',0)
# Explicitly authorize only the named IANA website for this live check.
config.set('proxy_allowed_hosts',config['proxy_allowed_hosts']+',example.com')
env={**os.environ,'PYTHONPATH':str(ROOT),'OSINTCLI_DATA_DIR':str(config.data),'OSINTCLI_CONFIG_DIR':str(config.directory),'NO_COLOR':'1'}
paths=[]
for tool in ['sherlock','maigret','exiftool']:
    path=executable(tool,base)
    if path:paths.append(str(Path(path).parent))
env['PATH']=os.pathsep.join(paths+[os.environ.get('PATH','')])
from PIL import Image
im=Image.new('RGB',(137,83),'#00c6d7');exif=Image.Exif();exif[315]='OSINTCLI controlled metadata test'
image=out/'controlled-local-test.jpg';im.save(image,exif=exif)
expected_hash=hashlib.sha256(image.read_bytes()).hexdigest()
checks=[('domain','example.com','domain','dns,rdap,ct'),('ip','1.1.1.1','ip','rdap,asn'),('email','test@example.com','email','email'),('website','example.com','domain','web'),('tls','example.com','domain','tls'),('username-positive','octocat','username','username'),('username-negative','osintcli-no-account-20261017-7fe93c','username','username'),('metadata',str(image),'metadata','metadata')]
if a.include_tools:checks += [('sherlock','octocat','username','sherlock'),('maigret','octocat','username','maigret'),('exiftool',str(image),'metadata','exiftool')]
if a.only:checks=[c for c in checks if c[0] in a.only.split(',')]
if not checks:p.error('No selected live checks matched --only')
results=[]
for label,value,kind,modules in checks:
    print('LIVE CHECK:',label,flush=True)
    command=[sys.executable,'-m','osintcli','--width','120','scan',value,'--kind',kind,'--modules',modules,'--yes']
    start=time.monotonic()
    r=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=150)
    (out/(label+'.log')).write_text(r.stdout+r.stderr)
    found=re.search(r'CASE_ID=([a-f0-9]{12})',r.stdout)
    result={'label':label,'target':image.name if kind=='metadata' else value,'modules':modules.split(','),'completed_at':now(),'duration_seconds':round(time.monotonic()-start,2),'exit_code':r.returncode,'verdict':'FAIL','checks':{}}
    if not found:
        result['diagnostic']='CLI did not return a case ID';results.append(result);print(result,flush=True);continue
    cid=found.group(1);db=Store(config);case=db.case(cid);rows=db.evidence(cid,raw=True);results_dir=out/label
    formats='pdf,json,csv,html,png' if label in ('domain','ip','metadata') else 'json'
    exp=subprocess.run([sys.executable,'-m','osintcli','--width','120','report',cid,'--formats',formats,'--out',str(results_dir)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
    (out/(label+'-export.log')).write_text(exp.stdout+exp.stderr)
    result.update(case_id=cid,case_state=case['state'],evidence_count=len(rows),counts_by_status=dict(Counter(x['status'] for x in rows)),export_exit=exp.returncode)
    result['source_errors']=[{'adapter':x['adapter_id'],'code':x['error_code'],'source':x['source_url'] or x['source_name'],'message':x['normalized_value']} for x in rows if x['status']=='FAILED_SOURCE']
    c=result['checks'];c['case_saved']=True;c['json_export']=exp.returncode==0 and bool(list(results_dir.glob('*.json')))
    observed=[x for x in rows if x['status']!='FAILED_SOURCE']
    if label=='domain':
        c['dns_a_values']=any(x['entity_type']=='dns' and x['title']=='DNS A' for x in observed)
        c['rdap_domain']=any(x['entity_type']=='rdap' and x['title']=='RDAP / ldhName' and x['normalized_value'].lower()=='example.com' for x in observed)
        c['ct_names']=any(x['entity_type']=='certificate_name' and (x['normalized_value']=='example.com' or x['normalized_value'].endswith('.example.com')) for x in observed)
    elif label=='ip':
        c['rdap_network']=any(x['entity_type']=='rdap' and x['title']=='RDAP / startAddress' for x in observed)
        c['asn_cloudflare']=any(x['entity_type']=='asn' and '13335' in x['normalized_value'] for x in observed)
    elif label=='email':
        c['syntax']=any(x['entity_type']=='email_syntax' for x in rows)
        c['mail_dns']=any(x['title']=='DNS MX' and x['entity_type']=='dns' for x in observed)
        c['spf']=any('v=spf1' in x['normalized_value'] for x in observed)
    elif label=='website':c['homepage_observed']=any(x['title']=='HTTP /' and '200' in x['normalized_value'] for x in observed)
    elif label=='tls':c['origin_certificate']=any(x['entity_type']=='tls' for x in observed)
    elif label.startswith('username-'):
        github=[x for x in rows if x['source_url'].startswith('https://api.github.com/users/')]
        if label=='username-positive':c['github_login_id']=any(x['entity_type']=='profile' and x['raw'].get('login','').lower()=='octocat' and x['raw'].get('id')==583231 for x in github)
        else:c['negative_control']=any(x['entity_type']=='profile_check' and '404' in x['normalized_value'] for x in github) and not any(x['entity_type']=='profile' for x in github)
    elif label=='metadata':
        c['dimensions']=any(x['entity_type']=='image_metadata' and x['raw'].get('width')==137 and x['raw'].get('height')==83 for x in rows)
        c['sha256']=any(x['entity_type']=='file' and x['raw'].get('sha256')==expected_hash for x in rows)
        c['artist']=any(x['title']=='Artist' and x['normalized_value']=='OSINTCLI controlled metadata test' for x in rows)
    elif label in ('sherlock','maigret'):c['github_candidate']=any(x['entity_type']=='profile' and 'github.com/octocat' in x['normalized_value'] for x in rows)
    elif label=='exiftool':
        c['dimensions']=any(x['title'].endswith(':ImageWidth') and x['normalized_value']=='137' for x in rows)
        c['artist']=any(x['title'].endswith(':Artist') and x['normalized_value']=='OSINTCLI controlled metadata test' for x in rows)
    if all(c.values()):result['verdict']='PASS_WITH_SOURCE_GAPS' if result['source_errors'] else 'PASS'
    elif observed:result['verdict']='PARTIAL'
    elif any(e['code']=='DIRECT_REQUIRED' for e in result['source_errors']):result['verdict']='UNVERIFIED_DIRECT_NETWORK_REQUIRED'
    results.append(result)
    print(label,result['verdict'],'evidence',len(rows),'state',case['state'],'checks',c,flush=True)

# Provider smoke test uses only a greeting, never case evidence or user data.
try:
    response=Client(config).request(config['endpoint']+'?text=Hai',redirects=0,max_bytes=32000,timeout=20,retries=0)
    try:
        payload=response.json();ok=isinstance(payload,dict) and payload.get('status') is True and isinstance(payload.get('result'),str) and bool(payload['result'].strip())
    except Exception:ok=False
    provider={'http_status':response.status,'content_type':response.headers.get('content-type'),'verdict':'PASS' if ok else 'UNAVAILABLE','body_preview':response.body[:250].decode('utf-8',errors='replace')}
except Exception as error:provider={'verdict':'UNAVAILABLE','error_code':getattr(error,'code',type(error).__name__)}
summary={'version':__version__,'generated_at':now(),'transport':a.transport,'method':'Real subprocess CLI calls; no injected client or mocked responses. Local image is a controlled fixture.','results':results,'provider_smoke':provider}
summary['fully_available']=all(r.get('case_state')=='DONE' and r['verdict']=='PASS' for r in results) and provider['verdict']=='PASS'
(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
print('SUMMARY',out/'summary.json',flush=True)
print('AI',provider,flush=True)

raise SystemExit(0 if summary['fully_available'] else 2)
