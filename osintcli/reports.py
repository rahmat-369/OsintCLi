"""Deterministic exports. AI prose is a separate, reviewed appendix."""
import csv
from collections import Counter
import html
import io
import json
from pathlib import Path
import re
import uuid
from . import __version__
from .core import AppError, now, digest, clean, write_atomic, atomic_path


def snapshot(db,cid,include_ai=False,summary=False):
    case=db.case(cid);rows=db.evidence(cid,raw=True);jobs=db.jobs(cid)
    return {"schema_version":2,"relationships":db.graph(cid),"reviews":db.reviews(cid),"methodology":("Fusion mengikuti tautan publik dengan batas mode dan jumlah halaman yang tercatat pada collection_scope. Tautan adalah observasi, bukan pembuktian identitas. Media dan query tidak diikuti otomatis." if "fusion" in case["scope"] else "Modul terpilih memeriksa sumber publik/lokal. Hubungan dicatat hanya bila tersedia dari sumber; tidak ada atribusi identitas otomatis."),"report_id":uuid.uuid4().hex[:16],"generator":"OsintCLI "+__version__,"generated_at":now(),"dataset_digest":db.dataset_digest(cid),"case":case,"counts":{"total":len(rows),"by_category":dict(Counter(r["entity_type"] for r in rows)),"by_status":dict(Counter(r["status"] for r in rows))},"jobs":jobs,"evidence":rows,"narrative":db.narrative(cid,reviewed=True) if include_ai else None,"summary_only":summary}

def safe_cell(v):
    s=clean(v)
    return "'"+s if s.lstrip().startswith(("=","+","-","@")) or s.startswith(("\t","\r","\n")) else s

def _arabic(text):
    if re.search(r"[\u0600-\u06ff]",text):
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            return get_display(arabic_reshaper.reshape(text))
        except ImportError:raise AppError("FONT","Teks Arab membutuhkan arabic-reshaper dan python-bidi; install profil reports.")
    return text

def fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    root=Path(__file__).parent/"assets"
    regular=root/"DejaVuSans.ttf";bold=root/"DejaVuSans-Bold.ttf"
    if not regular.exists() or not bold.exists():raise AppError("FONT","Font report bawaan hilang; install ulang paket.")
    pdfmetrics.registerFont(TTFont("OSINT",str(regular)))
    pdfmetrics.registerFont(TTFont("OSINT-Bold",str(bold)))
    pdfmetrics.registerFontFamily("OSINT",normal="OSINT",bold="OSINT-Bold",italic="OSINT",boldItalic="OSINT-Bold")
    return regular

def chart_image(data,path):
    from PIL import Image,ImageDraw,ImageFont
    regular=fonts();f=ImageFont.truetype(str(regular),18);small=ImageFont.truetype(str(regular),14)
    categories=data["counts"]["by_category"]
    im=Image.new("RGB",(1000,max(220,100+len(categories)*42)),"#f5f8fa");d=ImageDraw.Draw(im)
    d.text((28,20),"OBSERVED EVIDENCE / CATEGORY",font=f,fill="#142936")
    maximum=max(categories.values(),default=1)
    for i,(key,count) in enumerate(sorted(categories.items())):
        y=64+i*42;d.text((28,y+6),key,font=small,fill="#142936")
        width=int(count/maximum*560)
        d.rectangle((260,y+4,260+max(width,1),y+29),fill="#009cac")
        d.text((840,y+5),str(count),font=f,fill="#142936")
    if not categories:d.text((28,90),"No evidence collected",font=f,fill="#546575")
    d.text((28,im.height-27),"Source: local SQLite snapshot | "+data["generated_at"],font=small,fill="#546575")
    with atomic_path(path) as tmp:im.save(tmp,format="PNG")

def pdf_export(data,path):
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.graphics.shapes import Drawing,Rect,String,Line
    except ImportError:raise AppError("DEPENDENCY","PDF membutuhkan profil reports. Jalankan installer atau pip install '.[reports]'.")
    fonts()
    style=ParagraphStyle("Body",fontName="OSINT",fontSize=9,leading=14,textColor=colors.HexColor("#243c49"),splitLongWords=True,spaceAfter=7)
    heading=ParagraphStyle("Heading",parent=style,fontName="OSINT-Bold",fontSize=16,leading=22,spaceBefore=16,spaceAfter=12,keepWithNext=True)
    tiny=ParagraphStyle("Tiny",parent=style,fontSize=7,leading=11)
    title=ParagraphStyle("Title",parent=heading,fontSize=32,leading=40)
    def p(text,s=style):return Paragraph(html.escape(_arabic(clean(text))).replace("\n","<br/>"),s)
    def chunks(text,size=900):
        text=clean(text);result=[];current=[];length=0
        for line in text.splitlines() or [""]:
            for part in [line[n:n+size] for n in range(0,len(line),size)] or [""]:
                if current and (len(current)>=12 or length+len(part)>size):
                    result.append("\n".join(current));current=[];length=0
                current.append(part);length+=len(part)+1
        if current:result.append("\n".join(current))
        return result or [""]
    def table(rows,widths):
        t=Table([[p(x,style if len(widths)==1 else tiny) for x in row] for row in rows],colWidths=widths,repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e4f1f3")),("VALIGN",(0,0),(-1,-1),"TOP"),("LINEBELOW",(0,0),(-1,0),0.7,colors.HexColor("#009cac")),("BOTTOMPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),7),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#f6f8fa")])]))
        return t
    case=data["case"];rows=data["evidence"];story=[]
    story += [Spacer(1,48),p("OSINTCLI",title),p("PUBLIC-SOURCE INTELLIGENCE REPORT",heading),p("by R_HMT"),Spacer(1,28),p(case["target"],heading),p("Case "+case["id"]+"  |  "+case["kind"]),p("Generated "+data["generated_at"]),p("Report "+data["report_id"]),Spacer(1,30),p("Local investigative record. May contain sensitive public or file metadata. Share only after reviewing contents."),p("A matching username, HTTP response, or source claim does not establish a person's identity. VERIFIED means the recorded observation matches the consulted source."),p("OFFLINE FIXTURE / DEMONSTRATION" if "demo" in case["scope"] else "Source collection results; unavailable sources are listed explicitly."),PageBreak()]
    story += [p("01 / Executive summary",heading),p(f"Case state: {case['state']}. {data['counts']['total']} evidence records across {len(data['counts']['by_category'])} categories. Figures are computed from the database, never from AI."),table([["Status","Records"]]+[[k,str(v)] for k,v in sorted(data["counts"]["by_status"].items())],[340,170])]
    if not rows:story.append(p("No evidence collected. This does not establish absence of the target. Check source availability and scope."))
    story += [p("02 / Methodology and scope",heading),p("Selected modules: "+", ".join(case["scope"])),p("Collection began: "+case["created_at"]),p(data["methodology"]),p("Source gaps, historical records, soft-404 pages, rate limits and mutable metadata can reduce coverage. No exhaustive search or identity verification is implied."),table([["Module / version","State","Window (UTC)"]]+[[j["adapter"]+" / "+j["version"],j["state"],(j["started_at"] or "")+"\n"+(j["ended_at"] or "")] for j in data["jobs"]],[195,75,240])]
    story += [p("03 / Evidence overview",heading)]
    def bars(counts):
        draw=Drawing(500,40+26*max(1,len(counts)))
        maximum=max(counts.values(),default=1)
        if not counts:draw.add(String(0,20,"No records",fontName="OSINT",fontSize=10))
        for i,(key,value) in enumerate(sorted(counts.items())):
            y=draw.height-26*(i+1)
            draw.add(String(0,y+5,key,fontName="OSINT",fontSize=8))
            draw.add(Rect(150,y,270*value/maximum,17,fillColor=colors.HexColor("#009cac"),strokeColor=None))
            draw.add(String(435,y+5,str(value),fontName="OSINT-Bold",fontSize=9))
        return draw
    story += [KeepTogether([p("Category counts"),bars(data["counts"]["by_category"])]),KeepTogether([p("Status counts"),bars(data["counts"]["by_status"])])]
    days=Counter(r["collected_at"][:10] for r in rows)
    if len(days)>1:story += [p("Collection timeline / UTC day"),bars(days)]
    else:story.append(p("Timeline omitted: evidence spans fewer than two collection dates."))
    story += [p("04 / Public links and review",heading),p("Tautan menghubungkan halaman sumber dengan tujuan yang dicantumkan. Kesamaan username dan tautan belum membuktikan pemilik akun sama.")]
    if data["relationships"]:
        graph=Drawing(510,35+len(data["relationships"][:6])*42)
        for index,edge in enumerate(data["relationships"][:6]):
            y=graph.height-30-index*42
            for x,key in ((0,"from"),(280,"to")):
                label=edge[key].removeprefix("https://").removeprefix("http://")
                if len(label)>34:label=label[:31]+"..."
                graph.add(Rect(x,y-9,225,31,fillColor=colors.HexColor("#e4f1f3"),strokeColor=None))
                graph.add(String(x+6,y+5,label,fontName="OSINT",fontSize=7))
            graph.add(Line(229,y+4,275,y+4,strokeColor=colors.HexColor("#009cac")))
            graph.add(String(231,y-7,str(index+1),fontName="OSINT",fontSize=6))
        story += [graph,p("Diagram: maksimal enam hubungan. URL lengkap dan keputusan review ada di bawah.",tiny)]
    for edge in data["relationships"]:
        story += [p(edge["from"]+" → "+edge["to"]),p(edge["relation"]+" / depth "+str(edge["depth"])+" / review: "+edge["review"]["decision"],tiny),p("Source: "+edge["source_url"]+" / "+edge["collected_at"],tiny)]
        if edge["review"].get("note"):story.append(p("Review note: "+edge["review"]["note"]))
    if not data["relationships"]:story.append(p("No public cross-profile links observed in this case."))
    story += [PageBreak(),p("05 / Evidence register",heading)]
    display=rows[:15] if data["summary_only"] else rows
    if data["summary_only"] and len(rows)>15:story.append(p("Summary view: first 15 records. Companion JSON/CSV contains the complete dataset."))
    for n,r in enumerate(display,1):
        value=r["normalized_value"]
        try:
            fields=json.loads(value)
            if isinstance(fields,dict):value="\n".join(str(k)+": "+str(v) for k,v in fields.items())
        except (ValueError,TypeError):pass
        parts=chunks(value)
        entry=[]
        entry.extend([p(f"{n:03d} / {r['title']} [{r['status']}]",heading),p(r["id"]+" | "+r["adapter_id"]+" | "+r["collected_at"],tiny),table([["Observed value"],[parts[0]]],[510])])
        for part in parts[1:]:entry.append(table([["Observed value (continued)"],[part]],[510]))
        entry += [p("Reason: "+r["verification_reason"]),p("Basis: "+r["confidence_basis"],tiny)]
        source=r["source_url"] or r["source_name"]
        if source.startswith(("https://","http://")):
            safe=html.escape(source,quote=True)
            entry.append(Paragraph('<link href="'+safe+'" color="#007b87">'+html.escape(clean(source))+'</link>',tiny))
        else:entry.append(p(source,tiny))
        reviews=[review for review in data["reviews"] if review["evidence_id"]==r["id"]]
        if reviews:entry.append(p("Operator review: "+reviews[-1]["decision"]+" / "+reviews[-1]["note"]))
        entry.append(p("Evidence digest: "+r["digest"],tiny))
        if len(value)<900 and value.count("\n")<12 and len(r["title"])<100 and len(r["verification_reason"])<500:story.append(KeepTogether(entry))
        else:story.extend([KeepTogether(entry[:3]),*entry[3:]])
    story += [p("06 / Observations and limitations",heading),p("The register documents source observations at collection time. CANDIDATE records require manual review. FAILED_SOURCE records represent coverage gaps. An empty response is not a verified negative. Country/ASN registration fields do not locate a person."),p("07 / Appendix and trace",heading),p("Dataset SHA-256: "+data["dataset_digest"],tiny),p("Generator: "+data["generator"]),p("JSON companion preserves raw source payloads separately from normalized fields; CSV supplies a formula-safe flattened register.")]
    for j in data["jobs"]:
        if j["error_code"]:story.append(p(j["adapter"]+": "+j["error_code"]+" / "+(j["message"] or "")))
    narrative=data["narrative"]
    if narrative:
        story += [p("08 / Human-reviewed AI narrative",heading),p("Provider: "+narrative["provider"]+". Reviewed prose is not new evidence. Numeric counts and charts remain database-derived."),p("Prompt digest: "+narrative["prompt_digest"],tiny)]
        for part in chunks(narrative["text"]):story.append(p(part))
    else:story.append(p("AI narration not included. This report is complete without an external AI service."))
    def footer(canvas,doc):
        canvas.setFont("OSINT",7);canvas.setFillColor(colors.HexColor("#546575"))
        canvas.drawString(42,24,"OSINTCLI / R_HMT / "+case["id"])
        canvas.drawRightString(A4[0]-42,24,f"Page {doc.page}")
    with atomic_path(path) as tmp:
        doc=SimpleDocTemplate(str(tmp),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=38,bottomMargin=42,title="OSINTCLI / "+case["id"],author="R_HMT")
        doc.build(story,onFirstPage=footer,onLaterPages=footer)


def export(db,cid,formats=("pdf","docx","json","csv","html","png"),out=None,include_ai=False,summary=False):
    formats=list(dict.fromkeys(formats))
    if any(f not in {"pdf","docx","json","csv","html","png"} for f in formats):raise AppError("FORMAT","Format export tidak dikenal.")
    data=snapshot(db,cid,include_ai,summary)
    destination=Path(out).expanduser().resolve() if out else db.config.data/"reports"/cid
    destination.mkdir(parents=True,exist_ok=True)
    paths=[]
    for fmt in formats:
        path=destination/("osintcli-"+cid+"."+fmt)
        if fmt=="json":write_atomic(path,json.dumps(data,ensure_ascii=False,indent=2))
        elif fmt=="csv":
            buf=io.StringIO(newline="");writer=csv.writer(buf)
            fields=["id","entity_type","normalized_value","title","status","source_url","source_name","adapter_id","collected_at","verification_reason","confidence_basis","digest","error_code"]
            writer.writerow(fields)
            for row in data["evidence"]:writer.writerow([safe_cell(row.get(k) or "") for k in fields])
            write_atomic(path,buf.getvalue())
        elif fmt=="html":
            def esc(x):return html.escape(clean(x))
            body="".join("<article><h2>"+esc(r["title"])+"</h2><p>"+esc(r["status"])+"</p><pre>"+esc(r["normalized_value"])+"</pre><p>"+esc(r["source_url"] or r["source_name"])+"</p><small>"+esc(r["collected_at"])+" · "+esc(r["verification_reason"])+"</small></article>" for r in data["evidence"])
            body="<h2>Public links / review</h2>"+"".join("<article><p>"+esc(e["from"])+" → "+esc(e["to"])+"</p><p>"+esc(e["relation"])+" / "+esc(e["review"]["decision"])+"</p><small>"+esc(e["source_url"])+"</small></article>" for e in data["relationships"])+body
            text='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>OSINTCLI report</title><style>body{max-width:900px;margin:40px auto;padding:20px;font:16px system-ui;color:#17323d;background:#f5f8fa}article{background:white;padding:20px;margin:15px 0;border-left:3px solid #009cac}pre,small{white-space:pre-wrap;overflow-wrap:anywhere}h1{letter-spacing:.08em}</style><h1>OSINTCLI</h1><p>by R_HMT · '+esc(data["case"]["target"])+"</p><p>"+str(data["counts"]["total"])+" evidence records · "+esc(data["generated_at"])+"</p><p>Matching usernames do not verify identity. FAILED_SOURCE is a coverage gap.</p>"+body+"<footer>Dataset SHA-256: "+esc(data["dataset_digest"])+"</footer></html>"
            write_atomic(path,text)
        elif fmt=="png":chart_image(data,path)
        elif fmt=="pdf":pdf_export(data,path)
        elif fmt=="docx":
            from .docx_report import docx_export
            docx_export(data,path)
        paths.append(path)
    return paths
