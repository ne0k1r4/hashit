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
The portal will be live locally at `http://localhost:8000`.

### Cloudflare Integration (Sharing / Public Access)

`hashit` has built-in Cloudflare Tunnel integration allowing zero-configuration sharing:

* **Quick Tunnel (Free Random Domain):**
  If `TUNNEL_TOKEN` is left empty in `.env`, starting the container automatically spins up a Cloudflare Quick Tunnel. Check the docker logs to retrieve your temporary random URL:
  ```sh
  docker compose logs tunnel
  ```
  *(Example URL: `https://something-random.trycloudflare.com`)*
  
* **Custom Domain (Named Tunnel):**
  1. Create a tunnel in your Cloudflare Zero Trust Dashboard.
  2. Map your custom subdomain (e.g., `hashit.yourdomain.com`) to the internal service path `http://hashit:8000`.
  3. Copy your Cloudflare Tunnel Token and add it to `.env`:
     ```env
     TUNNEL_TOKEN=your_cloudflare_tunnel_token_here
     ```
  4. Run `docker compose up -d` to connect securely under your domain.

## Testing

```sh
pip install pytest httpx pytest-asyncio
pytest tests/ -v
```

## License

MIT — built with love by [ne0k1r4](https://github.com/ne0k1r4)
