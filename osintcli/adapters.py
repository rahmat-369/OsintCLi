"""Public-source adapters. Every emitted item retains its own source and reason."""
import hashlib
import json
from pathlib import Path
import shutil
import socket
import ssl
from urllib.parse import urlencode, quote, urlsplit
import zipfile
import xml.etree.ElementTree as ET
from .core import AppError, canonical
from .net import public_address


def item(kind,value,source,title=None,status="VERIFIED",raw=None,reason=None):
    return dict(entity_type=kind,value=value,source_url=source if source.startswith("http") else "",source_name=source,title=title or kind,status=status,raw=raw if raw is not None else value,verification_reason=reason or "Nilai diamati langsung pada respons sumber; bukan validasi kepemilikan/identitas.",confidence_basis="Observasi deterministik pada waktu pengambilan.")

def failed(source,error):
    return dict(entity_type="source_error",value=str(error),title="Sumber tidak tersedia",source_url=source if source.startswith("http") else "",source_name=source,status="FAILED_SOURCE",error_code=getattr(error,"code","SOURCE"),verification_reason="Tidak dapat memperoleh bukti; bukan bukti ketiadaan.",confidence_basis="Kegagalan akses/parsing sumber.")

def dns_query(ctx,name,typ):
    url="https://dns.google/resolve?"+urlencode({"name":name,"type":typ})
    data=ctx.client.json(url)
    if not isinstance(data,dict) or not isinstance(data.get("Status"),int):raise AppError("SCHEMA","Skema DNS tidak valid.")
    if data["Status"] not in (0,3):raise AppError("DNS_STATUS",f"Resolver mengembalikan status {data['Status']}.")
    answers=data.get("Answer",[])
    if not isinstance(answers,list):raise AppError("SCHEMA","Answer DNS tidak valid.")
    return url,data,answers

def dns(ctx):
    host=ctx.value.split("@")[-1]
    types=[("A",host),("AAAA",host),("MX",host),("NS",host),("TXT",host)]
    if ctx.kind=="email": types=[("MX",host),("TXT",host),("TXT","_dmarc."+host)]
    for typ,name in types:
        try:
            url,data,answers=dns_query(ctx,name,typ)
            if not answers:yield item("dns_status",f"{typ} {name}: resolver status {data['Status']}, no answers",url,raw=data,reason="Resolver tidak memberi jawaban untuk pertanyaan ini; tidak membuktikan target tidak ada.")
            for a in answers[:100]:
                yield item("dns",f"{a.get('name',name)} {a.get('type',typ)} {a.get('data','')}",url,title=f"DNS {typ}",raw=a)
        except AppError as e:
            if e.code=="CANCELLED":raise
            yield failed("https://dns.google/resolve",e)

def rdap(ctx):
    url="https://rdap.org/"+("ip/" if ctx.kind=="ip" else "domain/")+quote(ctx.value,safe="")
    r=ctx.client.request(url);data=r.json()
    if r.status!=200:raise AppError("HTTP_"+str(r.status),"RDAP tidak tersedia.")
    if not isinstance(data,dict) or "objectClassName" not in data:raise AppError("SCHEMA","Skema RDAP tidak valid.")
    for key in ["objectClassName","handle","ldhName","name","type","country","startAddress","endAddress","status","events","nameservers","port43"]:
        if key in data:
            yield item("rdap",data[key],r.url,"RDAP / "+key,raw={key:data[key]},reason="Data registrasi publik RDAP; country adalah administrasi registrasi, bukan lokasi orang/perangkat.")
    # Do not pull contact vCards or create private-person identity links.

def ct(ctx):
    url="https://crt.sh/?"+urlencode({"q":"%."+ctx.value,"output":"json"})
    data=ctx.client.json(url)
    if not isinstance(data,list):raise AppError("SCHEMA","Skema CT tidak valid.")
    seen=set()
    for row in data:
        if not isinstance(row,dict):continue
        for name in str(row.get("name_value","")).splitlines():
            name=name.lower().rstrip(".")
            if (name==ctx.value or name.endswith("."+ctx.value)) and name not in seen:
                seen.add(name)
                yield item("certificate_name",name,url,status="CANDIDATE",raw={k:row.get(k) for k in ("id","name_value","not_before","not_after","issuer_name")},reason="Nama tercatat pada certificate transparency; mungkin historis, belum dibuktikan aktif.")
                if len(seen)>=100:
                    yield item("collection_limit","CT dibatasi 100 nama unik.",url,status="UNVERIFIED");return
    if not seen:yield item("source_observation","Tidak ada entri CT dalam respons.",url,status="UNVERIFIED")

def web(ctx):
    for path in ("/","/robots.txt","/sitemap.xml"):
        url="https://"+ctx.value+path
        try:
            r=ctx.client.request(url,max_bytes=1_000_000)
            useful={k:v for k,v in r.headers.items() if k in {"server","content-type","content-security-policy","strict-transport-security","x-frame-options","last-modified"}}
            yield item("http",{"status":r.status,"headers":useful,"bytes":len(r.body)},r.url,title="HTTP "+path,raw={"status":r.status,"headers":useful},status="VERIFIED" if r.status==200 else "UNVERIFIED")
            if path!="/" and r.status==200:
                yield item("public_document",r.body.decode("utf-8",errors="replace")[:6000],r.url,title=path,reason="Cuplikan maksimal 6000 karakter; XML/HTML tidak dieksekusi.")
        except AppError as e:
            if e.code=="CANCELLED":raise
            yield failed(url,e)

def tls(ctx):
    ip=public_address(ctx.value,443)
    try:
        with socket.create_connection((ip,443),timeout=ctx.config["timeout_seconds"]) as sock:
            with ssl.create_default_context().wrap_socket(sock,server_hostname=ctx.value) as secure:
                cert=secure.getpeercert()
                yield item("tls",{"protocol":secure.version(),"issuer":cert.get("issuer"),"notAfter":cert.get("notAfter"),"subjectAltName":cert.get("subjectAltName")},"https://"+ctx.value,title="TLS certificate",reason="TLS handshake tervalidasi saat pengambilan; bukan audit keamanan menyeluruh.")
    except OSError as e:raise AppError("TLS","Handshake TLS gagal.") from e

def asn(ctx):
    import ipaddress
    ip=ipaddress.ip_address(ctx.value)
    name=(".".join(reversed(str(ip).split(".")))+".origin.asn.cymru.com" if ip.version==4 else ".".join(reversed(ip.exploded.replace(":","")))+".origin6.asn.cymru.com")
    url,data,answers=dns_query(ctx,name,"TXT")
    for a in answers:yield item("asn",a.get("data",""),url,title="Team Cymru ASN",raw=a,reason="Pemetaan routing publik; country bukan geolokasi presisi.")
    if not answers:yield item("source_observation","ASN tidak ditemukan pada respons resolver.",url,status="UNVERIFIED",raw=data)

def email(ctx):
    yield item("email_syntax",ctx.value,"local:syntax",reason="Sintaks sederhana lolos; tidak menguji keberadaan kotak surat.")
    yield from dns(ctx)

PROFILE_SITES=[("GitHub","https://github.com/{}"),("GitLab","https://gitlab.com/{}"),("Reddit","https://www.reddit.com/user/{}/")]
def username(ctx):
    for name,template in PROFILE_SITES:
        url=template.format(quote(ctx.value,safe=""))
        try:
            r=ctx.client.request(url,max_bytes=2_000_000,redirects=0)
            if r.status==200:
                yield item("profile",url,url,title=name,status="CANDIDATE",reason="HTTP 200 hanya kandidat; halaman umum/soft-404 mungkin. Periksa manual. Nama sama bukan identitas sama.")
            elif r.status==404:
                yield item("profile_check","HTTP 404 pada waktu pemeriksaan",url,title=name,status="UNVERIFIED",reason="Tidak tersedia pada URL ini saat dicek; bukan bukti akun tidak pernah ada.")
            else:yield failed(url,AppError("HTTP_"+str(r.status),f"Respons {r.status}; hasil tidak pasti."))
        except AppError as e:
            if e.code=="CANCELLED":raise
            yield failed(url,e)

def metadata(ctx):
    p=Path(ctx.value)
    if p.stat().st_size>ctx.config["max_file_mb"]*1024*1024:raise AppError("FILE_SIZE","File melampaui batas metadata.")
    content=p.read_bytes()
    yield item("file",{"name":p.name,"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest()},"local:selected-file",reason="File pilihan pengguna; tidak dikirim ke sumber daring.")
    suffix=p.suffix.lower()
    if suffix in {".jpg",".jpeg",".png",".webp",".tif",".tiff",".gif",".bmp"}:
        try:
            from PIL import Image, ExifTags
            Image.MAX_IMAGE_PIXELS=30_000_000
            with Image.open(p) as im:
                yield item("image_metadata",{"format":im.format,"width":im.width,"height":im.height,"mode":im.mode},"local:Pillow")
                for k,v in im.getexif().items():
                    if isinstance(v,bytes):v=f"binary metadata ({len(v)} bytes)"
                    yield item("exif",str(v)[:4000],"local:Pillow",title=ExifTags.TAGS.get(k,str(k)),reason="Metadata dapat berisi GPS/identitas dan dapat dimodifikasi; periksa sumber asli.")
        except ImportError:yield failed("local:Pillow",AppError("DEPENDENCY","Pillow belum terpasang; install profil reports."))
    elif suffix==".pdf":
        try:
            from pypdf import PdfReader
            doc=PdfReader(p)
            if doc.is_encrypted:raise AppError("ENCRYPTED","PDF terenkripsi; dekripsi tidak dicoba.")
            yield item("document_metadata",dict(doc.metadata or {}),"local:pypdf")
            yield item("document_metadata",len(doc.pages),"local:pypdf",title="Page count")
        except ImportError:yield failed("local:pypdf",AppError("DEPENDENCY","pypdf belum terpasang."))
    elif suffix in {".docx",".xlsx",".pptx"}:
        with zipfile.ZipFile(p) as z:
            for name in ["docProps/core.xml","docProps/app.xml"]:
                if name not in z.namelist():continue
                if z.getinfo(name).file_size>1_000_000:raise AppError("FILE_SIZE","XML metadata terlalu besar.")
                content=z.read(name)
                if b"<!DOCTYPE" in content or b"<!ENTITY" in content:raise AppError("XML","Entity XML ditolak.")
                root=ET.fromstring(content)
                yield item("document_metadata",{el.tag.split("}")[-1]:el.text for el in root},"local:OOXML",title=name)
    else:yield item("metadata_note","Format ini hanya hash/ukuran. Pilih adapter exiftool untuk format tambahan.","local",status="UNVERIFIED")

ADAPTERS={"dns":dns,"rdap":rdap,"ct":ct,"web":web,"tls":tls,"asn":asn,"email":email,"username":username,"metadata":metadata}
DEFAULT_SCOPE={"domain":["dns","rdap","ct"],"ip":["rdap","asn"],"email":["email"],"username":["username"],"metadata":["metadata"]}
ALLOWED={"domain":{"dns","rdap","ct","web","tls"},"ip":{"rdap","asn"},"email":{"email","dns"},"username":{"username","sherlock","maigret"},"metadata":{"metadata","exiftool"}}
