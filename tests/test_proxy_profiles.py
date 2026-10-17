import json
import socket
import tempfile
import threading
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit
from osintcli.core import Config,AppError
from osintcli.engine import Context
from osintcli.net import Client,Response
from osintcli.adapters import username,tls

class ProxyTransport(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.config=Config(root/'data',root/'config');self.config.set('http_transport','proxy')
        self.client=Client(self.config)
    def tearDown(self):self.temp.cleanup()
    def request(self,url='https://dns.google/resolve'):
        return self.client.request(url,retries=0)
    def response(self,body=b'{}',status=200,headers=None):
        r=Mock();r.code=status;r.headers=headers or {'Content-Type':'application/json'};r.read.return_value=body
        r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False);return r
    def opener(self,response):
        opener=Mock();opener.open.return_value=response;return opener
    def test_no_environment_proxy_is_clear_error(self):
        with patch('osintcli.net.getproxies',return_value={}),self.assertRaises(AppError) as e:self.request()
        self.assertEqual(e.exception.code,'PROXY_CONFIG')
    def test_unapproved_arbitrary_host_denied_before_network(self):
        with patch('osintcli.net.build_opener') as build,self.assertRaises(AppError) as e:self.request('https://unapproved.example.com/')
        self.assertEqual(e.exception.code,'PROXY_SCOPE');build.assert_not_called()
    def test_allowlist_rejects_literals_and_wildcards(self):
        for value in ['127.0.0.1','*.example.com','localhost','internal.local','example.com:443']:
            with self.subTest(value=value),self.assertRaises(AppError):self.config.set('proxy_allowed_hosts',value)
    def test_https_only(self):
        with self.assertRaises(AppError) as e:self.request('http://dns.google/resolve')
        self.assertEqual(e.exception.code,'PROXY_SCOPE')
    def test_valid_json_and_normal_pacing_path(self):
        opener=self.opener(self.response(b'{"Status":0}'))
        with patch('osintcli.net.getproxies',return_value={'https':'http://127.0.0.1:8888'}),patch('osintcli.net.build_opener',return_value=opener):
            self.assertEqual(self.request().json(),{'Status':0})
            self.assertEqual(opener.open.call_args.kwargs['timeout'],15)
    def test_redirect_revalidates_host(self):
        opener=self.opener(self.response(b'',302,{'Location':'https://evil.example.com/'}))
        with patch('osintcli.net.getproxies',return_value={'https':'http://127.0.0.1:8888'}),patch('osintcli.net.build_opener',return_value=opener),self.assertRaises(AppError) as e:self.request()
        self.assertEqual(e.exception.code,'PROXY_SCOPE');self.assertEqual(opener.open.call_count,1)
    def test_auth_stripped_on_approved_cross_host_redirect(self):
        opener=Mock();opener.open.side_effect=[self.response(b'',302,{'Location':'https://rdap.org/'}),self.response()]
        self.client._wait=lambda _:None
        with patch('osintcli.net.getproxies',return_value={'https':'http://127.0.0.1:8888'}),patch('osintcli.net.build_opener',return_value=opener):
            self.client.request('https://dns.google/',headers={'Authorization':'private'},retries=0)
        first,second=[c.args[0] for c in opener.open.call_args_list]
        self.assertEqual(first.get_header('Authorization'),'private');self.assertIsNone(second.get_header('Authorization'))
    def test_oversized_payload_rejected(self):
        opener=self.opener(self.response(b'123456'))
        with patch('osintcli.net.getproxies',return_value={'https':'http://127.0.0.1:8888'}),patch('osintcli.net.build_opener',return_value=opener),self.assertRaises(AppError) as e:self.client.request('https://dns.google/',max_bytes=5,retries=0)
        self.assertEqual(e.exception.code,'TOO_LARGE')
    def test_failure_does_not_print_proxy_secrets(self):
        opener=Mock();opener.open.side_effect=URLError('http://user:VERY_SECRET@proxy')
        with patch('osintcli.net.getproxies',return_value={'https':'http://user:VERY_SECRET@localhost:8888'}),patch('osintcli.net.build_opener',return_value=opener),self.assertRaises(AppError) as e:self.request()
        self.assertEqual(e.exception.code,'PROXY_NETWORK');self.assertNotIn('VERY_SECRET',str(e.exception))
    def test_tls_cannot_report_proxy_cert_as_origin_cert(self):
        ctx=Context('example.com','domain',self.config,self.client,threading.Event())
        with patch('osintcli.adapters.public_address') as resolver,self.assertRaises(AppError) as e:list(tls(ctx))
        self.assertEqual(e.exception.code,'DIRECT_REQUIRED');resolver.assert_not_called()
    def test_direct_mode_does_not_inherit_proxy(self):
        self.config.set('http_transport','direct')
        with patch('osintcli.net.public_address',side_effect=AppError('DNS','test')),patch.object(self.client,'_proxy_request') as proxy,self.assertRaises(AppError):self.request()
        proxy.assert_not_called()

class ProfileClassification(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.config=Config(root/'data',root/'config')
    def tearDown(self):self.temp.cleanup()
    def run_profile(self,response):
        client=Mock();client.request.side_effect=[response,Response(404,{},b'','https://gitlab.com/octocat'),Response(403,{},b'','https://www.reddit.com/user/octocat')]
        rows=list(username(Context('octocat','username',self.config,client,threading.Event())))
        return rows,client
    def test_github_matches_login_id_and_url(self):
        data={'login':'octocat','id':583231,'html_url':'https://github.com/octocat','type':'User'}
        rows,client=self.run_profile(Response(200,{'content-type':'application/json'},json.dumps(data).encode(),'https://api.github.com/users/octocat'))
        self.assertEqual(rows[0]['status'],'CANDIDATE');self.assertEqual(rows[0]['raw']['id'],583231)
        self.assertEqual(client.request.call_args_list[0].args[0],'https://api.github.com/users/octocat')
    def test_soft_200_wrong_user_not_candidate(self):
        data={'login':'wrong','id':12,'html_url':'https://github.com/wrong'}
        rows,_=self.run_profile(Response(200,{'content-type':'application/json'},json.dumps(data).encode(),'x'))
        self.assertEqual(rows[0]['status'],'FAILED_SOURCE');self.assertEqual(rows[0]['error_code'],'PROFILE_SCHEMA')
    def test_nonexistent_github_not_candidate(self):
        rows,_=self.run_profile(Response(404,{'content-type':'application/json'},b'{"message":"Not Found"}','x'))
        self.assertEqual(rows[0]['entity_type'],'profile_check');self.assertEqual(rows[0]['status'],'UNVERIFIED')
    def test_html_200_is_not_api_success(self):
        rows,_=self.run_profile(Response(200,{'content-type':'text/html'},b'<h1>Site Unavailable</h1>','x'))
        self.assertEqual(rows[0]['status'],'FAILED_SOURCE')
    def test_block_page_on_other_site_not_candidate(self):
        client=Mock();client.request.side_effect=[Response(404,{},b'','x'),Response(200,{},b'<h1>Site Unavailable</h1>','x'),Response(403,{},b'','x')]
        rows=list(username(Context('octocat','username',self.config,client,threading.Event())))
        self.assertEqual(rows[1]['error_code'],'CONTENT_TYPE')

class ExtraContracts(unittest.TestCase):
    def test_missing_tool_interpreter_has_actionable_error(self):
        from osintcli.external import run_process
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"broken-tool"
            path.write_text("#!/no/such/python\n");path.chmod(0o700)
            with self.assertRaises(AppError) as e:run_process([str(path)],root,threading.Event())
            self.assertEqual(e.exception.code,"TOOL_LAUNCH")
    def test_reddit_structured_identifier_is_required(self):
        with tempfile.TemporaryDirectory() as root:
            config=Config(Path(root)/'data',Path(root)/'config')
            client=Mock();client.request.side_effect=[Response(404,{},b'','x'),Response(200,{'content-type':'application/json'},b'[]','x'),Response(200,{'content-type':'application/json'},b'{"kind":"t2","data":{"name":"octocat","id":"abc"}}','x')]
            rows=list(username(Context('octocat','username',config,client,threading.Event())))
            self.assertEqual(rows[1]['entity_type'],'profile_check')
            self.assertEqual(rows[2]['status'],'CANDIDATE');self.assertEqual(rows[2]['raw']['id'],'abc')
    def test_github_schema_missing_id_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            config=Config(Path(root)/'data',Path(root)/'config')
            client=Mock();client.request.side_effect=[Response(200,{'content-type':'application/json'},b'{"login":"octocat","html_url":"https://github.com/octocat"}','x'),Response(200,{'content-type':'application/json'},b'[]','x'),Response(403,{},b'','x')]
            rows=list(username(Context('octocat','username',config,client,threading.Event())))
            self.assertEqual(rows[0]['error_code'],'PROFILE_SCHEMA')

if __name__=='__main__':unittest.main()
