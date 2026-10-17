import os
import shutil
import sys
import textwrap
from pathlib import Path
from .core import clean
from . import __version__

LABELS=["Auto Investigation","Username Intelligence","Domain / Website","IP / Network","Email Intelligence","Metadata Forensics","Evidence & History","AI Narration (optional)","Generate Report","Settings / Modules"]

class UI:
    def __init__(self,width=None):
        self.width=max(20,min(120,width or shutil.get_terminal_size((40,24)).columns))
        self.color=sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM")!="dumb"
    def put(self,text=""):
        for line in clean(text).split("\n"):
            for part in textwrap.wrap(line,width=self.width,replace_whitespace=False,drop_whitespace=True) or [""]:
                print(part)
    def heading(self,text):
        self.put("-"*self.width)
        self.put(text)
    def ask(self,prompt):
        self.put(prompt)
        return input("> ").strip()
    def confirm(self,prompt):return self.ask(prompt+" [y/N]").lower() in ("y","yes","ya")
    def banner(self):
        root=Path(__file__).parent/"assets"
        utf="utf" in (sys.stdout.encoding or "").lower()
        name="icon-mobile.txt"
        if self.color and utf:
            name="icon-rgb.ans" if os.environ.get("COLORTERM") in ("truecolor","24bit") else "icon-mobile.ans"
        p=root/name
        if p.exists():print(p.read_text(),end="")
        self.put("OSINTCLI / "+__version__)
        self.put("by R_HMT  |  Local-first OSINT")
    def menu(self):
        self.heading("PUBLIC SOURCES / LOCAL EVIDENCE")
        for i,label in enumerate(LABELS,1):self.put(f"[{i:02d}] {label}")
        self.put("[00] Exit")
    def evidence(self,rows,paginate=True):
        if not rows:self.put("Belum ada evidence.")
        for n,r in enumerate(rows,1):
            self.heading(f"{n:03d} / {r['status']}")
            self.put(r["title"]+" | "+r["adapter_id"])
            self.put(r["normalized_value"])
            self.put("Sumber: "+(r["source_url"] or r["source_name"]))
            self.put(r["collected_at"])
            self.put("Alasan: "+r["verification_reason"])
            if paginate and n%5==0 and n<len(rows):
                if self.ask("Enter: lanjut / 0: kembali")=="0":break
