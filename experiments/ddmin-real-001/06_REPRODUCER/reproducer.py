import json, urllib.error, urllib.request
from pathlib import Path
URL = 'http://127.0.0.1:11434/v1/chat/completions'
PAYLOAD = json.loads(Path(__file__).with_name('payload.json').read_text(encoding='utf-8'))
req = urllib.request.Request(URL, data=json.dumps(PAYLOAD).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        status = resp.status
except urllib.error.HTTPError as e:
    status = e.code
    body = e.read()
print(status)
print(body.decode('utf-8', errors='replace'))
