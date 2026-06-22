# hashit

Zero-friction, waifu-guarded secure file sharing portal.

```sh
$ pip install hashit
$ hashit send ./file.txt --expires 1h --max-downloads 1
```

## Features

- **No Accounts Required** — Share files or paste snippets instantly.
- **Self-Destruct Options** — Configurable expiry (15m to 7d) and download limits (burn after read).
- **Waifu-Guarded Security** — PBKDF2-SHA256 password protection, HMAC delete tokens, and rate limits.
- **Artistic QR Designer** — Generate custom stylized QR codes for links.
- **Admin Control** — Dashboard to monitor stats and purge expired files.
- **REST API** — Fully documented OpenAPI endpoints at `/api/docs`.

## Quick Start

### CLI Usage

```sh
# Upload a file (burn after 1 download, expires in 1 hour)
hashit send ./secret.zip --max-downloads 1 --expires 1h

# Share text paste
hashit paste "hello world" --name paste.txt

# Retrieve info or delete
hashit info x7k2m9ab
hashit delete x7k2m9ab --token <delete_token>
```

### Self-Hosting (Docker)

1. Clone the repository and configure `.env`:
   ```sh
   git clone https://github.com/ne0k1r4/hashit && cd hashit
   cp .env.example .env
   ```
2. Run via Docker Compose:
   ```sh
   docker compose up -d
   ```
The portal will be live at `http://localhost:8000`.

## Testing

```sh
pip install pytest httpx pytest-asyncio
pytest tests/ -v
```

## License

MIT — built with love by [ne0k1r4](https://github.com/ne0k1r4)
