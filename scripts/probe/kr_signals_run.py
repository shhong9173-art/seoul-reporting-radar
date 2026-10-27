"""Isolated real run of kr_signals_watch.run (no private store, no repo writes). Prints counts and short lines only."""
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kr_signals_watch as k  # noqa: E402

OUT = []
cfg = json.loads(k.CONFIG.read_text(encoding="utf-8"))
now = k.now_kst()
doc = k.run(cfg, now=now, previous=None, kepco_key=os.environ.get("KEPCO_API_KEY", "").strip())
for c in doc["checks"]:
    OUT.append(json.dumps(c, ensure_ascii=False))
OUT.append(f"decisions kept {len(doc['decisions'])} seen {len(doc['ftcSeen'])}")
for d in doc["decisions"][:25]:
    ms = "; ".join(f"{m['company']}={m['role']}{'(관련)' if m['related'] else ''}{' ' + ','.join(m['orderAmounts']) if m['orderAmounts'] else ''}" for m in d["mentions"])
    OUT.append(f"FTC {d['decidedOn']} file {d.get('fileDate')} {d['action']} {d['decisionNo']} [{ms}] {d['name'][:70]} flags={d['flags']}")
for p in doc["prices"]:
    s = p.get("summary") or {}
    OUT.append(f"PX {p['name']} {p['basis']} {p['unit']} src={p.get('source')} {s.get('date')} {s.get('price')} d{s.get('day')} w{s.get('week')} m{s.get('month')} ytd{s.get('ytd')} "
               f"stock {s.get('stock')} sm{s.get('stockMonth')} hi {s.get('high', {}).get('date')}:{s.get('high', {}).get('price')} lo {s.get('low', {}).get('date')}:{s.get('low', {}).get('price')} "
               f"sig={[x['text'] for x in p['signals']]}")
OUT.append(f"events {len(doc['events'])} size {len(json.dumps(doc, ensure_ascii=False))}")
for e in doc["events"][:10]:
    OUT.append(f"EV {e['text']}")
clean = [o.replace("\r", " ").replace("\n", " ").replace("%", "pct").replace("::", ": :") for o in OUT]
for i in range(0, len(clean), 5):
    print(f"::notice title=run-{i // 5:02d}::" + " | ".join(clean[i:i + 5])[:3900])
