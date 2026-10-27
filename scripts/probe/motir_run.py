import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kr_signals_watch as k  # noqa: E402

cfg = json.loads(k.CONFIG.read_text(encoding="utf-8"))
items, check = k.motir(cfg, k.now_kst(), None, k.Http())
OUT = [json.dumps(check, ensure_ascii=False)]
for x in items[:14]:
    t = x.get("trade")
    OUT.append(f"{x['date']} [{x['kind']}|{x['dept']}] {x['title'][:70]} co={x['companies']} emb={x['embargo']} trade={json.dumps(t, ensure_ascii=False)[:300] if t else None}")
clean = [o.replace("\r", " ").replace("\n", " ").replace("%", "pct").replace("::", ": :") for o in OUT]
for i in range(0, len(clean), 5):
    print(f"::notice title=motir-{i // 5:02d}::" + " | ".join(clean[i:i + 5])[:3900])
