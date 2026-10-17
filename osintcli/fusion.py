"""Bounded public-profile collection and explainable link traversal.

TikTok userInfo / Instagram public metadata extraction adapted from User Scanner
(Kaif, MIT), commit b85d470b48f7fb9d5ccff85080a882bf70049ed7.
No signup/recovery endpoints, browser impersonation or session cookies.
"""
from collections import deque
from html.parser import HTMLParser
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlunsplit, urljoin, quote, unquote, parse_qs
from .core import AppError, clean, domain, target
from .adapters import item, failed
from .net import validate_url

MODES = {"quick": (0, ("github", "gitlab")),
         "standard": (1, ("github", "gitlab", "instagram", "tiktok", "reddit")),
         "deep": (2, ("github", "gitlab", "instagram", "tiktok", "reddit"))}
HOSTS = {"github.com":"github", "gitlab.com":"gitlab", "instagram.com":"instagram",
         "tiktok.com":"tiktok", "reddit.com":"reddit"}
URLS = {"github":"https://github.com/{}", "gitlab":"https://gitlab.com/{}",
        "instagram":"https://www.instagram.com/{}/", "tiktok":"https://www.tiktok.com/@{}",
        "reddit":"https://www.reddit.com/user/{}/"}
URL_RE = re.compile(r'https?://[^\s<>"\x00-\x20]+')
EMAIL_RE = re.compile(r'(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])')


def normalize_url(value):
    value = clean(value).strip()
    if any(c.isspace() for c in value):raise AppError("URL","Whitespace di URL ditolak.")
    if len(value)>2048: raise AppError("URL", "URL terlalu panjang.")
    p = validate_url(value)
    host = p.hostname.lower()
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global or ip.is_multicast: raise AppError("SSRF", "Alamat internal ditolak.")
    except ValueError:
        domain(host)
    # Discovered URLs cannot carry queries (tracking, tokens or actions).
    if p.query: raise AppError("URL_QUERY", "Gunakan tautan publik tanpa query; query tidak diikuti otomatis.")
    return urlunsplit((p.scheme,host,p.path or "/","",""))


def profile_key(url):
    p=urlsplit(url); host=(p.hostname or "").removeprefix("www.")
    site=HOSTS.get(host); parts=[unquote(x) for x in p.path.split("/") if x]
    if not site:return None
    if site=="reddit":
        if len(parts)!=2 or parts[0] not in ("user","u"):return None
        handle=parts[1]
    else:
        if len(parts)!=1:return None
        handle=parts[0].removeprefix("@") if site=="tiktok" else parts[0]
    if handle.lower() in {"about","login","signup","explore","p","reel","accounts","settings","privacy","terms","features","pricing","customer-stories","enterprise","security","solutions","resources","readme","topics","collections","trending","marketplace","sponsors","orgs","organizations","join","contact","site","apps","events"}:return None
    try:handle=target(handle,"username")[1]
    except AppError:return None
    return site,handle


def canonical_link(url):
    url=normalize_url(url);key=profile_key(url)
    return URLS[key[0]].format(key[1].lower()) if key else url


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.meta={};self.links=[];self.identity_links=[];self.title="";self.in_title=False
        self.scripts=[];self.script=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=="meta":self.meta[a.get("property",a.get("name",""))]=a.get("content","")
        if tag=="a" and a.get("href"):
            self.links.append(a["href"])
            if "me" in a.get("rel", "").split():self.identity_links.append(a["href"])
        if tag=="title":self.in_title=not bool(self.title)
        if tag=="script" and a.get("type") in ("application/json","application/ld+json"):self.script=""
    def handle_data(self,data):
        if self.in_title:self.title+=data
        if self.script is not None:self.script+=data
    def handle_endtag(self,tag):
        if tag=="title":self.in_title=False
        if tag=="script" and self.script is not None:self.scripts.append(self.script);self.script=None


def nested_user(data):
    pending=[data];visited=0
    while pending and visited<10000:
        x=pending.pop();visited+=1
        if isinstance(x,dict):
            if isinstance(x.get("xig_user_by_username"),dict):return x["xig_user_by_username"]
            pending.extend(x.values())
        elif isinstance(x,list):pending.extend(x)
    return None


def tiktok_info(text):
    # raw_decode correctly handles escaped quotes and braces inside bios.
    for match in re.finditer(r'"userInfo"\s*:\s*',text):
        try:
            data,_=json.JSONDecoder().raw_decode(text[match.end():])
            if isinstance(data,dict) and data.get("uniqueId"):return data
        except ValueError:continue
    return None


def fetch_profile(ctx,site,handle):
    public=URLS[site].format(handle);source=public
    if site=="github":source="https://api.github.com/users/"+quote(handle,safe="")
    elif site=="gitlab":source="https://gitlab.com/api/v4/users?username="+quote(handle,safe="")
    elif site=="reddit":source=public+"about.json"
    elif site=="tiktok":source="https://www.tiktok.com/embed/@"+quote(handle,safe="")
    r=ctx.client.request(source,max_bytes=2_000_000)
    if r.status==404 and site in ("github","gitlab","reddit"):
        return None,source,"Sumber mengembalikan 404 pada waktu pemeriksaan."
    if r.status!=200:raise AppError("HTTP_"+str(r.status),"Profil publik tidak dapat dibaca; bukan bukti akun tidak ada.")
    links=[]
    if site=="github":
        d=r.json()
        if not isinstance(d,dict) or str(d.get("login","")).lower()!=handle.lower() or not d.get("id"):
            raise AppError("PROFILE_SCHEMA","Respons GitHub tidak cocok dengan username.")
        info={k:d[k] for k in ("login","id","name","bio","blog","email","company","location","followers","following","public_repos","created_at","updated_at","avatar_url") if d.get(k) is not None}
        if d.get("blog"):
            blog=str(d["blog"]);links.append(blog if "://" in blog else "https://"+blog)
        # Social accounts are a separate public endpoint; errors remain visible.
    elif site=="gitlab":
        d=r.json()
        if not isinstance(d,list):raise AppError("PROFILE_SCHEMA","Skema GitLab berubah.")
        d=next((x for x in d if isinstance(x,dict) and str(x.get("username","")).lower()==handle.lower()),None)
        if not d:return None,source,"API tidak mengembalikan username yang cocok."
        if not d.get("id"):raise AppError("PROFILE_SCHEMA","ID GitLab tidak ditemukan.")
        info={k:d[k] for k in ("id","username","name","bio","web_url","avatar_url","website_url") if d.get(k) is not None}
        if d.get("website_url"):links.append(d["website_url"])
    elif site=="reddit":
        d=r.json();d=d.get("data",{}) if isinstance(d,dict) else {}
        if str(d.get("name","")).lower()!=handle.lower() or not d.get("id"):raise AppError("PROFILE_SCHEMA","Respons Reddit tidak cocok.")
        info={k:d[k] for k in ("id","name","created_utc","link_karma","comment_karma") if k in d}
        sub=d.get("subreddit") or {};info["bio"]=sub.get("public_description","")
    elif site=="tiktok":
        d=tiktok_info(r.body.decode("utf-8",errors="replace"))
        if not d or str(d.get("uniqueId","")).lower()!=handle.lower():raise AppError("PROFILE_SCHEMA","TikTok tidak memberi metadata yang cocok; mungkin privat/diblokir.")
        info={k:d[k] for k in ("id","uniqueId","nickname","signature","followerCount","followingCount","heartCount","verified","privateAccount","avatarThumbUrl") if k in d}
        info["bio"]=d.get("signature","")
    else:
        page=Page();page.feed(r.body.decode("utf-8",errors="replace"))
        title=page.meta.get("og:title","")
        if f"(@{handle.lower()})" not in title.lower():raise AppError("PROFILE_SCHEMA","Instagram tidak memberi metadata profil; login/challenge tidak dianggap ditemukan.")
        info={"username":handle,"name":title.split("(@")[0].strip(),"description":page.meta.get("og:description","")}
        for script in page.scripts:
            try:d=nested_user(json.loads(script))
            except (ValueError,RecursionError):continue
            if d and str(d.get("username","")).lower()==handle.lower():
                info.update({k:d[k] for k in ("pk","full_name","biography","is_verified","is_private") if k in d})
                info["bio"]=d.get("biography","")
                for link in (d.get("bio_links") or []):
                    if isinstance(link,dict) and isinstance(link.get("url"),str):links.append(link["url"])
                if d.get("external_url"):links.append(d["external_url"])
                break
    for key in ("bio","description"):
        links.extend(m.group().rstrip(".,);]") for m in URL_RE.finditer(str(info.get(key,""))))
    info={k:clean(v)[:4000] if isinstance(v,str) else v for k,v in info.items()}
    return {"site":site,"username":handle,"profile_url":public,"fields":info,"links":links[:30]},source,None


def public_page(ctx,url):
    r=ctx.client.request(url,max_bytes=1_000_000)
    if r.status!=200:raise AppError("HTTP_"+str(r.status),"Halaman publik tidak dapat dibaca.")
    ct=r.headers.get("content-type","").lower()
    if "html" not in ct:raise AppError("CONTENT_TYPE","Penelusuran tautan hanya membaca HTML publik.")
    page=Page();page.feed(r.body.decode("utf-8",errors="replace"))
    if any(s in page.title.lower() for s in ("just a moment","access denied","captcha","verify you are human")):
        raise AppError("CHALLENGE","Sumber menampilkan challenge; tidak dihitung sebagai profil.")
    links=[]
    hub=(urlsplit(r.url).hostname or "").removeprefix("www.") in ("linktr.ee","bio.link","beacons.ai")
    for href in page.links:
        if href.startswith(("#","javascript:","data:")):continue
        link=urljoin(r.url,href);host=urlsplit(link).hostname
        if profile_key(link) or host=="wa.me" or href.startswith(("mailto:","tel:")) or href in page.identity_links or (hub and host!=urlsplit(r.url).hostname):links.append(link)
    return {"site":"website","profile_url":r.url,"fields":{"title":clean(page.title)[:300],"description":clean(page.meta.get("description", ""))[:2000]},"links":links[:60]},r.url


def relationship(parent,child,source,depth,kind="PUBLIC_LINK"):
    return item("relationship",parent+" → "+child,source,title=kind,status="CANDIDATE",
                raw={"from":parent,"to":child,"relation":kind,"depth":depth},
                reason="Tautan/identifier tercantum pada sumber publik. Hubungan ini belum membuktikan pemilik akun sama.")


def phone(ctx):
    yield item("phone_format",{"international":ctx.value,"digits":ctx.value[1:]},"local:phone",status="UNVERIFIED",
               reason="Normalisasi format internasional saja; bukan pemeriksaan nomor aktif, WhatsApp, nama, atau lokasi.")


def fusion(ctx):
    mode=ctx.config["fusion_mode"];depth_limit,sites=MODES[mode];budget=ctx.config["fusion_max_nodes"]
    queue=deque();seen=set();edges=set();count=0
    if ctx.kind=="username":
        for site in sites:queue.append((URLS[site].format(ctx.value),0))
    else:queue.append((ctx.value,0))
    yield item("collection_scope",{"mode":mode,"depth":depth_limit,"max_pages":budget,"sites":list(sites)},"local:fusion",
               title="Fusion scope",reason="Batas pengumpulan; URL media tidak diunduh, query tidak diikuti.")
    while queue and count<budget:
        if ctx.stop.is_set():raise AppError("CANCELLED","Dibatalkan.")
        url,depth=queue.popleft()
        try:url=canonical_link(url)
        except AppError:continue
        if url in seen:continue
        seen.add(url);count+=1;key=profile_key(url)
        try:
            if key:
                data,source,absence=fetch_profile(ctx,*key)
                if data is None:
                    yield item("profile_check",url,source,title=key[0]+" / tidak ditemukan pada respons",status="UNVERIFIED",reason=absence)
                    continue
            else:data,source=public_page(ctx,url)
            yield item("profile" if key else "website",data["fields"],source,title=(key[0]+" / @"+key[1]) if key else data["fields"].get("title") or url,
                       status="CANDIDATE" if key else "VERIFIED",raw=data,reason="Metadata halaman/API cocok dengan profil yang diminta; kepemilikan lintas akun perlu ditinjau." if key else "Judul/tautan diamati dari HTML publik.")
            if key and key[0]=="github" and mode!="quick":
                social_source="https://api.github.com/users/"+quote(key[1],safe="")+"/social_accounts"
                try:
                    social=ctx.client.json(social_source)
                    if not isinstance(social,list):raise AppError("PROFILE_SCHEMA","Skema social_accounts berubah.")
                    for entry in social[:30]:
                        if isinstance(entry,dict) and isinstance(entry.get("url"),str):
                            child=entry["url"]
                            try:child=canonical_link(child)
                            except AppError:continue
                            edge=(url,child)
                            if edge not in edges:
                                edges.add(edge);yield relationship(url,child,social_source,depth+1,"PLATFORM_LINK")
                                if depth<depth_limit:queue.append((child,depth+1))
                except AppError as e:
                    if e.code=="CANCELLED":raise
                    yield failed(social_source,e)
            for link in data["links"]:
                if not isinstance(link,str):continue
                # Public contact links are recorded, never messaged or registered.
                if link.startswith(("mailto:","tel:")):
                    kind="PUBLIC_CONTACT";child=clean(link.split("?",1)[0])[:200]
                else:
                    try:child=canonical_link(link)
                    except AppError:continue
                    kind="PUBLIC_CONTACT" if urlsplit(child).hostname in ("wa.me","api.whatsapp.com") else "PUBLIC_LINK"
                if child==url or (url,child) in edges:continue
                edges.add((url,child));yield relationship(url,child,source,depth+1,kind)
                # Crawl profile links and outbound pages only; no same-site spider.
                cross_host=urlsplit(child).hostname!=urlsplit(url).hostname
                if kind!="PUBLIC_CONTACT" and depth<depth_limit and (profile_key(child) or cross_host) and len(queue)<budget*3:
                    queue.append((child,depth+1))
            for field in ("email","bio","description"):
                for match in EMAIL_RE.finditer(str(data["fields"].get(field,""))):
                    child="mailto:"+match.group()
                    if (url,child) not in edges:
                        edges.add((url,child));yield relationship(url,child,source,depth+1,"PUBLIC_CONTACT")
        except AppError as e:
            if e.code=="CANCELLED":raise
            yield failed(url,e)
    if queue:yield item("collection_limit",f"Batas {budget} halaman tercapai; masih ada tautan dalam antrean.","local:fusion",status="UNVERIFIED")
