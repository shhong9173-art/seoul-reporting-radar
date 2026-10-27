import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kr_signals_watch as k  # noqa: E402

cfg = json.loads(k.CONFIG.read_text(encoding="utf-8"))
h = k.Http()
r, e = h.call("GET", k.MOTIR_LIST, params={"pageIndex": 1})
rows = k.parse_motir_list(r.text)
OUT = [f"status {e} len {len(r.text)} rows {len(rows)}", json.dumps(rows[:3], ensure_ascii=False)[:1500]]
i = r.text.find('data-cell-header="제목"')
OUT.append(r.text[i:i + 700])
items, check = k.motir(cfg, k.now_kst(), None, k.Http())
OUT.append(json.dumps(check, ensure_ascii=False))
for x in items[:14]:
    t = x.get("trade")
    OUT.append(f"{x['date']} [{x['kind']}|{x['dept']}] {x['title'][:70]} co={x['companies']} emb={x['embargo']} trade={json.dumps(t, ensure_ascii=False)[:300] if t else None}")
clean = [o.replace("\r", " ").replace("\n", " ").replace("%", "pct").replace("::", ": :") for o in OUT]
for i in range(0, len(clean), 5):
    print(f"::notice title=motir-{i // 5:02d}::" + " | ".join(clean[i:i + 5])[:3900])
