#!/usr/bin/env python3
# hashit cli (https://github.com/ne0k1r4/hashit)

import os
import sys
import json
import argparse
import mimetypes
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

SERVER = os.getenv("HASHIT_SERVER", "https://hashit.io")

# short names bc i got tired of typing RESET every time
R = "\033[0m"
B = "\033[1m"
D = "\033[2m"
G = "\033[32m"
RE = "\033[31m"
Y = "\033[33m"
C = "\033[36m"

def die(msg):
    # every cli needs a die(), fight me
    print(f"{RE}error:{R} {msg}", file=sys.stderr)
    sys.exit(1)

def fmt_size(n):
    # stolen from stackoverflow ngl
    for u in ["B","KB","MB","GB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def fmt_date(iso):
    return iso[:16].replace("T", " ") + " UTC"


class Multipart:
    # built this myself bc requests adds too many deps
    def __init__(self):
        import os as _os
        self.boundary = "hashit" + _os.urandom(8).hex()
        self._parts = []

    def add_field(self, name, val):
        self._parts.append(
            f'--{self.boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode()
        )

    def add_file(self, name, filename, data, mime="application/octet-stream"):
        hdr = (
            f'--{self.boundary}\r\n'
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f'Content-Type: {mime}\r\n\r\n'
        ).encode()
        self._parts.append(hdr + data + b"\r\n")

    def encode(self):
        return b"".join(self._parts) + f"--{self.boundary}--\r\n".encode()

    def content_type(self):
        return f"multipart/form-data; boundary={self.boundary}"


def api(endpoint, mp=None, method="POST"):
    url = f"{SERVER}{endpoint}"
    if mp:
        body = mp.encode()
        req = urllib.request.Request(url, data=body,
               headers={"Content-Type": mp.content_type()}, method=method)
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            detail = json.loads(body).get("detail", body)
        except (ValueError, AttributeError):
            detail = body
        die(f"{e.code} — {detail}")
    except Exception as e:
        die(str(e))


def cmd_send(args):
    # TODO: add a progress bar for CLI uploads, ne0k1r4 was talking about using tqdm or writing a simple custom bar
    path = Path(args.file)
    if not path.exists():
        die(f"file not found: {path}")

    size = path.stat().st_size
    print(f"  {D}uploading {B}{path.name}{R}{D} ({fmt_size(size)})...{R}", end="", flush=True)

    mp = Multipart()
    mp.add_file("file", path.name, path.read_bytes(),
                mimetypes.guess_type(str(path))[0] or "application/octet-stream")
    mp.add_field("ttl", args.expires)
    if args.password:
        mp.add_field("password", args.password)
    if args.max_downloads:
        mp.add_field("max_downloads", str(args.max_downloads))
    if args.note:
        mp.add_field("note", args.note)

    r = api("/api/upload", mp)
    print(f" {G}done{R}")

    if args.json:
        print(json.dumps(r, indent=2))
        return

    print()
    print(f"  {G}{B}{r['url']}{R}")
    print()
    print(f"  {D}file     {R}{r['filename']}")
    print(f"  {D}size     {R}{fmt_size(r['size'])}")
    print(f"  {D}expires  {R}{fmt_date(r['expires_at'])}")
    if r.get("protected"):
        print(f"  {D}password {R}{Y}protected{R}")
    if r.get("max_downloads"):
        print(f"  {D}limit    {R}{r['max_downloads']} downloads")
    print()
    print(f"  {D}curl -LO \"{r['url'].replace('/d/', '/api/download/')}\"{R}")
    print(f"  {D}delete token: {r['delete_token'][:16]}...{R}")
    print()


def cmd_paste(args):
    if args.text == "-" or (not args.text and not sys.stdin.isatty()):
        content = sys.stdin.read()
    elif args.text:
        content = args.text
    else:
        die("provide text or pipe via stdin: cat file.py | hashit paste -")

    mp = Multipart()
    mp.add_field("content", content)
    mp.add_field("filename", args.name)
    mp.add_field("ttl", args.expires)
    if args.password:
        mp.add_field("password", args.password)

    r = api("/api/paste", mp)

    if args.json:
        print(json.dumps(r, indent=2))
        return

    print()
    print(f"  {G}{B}{r['url']}{R}")
    print(f"  {D}expires {fmt_date(r['expires_at'])}{R}")
    print()


def cmd_url(args):
    print(f"  {D}fetching {args.url}...{R}", end="", flush=True)
    mp = Multipart()
    mp.add_field("url", args.url)
    mp.add_field("ttl", args.expires)
    if args.password:
        mp.add_field("password", args.password)
    r = api("/api/upload-url", mp)
    print(f" {G}done{R}")
    if args.json:
        print(json.dumps(r, indent=2))
        return
    print()
    print(f"  {G}{B}{r['url']}{R}")
    print(f"  {D}file {r['filename']} · {fmt_size(r['size'])}{R}")
    print()


def cmd_info(args):
    slug = args.slug.rstrip("/").split("/")[-1]
    url = f"{SERVER}/api/info/{slug}"
    if args.password:
        url += f"?password={urllib.parse.quote(args.password)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            r = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            die("not found or expired")
        if e.code == 401:
            die("password required (--password)")
        die(str(e.code))

    if args.json:
        print(json.dumps(r, indent=2))
        return

    print()
    print(f"  {D}filename  {R}{r['filename']}")
    print(f"  {D}size      {R}{fmt_size(r['size'])}")
    print(f"  {D}mime      {R}{r['mime']}")
    print(f"  {D}expires   {R}{fmt_date(r['expires_at'])}")
    print(f"  {D}downloads {R}{r['downloads']}" + (f"/{r['max_downloads']}" if r['max_downloads'] else ""))
    print(f"  {D}protected {R}{'yes' if r['protected'] else 'no'}")
    if r.get("note"):
        print(f"  {D}note      {R}{r['note']}")
    print()


def cmd_delete(args):
    slug = args.slug.rstrip("/").split("/")[-1]
    url = f"{SERVER}/api/delete/{slug}?token={urllib.parse.quote(args.token or '')}"
    if args.password:
        url += f"&password={urllib.parse.quote(args.password)}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=10):
            print(f"  {G}deleted{R} {slug}")
    except urllib.error.HTTPError as e:
        if e.code == 403:
            die("provide --token or --password")
        die(str(e.code))


def cmd_qr(args):
    slug = args.slug.rstrip("/").split("/")[-1]
    url = f"{SERVER}/api/qr/{slug}"
    out = Path(args.output or f"{slug}.png")
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            out.write_bytes(resp.read())
        print(f"  {G}saved{R} {out}")
    except Exception as e:
        die(str(e))


def main():
    # TODO: check HASHIT_SERVER env variable format on startup, sometimes i put a trailing slash and it breaks
    global SERVER
    p = argparse.ArgumentParser(
        prog="hashit",
        description="send files, get links.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  hashit send ./report.pdf
  hashit send ./dump.sql.gz --expires 1h --max-downloads 1
  hashit send ./video.mp4 --password s3cr3t --expires 7d
  hashit paste "$(cat config.yml)" --name config.yml
  cat error.log | hashit paste -
  hashit url https://example.com/file.zip
  hashit info x7k2m9ab
  hashit delete x7k2m9ab --token abc123
  hashit qr x7k2m9ab
""",
    )
    p.add_argument("--server", default=SERVER, metavar="URL",
                   help="server URL (default: $HASHIT_SERVER or https://hashit.io)")
    p.add_argument("--json", action="store_true", help="json output")

    sub = p.add_subparsers(dest="cmd", metavar="command")

    # send
    s = sub.add_parser("send", help="upload a file")
    s.add_argument("file")
    s.add_argument("--expires", default="24h", metavar="TTL", help="e.g. 1h, 7d")
    s.add_argument("--password", default=None)
    s.add_argument("--max-downloads", default=None, type=int)
    s.add_argument("--note", default=None)

    # paste
    pp = sub.add_parser("paste", help="share text or code")
    pp.add_argument("text", nargs="?", help="text to share (or - for stdin)")
    pp.add_argument("--name", default="paste.txt")
    pp.add_argument("--expires", default="24h", metavar="TTL")
    pp.add_argument("--password", default=None)

    # url
    pu = sub.add_parser("url", help="upload from URL")
    pu.add_argument("url")
    pu.add_argument("--expires", default="24h", metavar="TTL")
    pu.add_argument("--password", default=None)

    # info
    i = sub.add_parser("info", help="get file info")
    i.add_argument("slug")
    i.add_argument("--password", default=None)

    # delete
    d = sub.add_parser("delete", help="delete a file")
    d.add_argument("slug")
    d.add_argument("--token", default=None, help="delete token")
    d.add_argument("--password", default=None)

    # qr
    q = sub.add_parser("qr", help="generate QR code")
    q.add_argument("slug")
    q.add_argument("--output", default=None, metavar="FILE")

    args = p.parse_args()
    SERVER = args.server.rstrip("/")

    if args.cmd == "send":
        cmd_send(args)
    elif args.cmd == "paste":
        cmd_paste(args)
    elif args.cmd == "url":
        cmd_url(args)
    elif args.cmd == "info":
        cmd_info(args)
    elif args.cmd == "delete":
        cmd_delete(args)
    elif args.cmd == "qr":
        cmd_qr(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
