"""Isolated real run of kr_stats_watch.run (no private store). Short lines only."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kr_stats_watch as k  # noqa: E402

cfg = json.loads(k.CONFIG.read_text(encoding="utf-8"))
now = k.now_kst()
doc = k.run(cfg, now=now, previous=None, ecos_key=os.environ.get("ECOS_API_KEY", "").strip(), kosis_key=os.environ.get("KOSIS_API_KEY", "").strip())
OUT = [json.dumps(c, ensure_ascii=False) for c in doc["checks"]]
for s in []:
    m = s.get("summary") or {}
    OUT.append(f"S {s['label']} [{s['officialName']}|{s['unit']}] {m.get('period')} {m.get('value')} mom{m.get('mom')} yoy{m.get('yoy')} hi {m.get('high')} lo {m.get('low')} sig={[x['text'] for x in s['signals']]}")
kd = doc["kaida"]
OUT.append(f"KAIDA {kd['period']} total {kd['total']} " + " ; ".join(f"{b['brand']} {b['units']:.0f} {b['rank']}위(직전 {b['prevRank']}) yoy{b['yoy']}" for b in kd["brands"]))
OUT.append(f"KAIDA sig {[x['text'] for x in kd['signals']]}")
OUT.append(f"size {len(json.dumps(doc, ensure_ascii=False))}")
clean = [o.replace("\r", " ").replace("\n", " ").replace("%", "pct").replace("::", ": :") for o in OUT]
for i in range(0, len(clean), 4):
    print(f"::notice title=run-{i // 4:02d}::" + " | ".join(clean[i:i + 4])[:3900])
