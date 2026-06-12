"""
security helpers — hashing, rate limiting, validation, headers
"""

import re
import os
import hmac
import time
import hashlib
import secrets
import ipaddress
from collections import defaultdict
from typing import Optional
from fastapi import Request, HTTPException

SECRET = os.getenv("HASHIT_SECRET", secrets.token_hex(32))

SLUG_RE    = re.compile(r"^[a-z2-9]{8}$")
MAX_FN_LEN = 255

BLOCKED_EXTS = {
    ".exe",".dll",".bat",".cmd",".com",".msi",".ps1",".vbs",
    ".jar",".py",".rb",".sh",".bash",".zsh",".fish",".php",
    ".asp",".aspx",".jsp",".phtml",".scr",".pif",".lnk",".reg",
}

FORCE_DOWNLOAD_EXTS = {".html",".htm",".svg",".xml",".xhtml"}

SAFE_INLINE_MIMES = {
    "text/plain","application/json","application/pdf",
    "image/png","image/jpeg","image/gif","image/webp","image/bmp","image/svg+xml",
    "audio/mpeg","audio/ogg","audio/wav",
    "video/mp4","video/webm","video/ogg",
}

SECURITY_HEADERS = {
    "X-Content-Type-Options":    "nosniff",
    "X-Frame-Options":           "DENY",
    "X-XSS-Protection":          "1; mode=block",
    "Referrer-Policy":           "no-referrer",
    "Permissions-Policy":        "geolocation=(), microphone=(), camera=()",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    ),
}


def pw_hash(pw: str) -> str:
    salt = secrets.token_bytes(32)
    dk   = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + ":" + dk.hex()


def pw_verify(pw: str, stored: str) -> bool:
    try:
        salt, dk = bytes.fromhex(stored[:64]), bytes.fromhex(stored[65:])
        check    = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
        return hmac.compare_digest(check, dk)
    except Exception:
        return False


def make_delete_token(slug: str) -> str:
    return hmac.new(SECRET.encode(), slug.encode(), "sha256").hexdigest()


def verify_delete_token(slug: str, token: str) -> bool:
    expected = make_delete_token(slug)
    return hmac.compare_digest(expected, token)


def safe_filename(name: str) -> str:
    name = os.path.basename(name).replace("\x00", "")
    name = re.sub(r"[^\w.\-]", "_", name).lstrip(".")
    return name[:MAX_FN_LEN] or "file"


def get_ip(request: Request) -> str:
    behind_proxy = os.getenv("HASHIT_BEHIND_PROXY", "0") == "1"
    if behind_proxy:
        fwd = request.headers.get("X-Forwarded-For", "")
        ip  = fwd.split(",")[0].strip()
        try:
            ipaddress.ip_address(ip)
            return ip
        except ValueError:
            pass
    return request.client.host if request.client else "0.0.0.0"


def parse_ttl(s: str) -> int:
    s = s.strip().lower()
    try:
        if s.endswith("h"): return int(s[:-1]) * 3600
        if s.endswith("m"): return int(s[:-1]) * 60
        if s.endswith("d"): return int(s[:-1]) * 86400
        return int(s)
    except (ValueError, OverflowError):
        raise HTTPException(400, "invalid ttl — use 30m, 6h, 7d")


def new_slug(length: int = 8) -> str:
    return "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(length))


# ── rate limiter ──────────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self):
        self._data: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, limit: int, window: int = 60) -> bool:
        now = time.monotonic()
        self._data[key] = [t for t in self._data[key] if now - t < window]
        if len(self._data[key]) >= limit:
            return False
        self._data[key].append(now)
        return True

    def cleanup(self):
        now = time.monotonic()
        self._data = defaultdict(list, {
            k: [t for t in v if now - t < 3600]
            for k, v in self._data.items() if v
        })

limiter = RateLimiter()

RL_UPLOAD   = int(os.getenv("HASHIT_RL_UPLOAD",   "20"))
RL_DOWNLOAD = int(os.getenv("HASHIT_RL_DOWNLOAD", "120"))
