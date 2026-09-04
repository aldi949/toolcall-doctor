import json, sys
from pathlib import Path

here = Path(__file__).resolve().parent
engine = next(p / "engine" for p in [here, *here.parents] if (p / "engine").is_dir())
sys.path.insert(0, str(engine))
from execute import post
from behavioral_oracle import evaluate
p=json.loads(Path(__file__).with_name('payload.json').read_text(encoding='utf-8'))
out=Path(sys.argv[1])
exe=post(p, out)
ora=evaluate(exe['status'], exe['text'], p)
(out/'oracle.json').write_text(json.dumps(ora, indent=2)+'\n', encoding='utf-8')
print(ora.get('http_status'))
