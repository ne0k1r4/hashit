#!/bin/bash
set -e
cd "$(dirname "$0")"

G='\033[32m'; Y='\033[33m'; R='\033[31m'; C='\033[36m'; B='\033[1m'; RST='\033[0m'

echo ""
echo -e "${C}${B}  #hashit v2.0${RST}"
echo -e "${R}  ne0k1r4 · india${RST}"
echo ""

# venv
if [ ! -d venv ]; then
  echo -e "  ${Y}→${RST} creating virtual environment..."
  python -m venv venv
fi
source venv/bin/activate

# deps
if ! python -c "import fastapi" 2>/dev/null; then
  echo -e "  ${Y}→${RST} installing dependencies..."
  pip install -r requirements.txt -q
fi

# upload dir
export HASHIT_UPLOAD_DIR="${HASHIT_UPLOAD_DIR:-$HOME/hashit_uploads}"
mkdir -p "$HASHIT_UPLOAD_DIR"

PORT=8000

# ── cloudflared tunnel ────────────────────────────────────────
if command -v cloudflared &>/dev/null; then
  echo -e "  ${Y}→${RST} starting cloudflared tunnel..."
  cloudflared tunnel --url http://localhost:$PORT --no-autoupdate \
    > /tmp/hashit_cf.log 2>&1 &
  CF_PID=$!

  for i in $(seq 1 20); do
    CF_URL=$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' \
             /tmp/hashit_cf.log 2>/dev/null | head -1)
    [ -n "$CF_URL" ] && break
    sleep 1
  done

  if [ -n "$CF_URL" ]; then
    export HASHIT_BASE_URL="$CF_URL"
    echo ""
    echo -e "  ${G}${B}✓ public URL: ${CF_URL}${RST}"
    echo ""
  else
    echo -e "  ${Y}⚠ cloudflared started but URL not detected yet${RST}"
    export HASHIT_BASE_URL="http://localhost:$PORT"
  fi

  trap "kill $CF_PID 2>/dev/null; exit" INT TERM
else
  echo -e "  ${Y}⚠ cloudflared not found — links will use localhost${RST}"
  echo -e "  ${Y}  install: yay -S cloudflared${RST}"
  export HASHIT_BASE_URL="${HASHIT_BASE_URL:-http://localhost:$PORT}"
fi

echo -e "  ${G}✓${RST} upload dir : $HASHIT_UPLOAD_DIR"
echo -e "  ${G}✓${RST} local      : http://localhost:$PORT"
echo -e "  ${G}✓${RST} api docs   : http://localhost:$PORT/api/docs"
echo -e "  ${G}✓${RST} admin      : http://localhost:$PORT/admin"
echo ""

uvicorn server.main:app \
  --host 0.0.0.0 \
  --port $PORT \
  --log-level warning \
  --reload
