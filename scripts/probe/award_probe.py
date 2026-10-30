"""격리 탐침 31g: kr_workforce_watch.run 실제 조회(저장 안 함) — 첫 실행(기준선)과 이어 실행(채우기·지난달 비교). 키 값 미출력."""
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_workforce_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
cfg = json.loads((Path(__file__).resolve().parents[2] / "data" / "workforce_watch.json").read_text(encoding="utf-8"))
api = w.Api((os.environ.get("KR_FUEL_API_KEY") or "").strip())
out = []
t0 = time.time()
now = dt.datetime.now(KST)
doc = w.run(cfg, now=now, previous=None, api=api, budget=11 * 60)
out.append(f"1차 {time.time() - t0:.0f}s 상태 {doc['status']} 자료 {doc['month']} scan {doc['scanStatus']} API {doc['apiCalls']} checks={doc['checks']}")
by = {}
for s in doc["sites"]:
    by.setdefault(s["company"], []).append(f"{s['name'][:22]}[{s['region']}]{(s['history'].get(doc['month']) or {}).get('members')}명/{len(s['history'])}달")
out.append("자사 " + " ‖ ".join(f"{c}: {', '.join(v[:5])}{' 외 ' + str(len(v) - 5) if len(v) > 5 else ''}" for c, v in by.items()))
missing = [c["company"] for c in cfg["companies"] if c["company"] not in by]
out.append(f"자사 못 찾음 {missing}")
tiers = {}
for p in doc["projects"]:
    tiers.setdefault(p["tier"], []).append(f"{p['company']}:{p['name'][:60]}")
out.append(f"공사 현장 보관 {len(doc['projects'])} 본 이름 {len(doc['projectSeen'])} A {len(tiers.get('A', []))} B {len(tiers.get('B', []))}")
out.append("A 예 " + " ‖ ".join(tiers.get("A", [])[:25]))
t1 = time.time()
doc2 = w.run(cfg, now=now + dt.timedelta(hours=1), previous=doc, api=api, budget=6 * 60)
filled = sum(1 for s in doc2["sites"] if len(s["history"]) >= 2)
out.append(f"2차 {time.time() - t1:.0f}s 상태 {doc2['status']} API 누적 {doc2['apiCalls']} 2달 이상 {filled}/{len(doc2['sites'])} checks={doc2['checks']}")
out.append("이벤트 " + " ‖ ".join(f"{e['tier']} {e['kind']} {e['text'][:160]}" for e in doc2["events"][:12]))
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
