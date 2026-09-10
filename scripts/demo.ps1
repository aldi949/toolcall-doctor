# Local live-demo helper. Does not fake results. Doctor itself needs no GPU.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

Write-Host "ToolCall Doctor local demo"
Write-Host "Doctor POSTs to your runtime. It does not require a GPU of its own."
Write-Host ""

if ($args -contains "--dry-run") {
    & toolcall-doctor diagnose --example enum-keyword --dry-run -o out
    exit $LASTEXITCODE
}

$Url = if ($env:TOOLCALL_DOCTOR_URL) { $env:TOOLCALL_DOCTOR_URL } else { "http://127.0.0.1:11434/v1/chat/completions" }

try {
    $code = python -c "import httpx,sys; from urllib.parse import urlparse; u=sys.argv[1]; o=urlparse(u); r=httpx.get(o.scheme+'://'+o.netloc+'/api/version', timeout=3); sys.exit(0 if r.status_code==200 else 1)" $Url
    if ($LASTEXITCODE -ne 0) { throw "probe failed" }
} catch {
    Write-Host "error: cannot reach runtime at $Url" -ForegroundColor Red
    Write-Host "  why: Ollama (or TOOLCALL_DOCTOR_URL) is not accepting connections."
    Write-Host "  do:  start ollama serve, or run: toolcall-doctor demo -o out"
    exit 3
}

python -c "import httpx,sys; from urllib.parse import urlparse; u=sys.argv[1]; o=urlparse(u); names=[m.get('name') for m in httpx.get(o.scheme+'://'+o.netloc+'/api/tags', timeout=5).json().get('models') or []]; sys.exit(0 if any(n=='llama3.2:3b' or (n or '').startswith('llama3.2') for n in names) else 1)" $Url
if ($LASTEXITCODE -ne 0) {
    Write-Host "error: model llama3.2:3b is not loaded" -ForegroundColor Red
    Write-Host "  do:  ollama pull llama3.2:3b"
    exit 3
}

Write-Host "Runtime reachable. Starting bundled deterministic live demo (enum-keyword, -n 1)."
Write-Host "This is not external validation."
& toolcall-doctor diagnose --example enum-keyword -n 1 -o out --url $Url
exit $LASTEXITCODE
