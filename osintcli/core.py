from __future__ import annotations
import contextlib
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import tomllib
from datetime import datetime, timezone
from urllib.parse import urlsplit

class AppError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def clean(value):
    # Remove terminal/OSC escape controls, including bidirectional overrides.
    text = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", str(value))
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return "".join(c for c in text if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127 and c not in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"))

def private_dir(path):
    path = Path(path).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path

@contextlib.contextmanager
def atomic_path(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    os.close(fd)
    try:
        yield Path(tmp)
        with open(tmp, "rb") as f:
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)

def write_atomic(path, text):
    with atomic_path(path) as tmp:
        tmp.write_text(text, encoding="utf-8")

DEFAULTS = {
    "timeout_seconds": 15, "retries": 1, "max_workers": 3,
    "request_interval": 0.8, "max_file_mb": 25,
    "provider": "nexray_http", "endpoint": "https://api.nexray.eu.cc/ai/claude",
    "method": "GET", "input_parameter": "text", "response_text_path": "result",
    "success_path": "status", "max_url_length": 1800, "ai_timeout_seconds": 25,
    "custom_instructions": "Tulis Bahasa Indonesia yang jelas, ringkas, dan netral.",
}

class Config:
    def __init__(self, data=None, config=None):
        self.data = private_dir(data or os.environ.get("OSINTCLI_DATA_DIR", Path(os.environ.get("XDG_DATA_HOME", Path.home()/".local/share"))/"osintcli"))
        self.directory = private_dir(config or os.environ.get("OSINTCLI_CONFIG_DIR", Path(os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"osintcli"))
        self.path = self.directory/"config.toml"
        self.values = DEFAULTS.copy()
        if self.path.exists():
            try:
                self.values.update(tomllib.loads(self.path.read_text()))
            except (ValueError, OSError) as e:
                raise AppError("CONFIG", "Config TOML tidak valid; perbaiki config.toml.") from e
        self.validate()
        if not self.path.exists(): self.save()
        for d in ["cases", "reports"]: private_dir(self.data/d)

    def __getitem__(self, key): return self.values[key]

    def validate(self):
        for key, low, high in [("timeout_seconds",1,60),("retries",0,3),("max_workers",1,4),("request_interval",0.2,10),("max_file_mb",1,100),("max_url_length",128,8000),("ai_timeout_seconds",1,60)]:
            value = self.values[key]
            if not isinstance(value, (float,int)) or not low <= value <= high:
                raise AppError("CONFIG", f"{key} harus {low}..{high}.")
        for key in ("retries", "max_workers", "max_url_length"):
            if not isinstance(self.values[key], int): raise AppError("CONFIG", f"{key} harus integer.")
        if self.values["method"] not in ("GET", "POST"): raise AppError("CONFIG", "Method harus GET atau POST.")
        for key in ("endpoint", "input_parameter", "response_text_path", "success_path", "custom_instructions"):
            if not isinstance(self.values[key], str): raise AppError("CONFIG", f"{key} harus teks.")
        if len(self.values["custom_instructions"]) > 4000: raise AppError("CONFIG", "Instruksi maksimal 4000 karakter.")
        p = urlsplit(self.values["endpoint"])
        if p.scheme != "https" or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise AppError("CONFIG", "Endpoint harus HTTPS tanpa kredensial, query, atau fragment.")

    def set(self, key, value):
        if key not in DEFAULTS: raise AppError("CONFIG", "Pengaturan tidak dikenal.")
        old = self.values.copy()
        try:
            if isinstance(DEFAULTS[key], int): value = int(value)
            elif isinstance(DEFAULTS[key], float): value = float(value)
            self.values[key] = value
            self.validate()
            self.save()
        except (ValueError, AppError):
            self.values = old
            raise AppError("CONFIG", "Nilai pengaturan tidak valid.")

    def save(self):
        write_atomic(self.path, "# OSINTCLI - nonsecret settings\n" + "\n".join(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k,v in self.values.items()) + "\n")

    def headers(self):
        p = self.directory/"secrets.toml"
        if not p.exists(): return {}
        if p.stat().st_mode & 0o077: raise AppError("PERMISSIONS", "Jalankan chmod 600 pada secrets.toml.")
        headers = tomllib.loads(p.read_text()).get("headers", {})
        forbidden = {"host","content-length","transfer-encoding","connection"}
        if not isinstance(headers, dict) or any(k.lower() in forbidden or not re.fullmatch(r"[A-Za-z0-9-]+",k) or not isinstance(v,str) or "\r" in v or "\n" in v for k,v in headers.items()):
            raise AppError("CONFIG", "Header rahasia tidak valid.")
        return headers

def domain(value):
    try: value = value.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError: raise AppError("TARGET", "Domain tidak valid.")
    if len(value)>253 or "." not in value or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",x) for x in value.split(".")):
        raise AppError("TARGET", "Masukkan domain publik, misalnya example.com.")
    if value.endswith((".local", ".localhost", ".internal", ".lan")):
        raise AppError("TARGET", "Domain internal tidak didukung.")
    return value

def target(value, kind="auto"):
    value = value.strip()
    if not value or len(value)>2048 or any(ord(c)<32 for c in value): raise AppError("TARGET", "Target kosong/tidak valid.")
    if kind == "auto":
        if Path(value).expanduser().is_file(): kind = "metadata"
        elif value.startswith(("https://","http://")): kind = "domain"
        elif "@" in value and not value.startswith("@"): kind = "email"
        else:
            try: ipaddress.ip_address(value); kind = "ip"
            except ValueError: kind = "domain" if "." in value and not value.startswith("@") else "username"
    if kind == "metadata":
        p=Path(value).expanduser().resolve()
        if not p.is_file(): raise AppError("FILE", "File lokal tidak ditemukan.")
        return kind, str(p)
    if kind == "ip":
        try: ip=ipaddress.ip_address(value)
        except ValueError: raise AppError("TARGET", "IP tidak valid.")
        if not ip.is_global or ip.is_multicast or ip.is_reserved: raise AppError("TARGET", "Hanya IP publik yang didukung.")
        return kind, str(ip)
    if kind == "domain":
        if "://" in value:
            p=urlsplit(value)
            if p.scheme not in ("https","http") or p.username or p.password or p.query or p.fragment:
                raise AppError("TARGET", "Gunakan URL publik tanpa kredensial/query/fragment.")
            value=p.hostname or ""
        return kind, domain(value)
    if kind == "email":
        if value.count("@")!=1: raise AppError("TARGET", "Email tidak valid.")
        local,host=value.split("@")
        if not re.fullmatch(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]{1,64}", local) or local.startswith(".") or local.endswith(".") or ".." in local:
            raise AppError("TARGET", "Sintaks email tidak didukung.")
        return kind, local+"@"+domain(host)
    if kind == "username":
        value=value.removeprefix("@")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}",value): raise AppError("TARGET", "Username: 1-64 huruf, angka, _, titik, atau -.")
        return kind,value
    raise AppError("TARGET", "Jenis target tidak dikenal.")
