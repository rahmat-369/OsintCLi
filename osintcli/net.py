"""Bounded direct HTTP with IP pinning, or explicit trusted-source proxy transport."""
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urljoin
from urllib.request import ProxyHandler, HTTPSHandler, HTTPRedirectHandler, Request, build_opener, getproxies
from urllib.error import HTTPError, URLError
from .core import AppError

@dataclass
class Response:
    status: int
    headers: dict
    body: bytes
    url: str
    def json(self):
        ct=self.headers.get("content-type","").lower()
        if "json" not in ct: raise AppError("CONTENT_TYPE", "Sumber tidak mengembalikan JSON.")
        try:return json.loads(self.body)
        except (ValueError,UnicodeError):raise AppError("JSON", "JSON sumber tidak valid.")

def public_address(host,port):
    try: addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    except OSError: raise AppError("DNS", "Resolusi DNS sumber gagal.")
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global or ipaddress.ip_address(a[4][0]).is_multicast or ipaddress.ip_address(a[4][0]).is_reserved for a in addresses):
        raise AppError("SSRF", "Alamat lokal/internal sumber ditolak.")
    return addresses[0][4][0]

def validate_url(url):
    try:
        p=urlsplit(url)
        if p.scheme not in ("https","http") or not p.hostname or p.username or p.password or p.port not in (None,80,443) or p.fragment or any(ord(c)<32 for c in url):
            raise ValueError()
        return p
    except ValueError:raise AppError("URL", "URL sumber harus HTTP(S) publik pada port standar.")

class Client:
    def __init__(self,config,stop=None):
        self.config=config; self.stop=stop or threading.Event()
        self.lock=threading.Lock(); self.last={};self.failures={}

    def _wait(self,seconds):
        if self.stop.wait(seconds):raise AppError("CANCELLED","Dibatalkan.")

    def _proxy_request(self,url,method,body,headers,max_bytes,timeout):
        p=validate_url(url)
        allowed={h.strip() for h in self.config["proxy_allowed_hosts"].split(",")}
        # Custom AI hostname is explicitly selected by the owner, never source-discovered.
        allowed.add(urlsplit(self.config["endpoint"]).hostname)
        if p.scheme!="https" or p.hostname not in allowed:
            raise AppError("PROXY_SCOPE","Mode proxy hanya HTTPS pada hostname yang disetujui. Tambahkan hostname publik lewat proxy_allowed_hosts bila memang diizinkan.")
        try:
            ipaddress.ip_address(p.hostname)
        except ValueError:pass
        else:raise AppError("SSRF","IP literal ditolak pada mode proxy.")
        if p.hostname=="localhost" or p.hostname.endswith((".local",".internal",".localhost",".lan")):
            raise AppError("SSRF","Host internal ditolak pada mode proxy.")
        proxy=getproxies().get("https")
        if not proxy:raise AppError("PROXY_CONFIG","Mode proxy memerlukan HTTPS_PROXY/https_proxy pada environment.")
        parsed=urlsplit(proxy)
        if parsed.scheme not in ("http","https") or not parsed.hostname:
            raise AppError("PROXY_CONFIG","HTTPS_PROXY harus URL proxy HTTP(S) yang valid.")
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        opener=build_opener(ProxyHandler({"https":proxy}),HTTPSHandler(context=ssl.create_default_context()),NoRedirect())
        request=Request(url,data=body,headers=headers,method=method)
        try:
            try:response=opener.open(request,timeout=timeout)
            except HTTPError as error:response=error
            with response:
                data=response.read(max_bytes+1)
                return Response(response.code,{k.lower():v for k,v in response.headers.items()},data,url)
        except URLError as error:
            raise AppError("PROXY_NETWORK","Koneksi proxy gagal (jaringan/TLS/timeout); alamat dan kredensial proxy tidak dicetak.") from error

    def request(self,url,method="GET",body=None,headers=None,redirects=3,max_bytes=2_000_000,timeout=None,retries=None):
        original=urlsplit(url).hostname
        retries=self.config["retries"] if retries is None else retries
        for hop in range(redirects+1):
            p=validate_url(url)
            if self.stop.is_set():raise AppError("CANCELLED","Dibatalkan.")
            with self.lock:
                failures,at=self.failures.get(p.hostname,(0,0))
                if failures>=3 and time.monotonic()-at<30:raise AppError("CIRCUIT_OPEN","Sumber sementara dinonaktifkan setelah kegagalan berulang.")
            for attempt in range(retries+1):
                try:
                    with self.lock:
                        wait=max(0,self.last.get(p.hostname,0)+self.config["request_interval"]-time.monotonic())
                        self.last[p.hostname]=time.monotonic()+wait
                    self._wait(wait)
                    h={"User-Agent":"OsintCLI/1.0 (+https://github.com/rahmat-369/OsintCLI)","Accept":"application/json, text/plain, */*","Accept-Encoding":"identity"}
                    if headers and p.hostname==original:h.update(headers)
                    if self.config["http_transport"]=="proxy":
                        result=self._proxy_request(url,method,body,h,max_bytes,timeout or self.config["timeout_seconds"])
                        data=result.body
                    else:
                        ip=public_address(p.hostname,p.port or (443 if p.scheme=="https" else 80))
                        port=p.port or (443 if p.scheme=="https" else 80)
                        conn=http.client.HTTPConnection(p.hostname,port,timeout=timeout or self.config["timeout_seconds"])
                        sock=socket.create_connection((ip,port),timeout=timeout or self.config["timeout_seconds"])
                        try:
                            conn.sock=ssl.create_default_context().wrap_socket(sock,server_hostname=p.hostname) if p.scheme=="https" else sock
                            conn.request(method,(p.path or "/")+("?"+p.query if p.query else ""),body=body,headers=h)
                            response=conn.getresponse()
                            data=response.read(max_bytes+1)
                            result=Response(response.status,{k.lower():v for k,v in response.getheaders()},data,url)
                        finally:
                            conn.close();sock.close()
                    if len(data)>max_bytes:raise AppError("TOO_LARGE","Respons melebihi batas ukuran.")
                    if result.status==429 or result.status>=500:
                        raise AppError("HTTP_"+str(result.status),"Sumber sibuk/rate-limited.")
                    with self.lock:self.failures[p.hostname]=(0,time.monotonic())
                    break
                except (OSError,ssl.SSLError,http.client.HTTPException) as e:
                    error=AppError("NETWORK","Koneksi sumber gagal (DNS/TLS/timeout).")
                    if attempt==retries:
                        with self.lock:self.failures[p.hostname]=(failures+1,time.monotonic())
                        raise error from e
                    self._wait(0.5*2**attempt)
                except AppError as e:
                    if not (e.code in ("DNS","PROXY_NETWORK") or e.code.startswith("HTTP_")) or attempt==retries:
                        if e.code!="CANCELLED":
                            with self.lock:self.failures[p.hostname]=(failures+1,time.monotonic())
                        raise
                    self._wait(0.5*2**attempt)
            if result.status in (301,302,303,307,308):
                if hop==redirects:raise AppError("REDIRECT","Redirect tidak diizinkan/melebihi batas.")
                location=result.headers.get("location")
                if not location:raise AppError("REDIRECT","Redirect tanpa tujuan.")
                next_url=urljoin(url,location)
                if p.scheme=="https" and urlsplit(next_url).scheme!="https":raise AppError("REDIRECT","Downgrade HTTPS ditolak.")
                # Never forward request bodies or authentication on redirects.
                if body is not None:raise AppError("REDIRECT","Redirect POST ditolak.")
                url=next_url;continue
            return result
        raise AppError("REDIRECT","Redirect gagal.")

    def json(self,url,**kwargs):
        r=self.request(url,**kwargs)
        if r.status!=200:raise AppError("HTTP_"+str(r.status),f"Sumber HTTP {r.status}.")
        return r.json()
