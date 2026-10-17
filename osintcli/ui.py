import os
import shutil
import sys
import textwrap
import time
from pathlib import Path
from .core import clean
from . import __version__

LABELS=["Auto Investigation / Fusion","Username Intelligence","Domain / Website","IP / Network","Email Intelligence","Metadata Forensics","Evidence / Review / History","AI Narration (optional)","Generate Report / PDF / DOCX","Settings / Modules","Profile URL / Public Links","Phone / Public Contact"]

class UI:
    def __init__(self,width=None):
        self.width=max(20,min(400,width or shutil.get_terminal_size((40,24)).columns))
        self.color=sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM")!="dumb"
    def paint(self,text,color="cyan"):
        codes={"cyan":36,"green":92,"yellow":93,"red":91,"dim":90}
        return f"\033[{codes[color]}m{text}\033[0m" if self.color else text
    def put(self,text="",color=None):
        for line in clean(text).split("\n"):
            for part in textwrap.wrap(line,width=self.width,replace_whitespace=False,drop_whitespace=True) or [""]:
                print(self.paint(part,color) if color else part)
    def path(self,value,prefix=""):
        print(clean(prefix+str(value)))
    def heading(self,text):
        self.put("─"*min(self.width,80) if "utf" in (sys.stdout.encoding or "").lower() else "-"*min(self.width,80),"dim")
        self.put(text,"yellow")
    def ask(self,prompt):
        self.put(prompt,"cyan")
        return input(self.paint("> ","green")).strip()
    def confirm(self,prompt):return self.ask(prompt+" [y/N]").lower() in ("y","yes","ya")
    def startup(self,config,db):
        from .external import executable
        from .core import AppError
        from .cli import doctor
        checks=[("Database",lambda: str(len(db.cases()))+" kasus"),
                ("Engine",lambda: "Fusion / siap"),
                ("Laporan",lambda: "PDF + DOCX" if all(v=="READY" for v in doctor(config)["reports"].values()) else "lihat Settings / Modules")]
        animate=self.color and config["animation"]=="on" and not os.environ.get("OSINTCLI_NO_ANIMATION")
        try:
            for label,check in checks:
                if animate:
                    for frame in ("·","••","•••"):
                        print("\r"+self.paint(("  "+frame+" "+label).ljust(min(self.width,40)),"green"),end="",flush=True)
                        time.sleep(.10)
                    print("\r"+" "*min(self.width,40)+"\r",end="")
                result=check()
                self.put(("[!!] " if "lihat Settings" in result else "[OK] ")+label+" / "+result,"yellow" if "lihat Settings" in result else "green")
        except KeyboardInterrupt:self.put("Animasi dilewati.","dim")
        self.banner()
    def banner(self):
        root=Path(__file__).parent/"assets"
        original=root/"banner-original.txt"
        lines=original.read_text().splitlines() if original.exists() else []
        needed=max(map(len,lines),default=999)
        if needed<=self.width:
            for line in lines:print(self.paint(line,"yellow"))
        else:
            p=root/("banner-compact.txt" if self.width>=48 else "banner-mobile.txt")
            if p.exists():
                for line in p.read_text().splitlines():print(self.paint(line[:self.width],"yellow"))
        self.put("OSINTCLI / "+__version__,"yellow")
        self.put("by R_HMT  |  PUBLIC INTELLIGENCE","green")
        self.put("Collect · Connect · Review · Report","cyan")
    def menu(self):
        self.heading("INVESTIGATION WORKSPACE")
        for i,label in enumerate(LABELS,1):self.put(f"[{i:02d}] {label}","green")
        self.put("[00] Exit","dim")
    def evidence(self,rows,paginate=True):
        if not rows:self.put("Belum ada evidence.")
        for n,r in enumerate(rows,1):
            self.heading(f"{n:03d} / {r['status']}")
            self.put(r["title"]+" | "+r["adapter_id"])
            self.put("ID: "+r["id"],"dim")
            self.put(r["normalized_value"])
            self.put("Sumber: "+(r["source_url"] or r["source_name"]))
            self.put(r["collected_at"])
            self.put("Alasan: "+r["verification_reason"])
            if paginate and n%5==0 and n<len(rows):
                if self.ask("Enter: lanjut / 0: kembali")=="0":break
