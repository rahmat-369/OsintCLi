import io
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock
from osintcli.core import Config,AppError,target
from osintcli.db import Store,SCHEMA
from osintcli.engine import Context,run
from osintcli.fusion import fusion,relationship,fetch_profile,tiktok_info,normalize_url,profile_key
from osintcli.net import Response
from osintcli.external import parse_user_scanner
from osintcli.reports import snapshot,export

class Fusion(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name)
        self.config=Config(p/'data',p/'config');self.db=Store(self.config)
    def tearDown(self):self.tmp.cleanup()
    def context(self,kind='username',value='sample',client=None):return Context(value,kind,self.config,client or Mock(),threading.Event())
    def response(self,data,url='https://api.github.com/users/sample',status=200):return Response(status,{'content-type':'application/json'},json.dumps(data).encode(),url)
    def test_relative_data_directory_resolves(self):
        import os
        relative=os.path.relpath(self.config.data)
        c=Config(relative,self.config.directory)
        self.assertTrue(c.data.is_absolute())

    def test_url_safety(self):
        for url in ['http://127.0.0.1','https://u:p@example.com','https://localhost/a','https://site.internal','https://example.com/?token=secret','https://example.com:22/a']:
            with self.subTest(url=url),self.assertRaises(AppError):normalize_url(url)
    def test_profile_namespace(self):
        self.assertEqual(profile_key('https://www.tiktok.com/@sample'),('tiktok','sample'))
        self.assertIsNone(profile_key('https://github.com/sample/repository'))
        self.assertIsNone(profile_key('https://www.instagram.com/p/abc'))
    def test_phone_format_not_identity(self):
        self.assertEqual(target('+62 812-3456-7890'),('phone','+6281234567890'))
        with self.assertRaises(AppError):target('+0123','phone')
    def test_json_decoder_handles_braces_inside_bio(self):
        d={'uniqueId':'sample','signature':'a } { "quoted" bio'}
        self.assertEqual(tiktok_info('<script>"userInfo": '+json.dumps(d)+'</script>'),d)
    def test_soft_200_rejected(self):
        client=Mock();client.request.return_value=self.response({'login':'other','id':1})
        with self.assertRaises(AppError):fetch_profile(self.context(client=client),'github','sample')
    def test_tiktok_private_is_error(self):
        client=Mock();client.request.return_value=self.response({},status=400)
        with self.assertRaises(AppError):fetch_profile(self.context(client=client),'tiktok','sample')
    def test_instagram_login_page_is_error(self):
        client=Mock();client.request.return_value=Response(200,{'content-type':'text/html'},b'<title>Login</title>','https://www.instagram.com/sample/')
        with self.assertRaises(AppError):fetch_profile(self.context(client=client),'instagram','sample')
    def test_pivot_cycles_provenance_and_contact(self):
        self.config.set('fusion_mode','deep')
        class Web:
            def __init__(self):self.urls=[]
            def request(self,url,**kwargs):
                self.urls.append(url)
                if 'api.github.com' in url:return Response(200,{'content-type':'application/json'},json.dumps({'login':'sample','id':1,'blog':'https://example.com','bio':'contact@example.com'}).encode(),url)
                return Response(200,{'content-type':'text/html'},b'<title>Example</title><a href="https://github.com/sample">profile</a><a href="https://wa.me/628123456789">contact</a><a href="http://127.0.0.1">blocked</a>',url)
            def json(self,url):return []
        c=Web();rows=list(fusion(self.context('profile','https://github.com/sample',c)))
        edges=[r for r in rows if r['entity_type']=='relationship']
        self.assertEqual(len(c.urls),2)
        self.assertTrue(any(r['raw']['to']=='https://example.com/' and r['source_url'].startswith('https://api.github.com') for r in edges))
        self.assertTrue(any(r['raw']['relation']=='PUBLIC_CONTACT' for r in edges))
        self.assertFalse(any('127.0.0.1' in url or 'wa.me' in url for url in c.urls))
    def test_node_budget(self):
        self.config.set('fusion_max_nodes',1)
        c=Mock();c.request.return_value=self.response({'login':'sample','id':1});c.json.return_value=[]
        rows=list(fusion(self.context(client=c)))
        self.assertEqual(c.request.call_count,1)
        self.assertTrue(any(r['entity_type']=='collection_limit' for r in rows))
    def test_cancellation(self):
        ctx=self.context();ctx.stop.set()
        with self.assertRaises(AppError):list(fusion(ctx))
        ctx.client.request.assert_not_called()
    def test_review_is_append_only_and_invalidates_ai(self):
        cid=self.db.create('sample','username',['fusion'])
        self.db.add(cid,'fusion',relationship('https://github.com/sample','https://example.com/','https://api.github.com/users/sample',1))
        eid=self.db.evidence(cid)[0]['id'];before=self.db.evidence(cid,True)
        nid=self.db.save_narrative(cid,'test','','p','draft');self.db.review(nid)
        self.db.review_evidence(cid,eid,'accepted','Public link observed')
        self.db.review_evidence(cid,eid,'rejected','Ownership not established')
        self.assertEqual(before,self.db.evidence(cid,True));self.assertEqual(len(self.db.reviews(cid)),2)
        self.assertEqual(self.db.graph(cid)[0]['review']['decision'],'rejected')
        self.assertIsNone(self.db.narrative(cid,True))
    def test_cross_case_review_rejected(self):
        a=self.db.create('a','username',['fusion']);b=self.db.create('b','username',['fusion'])
        self.db.add(a,'fusion',relationship('a','b','https://example.com',1))
        with self.assertRaises(AppError):self.db.review_evidence(b,self.db.evidence(a)[0]['id'],'accepted','note')
    def test_migrate_v1_preserves_case_and_backup(self):
        p=Path(self.tmp.name);cfg=Config(p/'old',p/'old-config')
        with sqlite3.connect(cfg.data/'osintcli.db') as c:
            c.executescript(SCHEMA)
            c.execute('INSERT INTO cases VALUES(?,?,?,?,?,?)',('oldcase','sample','username','2026-01-01','DONE','["username"]'))
        db=Store(cfg)
        self.assertEqual(db.case('oldcase')['target'],'sample');self.assertTrue(Path(str(db.path)+'.v1.backup').is_file())
    def test_user_scanner_adapter_errors_and_links(self):
        rows=list(parse_user_scanner(json.dumps([{'status':'Found','url':'https://github.com/sample','extra':{'website':'https://example.com/'}},{'status':'Error','reason':'blocked'}])))
        self.assertEqual([r['entity_type'] for r in rows],['profile','relationship','source_error'])
    def test_pdf_newline_heavy_profile(self):
        from osintcli.adapters import item
        cid=self.db.create('sample','username',['fusion'])
        self.db.add(cid,'fusion',item('profile',{'bio':'x\n'*800},'https://example.com'))
        files=export(self.db,cid,['pdf'],Path(self.tmp.name)/'out')
        self.assertGreater(files[0].stat().st_size,1000)

    def test_docx_and_json_same_review(self):
        from docx import Document
        cid=self.db.create('sample','username',['fusion'])
        self.db.add(cid,'fusion',relationship('https://github.com/sample','https://example.com/','https://api.github.com/users/sample',1))
        eid=self.db.evidence(cid)[0]['id'];self.db.review_evidence(cid,eid,'accepted','confirmed link text')
        files=export(self.db,cid,['docx','json'],Path(self.tmp.name)/'out')
        d=Document(files[0]);text='\n'.join(p.text for p in d.paragraphs)
        self.assertIn('confirmed link text',text)
        data=json.loads(files[1].read_text());self.assertEqual(data['relationships'][0]['review']['decision'],'accepted')
