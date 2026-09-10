#!/usr/bin/env sh
# Local live-demo helper. Does not fake results. Doctor itself needs no GPU.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "ToolCall Doctor local demo"
echo "Doctor POSTs to your runtime. It does not require a GPU of its own."
echo

if [ "${1:-}" = "--dry-run" ]; then
  exec toolcall-doctor diagnose --example enum-keyword --dry-run -o out
fi

URL="${TOOLCALL_DOCTOR_URL:-http://127.0.0.1:11434/v1/chat/completions}"
ORIGIN=$(python -c "from urllib.parse import urlparse; p=urlparse('$URL'); print(p.scheme + '://' + p.netloc)")

if ! python -c "import httpx,sys; r=httpx.get('$ORIGIN/api/version', timeout=3); sys.exit(0 if r.status_code==200 else 1)" 2>/dev/null; then
  echo "error: cannot reach $ORIGIN" >&2
  echo "  why: Ollama (or TOOLCALL_DOCTOR_URL) is not accepting connections." >&2
  echo "  do:  start \`ollama serve\`, or run: toolcall-doctor demo -o out" >&2
  exit 3
fi

if ! python -c "import httpx,sys; names=[m.get('name') for m in httpx.get('$ORIGIN/api/tags', timeout=5).json().get('models') or []]; sys.exit(0 if any(n=='llama3.2:3b' or (n or '').startswith('llama3.2') for n in names) else 1)" 2>/dev/null; then
  echo "error: model llama3.2:3b is not loaded at $ORIGIN" >&2
  echo "  do:  ollama pull llama3.2:3b" >&2
  exit 3
fi

echo "Runtime reachable. Starting bundled deterministic live demo (enum-keyword, -n 1)."
echo "This is not external validation."
exec toolcall-doctor diagnose --example enum-keyword -n 1 -o out --url "$URL"
