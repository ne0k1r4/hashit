# hashit

Zero-friction file sharing. Drop a file, get a link.

```
$ hashit send ./dump.sql.gz --expires 1h --max-downloads 1
  uploading dump.sql.gz (142 MB)... done

  https://hashit.io/x7k2m9ab

  file     dump.sql.gz
  size     142.0 MB
  expires  2026-06-08 14:30 UTC
  limit    1 download
```

---

## features

- **no account** — upload and share instantly
- **auto-delete** — files expire from 15 minutes to 7 days
- **burn after read** — set max downloads to 1
- **password protection** — PBKDF2-SHA256, constant-time comparison
- **pastes** — share code, logs, configs like a fast private pastebin
- **collections** — bundle multiple files under one link
- **upload from URL** — fetch and re-share remote files
- **QR codes** — generate QR for any link
- **admin dashboard** — manage files, view stats
- **full REST API** — swagger docs at `/api/docs`
- **self-hostable** — one Docker command

---

## cli

```sh
# install
pip install hashit

# or run directly (zero dependencies)
python cli/hashit.py send ./file.txt
```

```sh
# send a file
hashit send ./report.pdf

# burn after read
hashit send ./secret.zip --max-downloads 1 --expires 1h

# password protect
hashit send ./private.tar.gz --password hunter2 --expires 7d

# share code / text
hashit paste "$(cat config.yml)" --name config.yml
cat error.log | hashit paste -

# upload from URL
hashit url https://example.com/file.zip

# file info
hashit info x7k2m9ab

# delete (needs token from upload response)
hashit delete x7k2m9ab --token <delete_token>

# generate QR code
hashit qr x7k2m9ab
```

Point at your own server:

```sh
export HASHIT_SERVER=https://your-domain.com
hashit send ./file
```

---

## self-hosting

**docker:**

```sh
git clone https://github.com/ne0k1r4/hashit
cd hashit
cp .env.example .env
# edit .env — set HASHIT_BASE_URL and HASHIT_SECRET
docker compose up -d
```

**manual:**

```sh
git clone https://github.com/ne0k1r4/hashit
cd hashit
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env
./run.sh
```

**environment variables:**

| variable | default | description |
|---|---|---|
| `HASHIT_BASE_URL` | `http://localhost:8000` | public URL for generated links |
| `HASHIT_UPLOAD_DIR` | `/tmp/hashit_uploads` | file storage directory |
| `HASHIT_MAX_SIZE_MB` | `512` | max upload size |
| `HASHIT_MAX_TTL_HOURS` | `168` | max expiry (7 days) |
| `HASHIT_SECRET` | random | secret key for tokens |
| `HASHIT_ADMIN_TOKEN` | random (printed on startup) | admin dashboard token |
| `HASHIT_BEHIND_PROXY` | `0` | set to `1` if behind nginx |
| `HASHIT_RL_UPLOAD` | `20` | upload rate limit (per minute) |
| `HASHIT_RL_DOWNLOAD` | `120` | download rate limit (per minute) |

**nginx:**

```sh
cp nginx/hashit.conf /etc/nginx/sites-available/hashit
# edit server_name and SSL paths
ln -s /etc/nginx/sites-available/hashit /etc/nginx/sites-enabled/
certbot --nginx -d your-domain.com
nginx -t && systemctl reload nginx
```

---

## api

```
POST   /api/upload          upload a file
POST   /api/paste           share text/code
POST   /api/upload-url      upload from URL
GET    /api/info/:slug      file metadata
GET    /api/download/:slug  download file
DELETE /api/delete/:slug    delete (token or password)
GET    /api/qr/:slug        QR code (PNG)
POST   /api/collection      bundle files under one link
GET    /api/collection/:slug collection info
GET    /api/stats           public stats
GET    /health              health check
GET    /api/docs            swagger UI
```

admin (requires `X-Admin-Token` header or `?token=` query):

```
GET    /api/admin/stats
GET    /api/admin/files
DELETE /api/admin/files/:slug
```

---

## security

- passwords hashed with PBKDF2-HMAC-SHA256, 200k iterations, random 32-byte salt
- delete tokens are HMAC-SHA256 (slug + server secret)
- rate limiting per IP on all endpoints
- security headers: CSP, HSTS, X-Frame-Options, X-Content-Type-Options
- dangerous extensions (.exe, .sh, .php, etc.) blocked on upload
- path traversal protection, null byte injection blocked
- no server version fingerprinting
- WAL-mode SQLite with proper indexes
- atomic file writes

---

## tests

```sh
pip install pytest httpx pytest-asyncio
pytest tests/ -v
```

---

## license

MIT — built by [ne0k1r4](https://github.com/ne0k1r4) · india 🇮🇳
