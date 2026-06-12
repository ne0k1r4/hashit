import io, time, pytest, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport

@pytest.fixture(autouse=True)
def setup(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("HASHIT_UPLOAD_DIR", str(tmp_path / "uploads"))
    import server.db as db_mod
    db_mod.DB_PATH = tmp_path / "test.db"
    (tmp_path / "uploads").mkdir()
    db_mod.init_db()

@pytest.mark.asyncio
async def test_health():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health")
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_upload_download():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/upload",
            files={"file": ("hello.txt", b"hello world", "text/plain")},
            data={"ttl": "1h"})
        assert r.status_code == 200
        slug = r.json()["slug"]
        r2 = await c.get(f"/api/download/{slug}")
        assert r2.status_code == 200
        assert r2.content == b"hello world"

@pytest.mark.asyncio
async def test_password():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/upload",
            files={"file": ("s.txt", b"secret", "text/plain")},
            data={"ttl": "1h", "password": "hunter2"})
        slug = r.json()["slug"]
        assert (await c.get(f"/api/download/{slug}")).status_code == 401
        assert (await c.get(f"/api/download/{slug}?password=wrong")).status_code == 403
        assert (await c.get(f"/api/download/{slug}?password=hunter2")).status_code == 200

@pytest.mark.asyncio
async def test_burn_after_read():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/upload",
            files={"file": ("once.txt", b"burn", "text/plain")},
            data={"ttl": "1h", "max_downloads": "1"})
        slug = r.json()["slug"]
        assert (await c.get(f"/api/download/{slug}")).status_code == 200
        assert (await c.get(f"/api/download/{slug}")).status_code in (404, 410)

@pytest.mark.asyncio
async def test_blocked_ext():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/upload",
            files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
            data={"ttl": "1h"})
        assert r.status_code == 415

@pytest.mark.asyncio
async def test_delete():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r    = await c.post("/api/upload",
            files={"file": ("d.txt", b"bye", "text/plain")},
            data={"ttl": "1h"})
        d    = r.json()
        slug = d["slug"]
        tok  = d["delete_token"]
        assert (await c.delete(f"/api/delete/{slug}?token={tok}")).status_code == 200
        assert (await c.get(f"/api/download/{slug}")).status_code == 404

@pytest.mark.asyncio
async def test_paste():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/paste",
            data={"content": "print('hi')", "filename": "hi.py", "ttl": "1h"})
        assert r.status_code == 200
        slug = r.json()["slug"]
        assert (await c.get(f"/api/download/{slug}")).status_code == 200

@pytest.mark.asyncio
async def test_static_files():
    from server.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/static/css/style.css")
        assert r.status_code == 200
        assert "text/css" in r.headers.get("content-type", "")
        r_js = await c.get("/static/js/common.js")
        assert r_js.status_code == 200
        assert "javascript" in r_js.headers.get("content-type", "")

