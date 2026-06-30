# hashit — server v2.0 (by ne0k1r4 · india)

import os
import io
import time
import base64
import asyncio
import logging
import mimetypes
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
import aiofiles
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db, get_db, purge_expired
from .security import (
    pw_hash, pw_verify, make_delete_token, verify_delete_token,
    safe_filename, get_ip, parse_ttl, new_slug,
    limiter, SLUG_RE, BLOCKED_EXTS, FORCE_DOWNLOAD_EXTS,
    SAFE_INLINE_MIMES, SECURITY_HEADERS, RL_UPLOAD, RL_DOWNLOAD,
)

# config

UPLOAD_DIR = Path(os.getenv("HASHIT_UPLOAD_DIR", "/tmp/hashit_uploads"))
MAX_SIZE = int(os.getenv("HASHIT_MAX_SIZE_MB", "512")) * 1 << 20
MAX_TTL = int(os.getenv("HASHIT_MAX_TTL_HOURS", "168")) * 3600
BASE_URL = os.getenv("HASHIT_BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("HASHIT_ADMIN_TOKEN", secrets.token_hex(16))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("hashit")

# app

app = FastAPI(
    title="hashit",
    description="zero-friction file sharing by ne0k1r4",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-Admin-Token"],
    allow_credentials=False,
)

app.mount("/static", StaticFiles(directory=Path(__file__).parent.parent / "web" / "static"), name="static")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    path = str(request.url.path)
    if "\x00" in path or ".." in path:
        return JSONResponse({"detail": "bad request"}, status_code=400)
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    for h in ("server", "x-powered-by"):
        if h in response.headers:
            del response.headers[h]
    return response


@app.on_event("startup")
async def startup():
    # TODO: check if upload directory is actually writable before starting, sometimes docker volume mounts fail silently
    init_db()
    asyncio.create_task(_bg_purge())
    asyncio.create_task(_bg_rl_cleanup())
    log.info("hashit v2.0 · base=%s · upload_dir=%s", BASE_URL, UPLOAD_DIR)
    log.info("admin token: %s", ADMIN_TOKEN)


async def _bg_purge():
    while True:
        # runs every 5 min in background, not perfect but works
        await asyncio.sleep(300)
        n = await purge_expired()
        if n:
            log.info("purged %d expired files", n)


async def _bg_rl_cleanup():
    while True:
        # runs every 10 min in background to clean up rate limiter
        await asyncio.sleep(600)
        limiter.cleanup()


# helpers

def ts_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def get_base_url(request: Request) -> str:
    # Use request base url to automatically adapt to ngrok, local IP, or custom domains
    env_url = os.getenv("HASHIT_BASE_URL")
    if env_url:
        return env_url.rstrip("/")
    host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host")
    proto = request.headers.get("X-Forwarded-Proto") or request.url.scheme
    if host:
        return f"{proto}://{host}"
    return str(request.base_url).rstrip("/")


def require_admin(request: Request):
    # TODO: switch to proper JWT at some point, token in header is fine for now
    token = request.headers.get("X-Admin-Token") or request.query_params.get("token")
    if not token or token != ADMIN_TOKEN:
        raise HTTPException(403, "admin token required")


# upload

@app.post("/api/upload")
async def upload(
    request: Request,
    file: UploadFile = File(...),
    ttl: str = Form("24h"),
    password: Optional[str] = Form(None),
    max_downloads: Optional[int] = Form(None),
    note: Optional[str] = Form(None),
):
    ip = get_ip(request)
    if not limiter.allow(f"up:{ip}", RL_UPLOAD):
        raise HTTPException(429, "too many uploads")

    ttl_sec = min(parse_ttl(ttl), MAX_TTL)
    filename = safe_filename(file.filename or "file")
    ext = Path(filename).suffix.lower()

    if ext in BLOCKED_EXTS:
        raise HTTPException(415, f"'{ext}' files are not allowed")
    if password and len(password) > 1024:
        raise HTTPException(400, "password too long")
    if max_downloads is not None and not (1 <= max_downloads <= 10000):
        raise HTTPException(400, "max_downloads must be 1–10000")

    slug = new_slug()
    dest = UPLOAD_DIR / slug
    size = 0

    try:
        async with aiofiles.open(dest, "wb") as f:
            # read in 1mb chunks so we dont load the whole file into memory
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > MAX_SIZE:
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, f"too large — max {MAX_SIZE >> 20}MB")
                await f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        log.error("upload error ip=%s: %s", ip, e)
        raise HTTPException(500, "upload failed")

    mime = file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    exp = time.time() + ttl_sec
    dtok = make_delete_token(slug)
    pw_hash_ = pw_hash(password) if password else None

    async with get_db() as db:
        await db.execute(
            """INSERT INTO files
               (slug,filename,path,size,mime,password_hash,expires_at,
                max_downloads,downloads,is_paste,delete_token,created_at,ip,note)
               VALUES (?,?,?,?,?,?,?,?,0,0,?,?,?,?)""",
            (slug, filename, str(dest), size, mime, pw_hash_, exp,
             max_downloads, dtok, time.time(), ip, note)
        )
        await db.commit()

    log.info("upload slug=%s size=%d ip=%s ttl=%ds", slug, size, ip, ttl_sec)

    return {
        "slug": slug,
        "url": f"{get_base_url(request)}/d/{slug}",
        "filename": filename,
        "size": size,
        "expires_at": ts_iso(exp),
        "protected": password is not None,
        "max_downloads": max_downloads,
        "delete_token": dtok,
    }


# paste

@app.post("/api/paste")
async def paste(
    request: Request,
    content: str = Form(...),
    filename: str = Form("paste.txt"),
    ttl: str = Form("24h"),
    password: Optional[str] = Form(None),
):
    ip = get_ip(request)
    if not limiter.allow(f"up:{ip}", RL_UPLOAD):
        raise HTTPException(429, "too many requests")
    if len(content) > 10 << 20:
        raise HTTPException(413, "paste too large — max 10MB")
    if password and len(password) > 1024:
        raise HTTPException(400, "password too long")

    ttl_sec = min(parse_ttl(ttl), MAX_TTL)
    filename = safe_filename(filename)
    slug = new_slug()
    dest = UPLOAD_DIR / slug
    exp = time.time() + ttl_sec
    dtok = make_delete_token(slug)
    pw_hash_ = pw_hash(password) if password else None

    async with aiofiles.open(dest, "w", encoding="utf-8") as f:
        await f.write(content)

    async with get_db() as db:
        await db.execute(
            """INSERT INTO files
               (slug,filename,path,size,mime,password_hash,expires_at,
                max_downloads,downloads,is_paste,delete_token,created_at,ip,note)
               VALUES (?,?,?,?,?,?,?,?,0,1,?,?,?,?)""",
            (slug, filename, str(dest), len(content.encode()),
             "text/plain", pw_hash_, exp, None, dtok, time.time(), ip, None)
        )
        await db.commit()

    log.info("paste slug=%s ip=%s", slug, ip)
    return {
        "slug": slug,
        "url": f"{get_base_url(request)}/d/{slug}",
        "filename": filename,
        "size": len(content.encode()),
        "expires_at": ts_iso(exp),
        "delete_token": dtok,
    }


# upload from URL

@app.post("/api/upload-url")
async def upload_url(
    request: Request,
    url: str = Form(...),
    ttl: str = Form("24h"),
    password: Optional[str] = Form(None),
):
    import urllib.request
    import urllib.error

    ip = get_ip(request)
    if not limiter.allow(f"up:{ip}", RL_UPLOAD):
        raise HTTPException(429, "too many uploads")

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "only http/https URLs supported")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hashit/2.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_length = int(resp.headers.get("Content-Length", 0))
            if content_length > MAX_SIZE:
                raise HTTPException(413, "remote file too large")
            data = resp.read(MAX_SIZE + 1)
            if len(data) > MAX_SIZE:
                raise HTTPException(413, "remote file too large")
            mime = resp.headers.get_content_type() or "application/octet-stream"
            filename = safe_filename(url.rstrip("/").split("/")[-1] or "file")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"could not fetch URL: {e}")

    ttl_sec = min(parse_ttl(ttl), MAX_TTL)
    slug = new_slug()
    dest = UPLOAD_DIR / slug
    exp = time.time() + ttl_sec
    dtok = make_delete_token(slug)
    pw_hash_ = pw_hash(password) if password else None

    dest.write_bytes(data)

    async with get_db() as db:
        await db.execute(
            """INSERT INTO files
               (slug,filename,path,size,mime,password_hash,expires_at,
                max_downloads,downloads,is_paste,delete_token,created_at,ip,note)
               VALUES (?,?,?,?,?,?,?,?,0,0,?,?,?,?)""",
            (slug, filename, str(dest), len(data), mime,
             pw_hash_, exp, None, dtok, time.time(), ip, f"fetched from {url[:200]}")
        )
        await db.commit()

    log.info("upload-url slug=%s from=%s ip=%s", slug, url[:60], ip)
    return {
        "slug": slug,
        "url": f"{get_base_url(request)}/d/{slug}",
        "filename": filename,
        "size": len(data),
        "expires_at": ts_iso(exp),
        "delete_token": dtok,
    }


# info

@app.get("/api/info/{slug}")
async def info(slug: str, request: Request, password: Optional[str] = None):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")

    ip = get_ip(request)
    if not limiter.allow(f"info:{ip}", RL_DOWNLOAD):
        raise HTTPException(429, "too many requests")

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM files WHERE slug=?", (slug,))
        row = await cur.fetchone()

    if not row or time.time() > row["expires_at"]:
        raise HTTPException(404, "not found or expired")

    if row["password_hash"]:
        if not password:
            raise HTTPException(401, "password required")
        if not pw_verify(password, row["password_hash"]):
            await asyncio.sleep(0.3)
            raise HTTPException(403, "wrong password")

    return {
        "slug": slug,
        "filename": row["filename"],
        "size": row["size"],
        "mime": row["mime"],
        "expires_at": ts_iso(row["expires_at"]),
        "downloads": row["downloads"],
        "max_downloads": row["max_downloads"],
        "protected": row["password_hash"] is not None,
        "is_paste": bool(row["is_paste"]),
        "note": row["note"],
    }


# download

@app.get("/api/download/{slug}")
async def download(slug: str, request: Request, password: Optional[str] = None):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")

    ip = get_ip(request)
    if not limiter.allow(f"dl:{ip}", RL_DOWNLOAD):
        raise HTTPException(429, "too many requests")

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM files WHERE slug=?", (slug,))
        row = await cur.fetchone()

    if not row or time.time() > row["expires_at"]:
        raise HTTPException(404, "not found or expired")

    if row["password_hash"]:
        if not password:
            raise HTTPException(401, "password required")
        if not pw_verify(password, row["password_hash"]):
            await asyncio.sleep(0.3)
            raise HTTPException(403, "wrong password")

    if row["max_downloads"] and row["downloads"] >= row["max_downloads"]:
        raise HTTPException(410, "download limit reached")

    path = Path(row["path"])
    if not path.exists():
        raise HTTPException(404, "file not found on disk")

    async with get_db() as db:
        await db.execute(
            "UPDATE files SET downloads=downloads+1 WHERE slug=?", (slug,)
        )
        await db.commit()

    burn = row["max_downloads"] and (row["downloads"] + 1) >= row["max_downloads"]
    ext = Path(row["filename"]).suffix.lower()
    mime = row["mime"]

    disp = (f'attachment; filename="{row["filename"]}"'
            if ext in FORCE_DOWNLOAD_EXTS or mime not in SAFE_INLINE_MIMES
            else f'inline; filename="{row["filename"]}"')

    headers = {
        "Content-Disposition": disp,
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "X-Content-Type-Options": "nosniff",
    }

    log.info("download slug=%s ip=%s dl=%d", slug, ip, row["downloads"] + 1)
    response = FileResponse(path, media_type=mime, headers=headers)

    if burn:
        async def _burn():
            # 2 second delay so the response actually sends before we nuke the file
            await asyncio.sleep(2)
            path.unlink(missing_ok=True)
            async with get_db() as db:
                await db.execute("DELETE FROM files WHERE slug=?", (slug,))
                await db.commit()
            log.info("burned slug=%s", slug)
        asyncio.create_task(_burn())

    return response


# qr code

@app.get("/api/qr/{slug}")
async def qr_code(
    slug: str,
    request: Request,
    style: str = "dots",
    theme: str = "dark",
    size: int = 512,
    fg: Optional[str] = None,
    bg: Optional[str] = None,
    accent: Optional[str] = None,
):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")

    size = max(200, min(size, 1024))

    import re as _re
    if not _re.match(r"^[a-z]+$", style): style = "dots"
    if not _re.match(r"^[a-z]+$", theme): theme = "dark"

    hex_re = _re.compile(r"^#[0-9a-fA-F]{6}$")
    if fg and not hex_re.match(fg): fg = None
    if bg and not hex_re.match(bg): bg = None
    if accent and not hex_re.match(accent): accent = None

    try:
        from .qr import generate
        data = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate(
                f"{get_base_url(request)}/d/{slug}",
                style=style, theme=theme, size=size,
                fg=fg, bg=bg, accent=accent,
            )
        )
        return Response(
            data,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    except ImportError:
        raise HTTPException(503, "qrcode/pillow not installed: pip install qrcode[pil] pillow")
    except Exception as e:
        log.error("qr error slug=%s: %s", slug, e)
        raise HTTPException(500, "qr generation failed")


# delete

@app.delete("/api/delete/{slug}")
async def delete(
    slug: str,
    request: Request,
    token: Optional[str] = None,
    password: Optional[str] = None,
):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")

    ip = get_ip(request)
    if not limiter.allow(f"del:{ip}", 30):
        raise HTTPException(429, "too many requests")

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM files WHERE slug=?", (slug,))
        row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "not found")

    authorized = False
    if token and verify_delete_token(slug, token):
        authorized = True
    elif row["password_hash"] and password and pw_verify(password, row["password_hash"]):
        authorized = True

    if not authorized:
        log.warning("unauthorized delete slug=%s ip=%s", slug, ip)
        raise HTTPException(403, "provide delete token or correct password")

    Path(row["path"]).unlink(missing_ok=True)
    async with get_db() as db:
        await db.execute("DELETE FROM files WHERE slug=?", (slug,))
        await db.commit()

    log.info("deleted slug=%s ip=%s", slug, ip)
    return {"deleted": slug}


# collections

@app.post("/api/collection")
async def create_collection(
    request: Request,
    slugs: str = Form(...),
    title: str = Form(""),
    ttl: str = Form("24h"),
):
    ip = get_ip(request)
    if not limiter.allow(f"up:{ip}", RL_UPLOAD):
        raise HTTPException(429, "too many requests")

    slug_list = [s.strip() for s in slugs.split(",") if SLUG_RE.match(s.strip())]
    if not slug_list:
        raise HTTPException(400, "no valid slugs provided")
    if len(slug_list) > 50:
        raise HTTPException(400, "max 50 files per collection")

    ttl_sec = min(parse_ttl(ttl), MAX_TTL)
    cslug = new_slug()
    exp = time.time() + ttl_sec
    dtok = make_delete_token(cslug)

    async with get_db() as db:
        for s in slug_list:
            cur = await db.execute("SELECT slug FROM files WHERE slug=?", (s,))
            if not await cur.fetchone():
                raise HTTPException(404, f"file {s} not found")

        await db.execute(
            "INSERT INTO collections (slug,title,expires_at,created_at,ip,delete_token) VALUES (?,?,?,?,?,?)",
            (cslug, title or None, exp, time.time(), ip, dtok)
        )
        for s in slug_list:
            await db.execute(
                "INSERT INTO collection_files (collection_slug,file_slug) VALUES (?,?)",
                (cslug, s)
            )
        await db.commit()

    return {
        "slug": cslug,
        "url": f"{get_base_url(request)}/c/{cslug}",
        "files": len(slug_list),
        "expires_at": ts_iso(exp),
        "delete_token": dtok,
    }


@app.get("/api/collection/{slug}")
async def get_collection(slug: str, request: Request):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM collections WHERE slug=?", (slug,))
        col = await cur.fetchone()
        if not col or time.time() > col["expires_at"]:
            raise HTTPException(404, "collection not found or expired")

        cur = await db.execute(
            """SELECT f.* FROM files f
               JOIN collection_files cf ON cf.file_slug = f.slug
               WHERE cf.collection_slug = ?""",
            (slug,)
        )
        files = await cur.fetchall()

    return {
        "slug": slug,
        "title": col["title"],
        "expires_at": ts_iso(col["expires_at"]),
        "files": [
            {
                "slug": r["slug"],
                "url": f"{get_base_url(request)}/d/{r['slug']}",
                "filename": r["filename"],
                "size": r["size"],
                "mime": r["mime"],
            }
            for r in files
        ],
    }


# admin

@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    require_admin(request)
    async with get_db() as db:
        cur = await db.execute(
            "SELECT COUNT(*) as n, SUM(size) as s, SUM(downloads) as d FROM files WHERE expires_at > ?",
            (time.time(),)
        )
        row = await cur.fetchone()
        cur2 = await db.execute("SELECT COUNT(*) as n FROM files WHERE expires_at < ?", (time.time(),))
        exp = await cur2.fetchone()
    return {
        "active_files": row["n"] or 0,
        "total_size_bytes": row["s"] or 0,
        "total_downloads": row["d"] or 0,
        "expired_files": exp["n"] or 0,
        "version": "2.0.0",
        "base_url":         get_base_url(request),
    }


@app.get("/api/admin/files")
async def admin_files(request: Request, limit: int = 50, offset: int = 0):
    require_admin(request)
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM files ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (min(limit, 500), offset)
        )
        rows = await cur.fetchall()
    return [
        {
            "slug": r["slug"],
            "filename": r["filename"],
            "size": r["size"],
            "downloads": r["downloads"],
            "expires_at": ts_iso(r["expires_at"]),
            "ip": r["ip"],
            "is_paste": bool(r["is_paste"]),
        }
        for r in rows
    ]


@app.delete("/api/admin/files/{slug}")
async def admin_delete(slug: str, request: Request):
    require_admin(request)
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")
    async with get_db() as db:
        cur = await db.execute("SELECT path FROM files WHERE slug=?", (slug,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "not found")
        Path(row["path"]).unlink(missing_ok=True)
        await db.execute("DELETE FROM files WHERE slug=?", (slug,))
        await db.commit()
    log.info("admin deleted slug=%s", slug)
    return {"deleted": slug}


# health

@app.get("/health")
async def health():
    # TODO: add database connection status check to health probe, ne0k1r4 says we need it for uptime monitoring
    return {"status": "ok", "version": "2.0.0", "ts": int(time.time())}


@app.get("/api/stats")
async def public_stats():
    async with get_db() as db:
        cur = await db.execute(
            "SELECT COUNT(*) as n, COALESCE(SUM(size),0) as s FROM files WHERE expires_at > ?",
            (time.time(),)
        )
        row = await cur.fetchone()
    return {"files": row["n"], "size_bytes": row["s"], "version": "2.0.0"}


# web routes

TEMPLATE_DIR = Path(__file__).parent.parent / "web" / "templates"


def get_template(filename: str) -> str:
    path = TEMPLATE_DIR / filename
    if not path.exists():
        raise HTTPException(500, f"Template {filename} not found")
    return path.read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
async def index():
    return get_template("index.html")


@app.get("/d/{slug}", response_class=HTMLResponse)
async def download_page(slug: str):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")
    return get_template("download.html")


@app.get("/c/{slug}", response_class=HTMLResponse)
async def collection_page(slug: str):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")
    return get_template("collection.html")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return get_template("admin.html")


@app.get("/qr/{slug}", response_class=HTMLResponse)
async def qr_page(slug: str):
    if not SLUG_RE.match(slug):
        raise HTTPException(404, "not found")
    return get_template("qr.html")
