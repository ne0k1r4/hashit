"""
database layer — sqlite via aiosqlite
WAL mode, proper indexes, connection pooling
"""

import os
import time
import sqlite3
import contextlib
import aiosqlite
from pathlib import Path
from typing import Optional

DB_PATH = Path(os.getenv("HASHIT_DB_PATH", str(Path(__file__).parent.parent / "data" / "hashit.db")))


def get_sync_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@contextlib.asynccontextmanager
async def get_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as con:
        con.row_factory = aiosqlite.Row
        yield con


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
    slug          TEXT PRIMARY KEY,
    filename      TEXT NOT NULL,
    path          TEXT NOT NULL,
    size          INTEGER NOT NULL,
    mime          TEXT NOT NULL,
    password_hash TEXT,
    expires_at    REAL NOT NULL,
    max_downloads INTEGER,
    downloads     INTEGER NOT NULL DEFAULT 0,
    is_paste      INTEGER NOT NULL DEFAULT 0,
    delete_token  TEXT NOT NULL,
    created_at    REAL NOT NULL,
    ip            TEXT,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS collections (
    slug         TEXT PRIMARY KEY,
    title        TEXT,
    expires_at   REAL NOT NULL,
    created_at   REAL NOT NULL,
    ip           TEXT,
    delete_token TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_files (
    collection_slug TEXT NOT NULL REFERENCES collections(slug) ON DELETE CASCADE,
    file_slug       TEXT NOT NULL REFERENCES files(slug) ON DELETE CASCADE,
    PRIMARY KEY (collection_slug, file_slug)
);

CREATE INDEX IF NOT EXISTS idx_files_expires ON files(expires_at);
CREATE INDEX IF NOT EXISTS idx_files_ip      ON files(ip);
"""


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = get_sync_db()
    con.executescript(SCHEMA)
    con.commit()
    con.close()


async def purge_expired() -> int:
    async with get_db() as db:
        cur  = await db.execute(
            "SELECT slug, path FROM files WHERE expires_at < ?", (time.time(),)
        )
        rows = await cur.fetchall()
        for row in rows:
            Path(row["path"]).unlink(missing_ok=True)
        if rows:
            await db.execute("DELETE FROM files WHERE expires_at < ?", (time.time(),))
            await db.execute("DELETE FROM collections WHERE expires_at < ?", (time.time(),))
            await db.commit()
    return len(rows)
