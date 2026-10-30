"""격리 탐침 31h: kr_workforce_watch 첫 실행(운영과 같은 22분 한도 대신 16분) — 공사 이름 묶음·A 목록·자사 사업장 상세 채움 정도(저장 안 함, 키 값 미출력)."""
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
doc = w.run(cfg, now=dt.datetime.now(KST), previous=None, api=api, budget=16 * 60)
have = sum(1 for s in doc["sites"] if doc["month"] in s["history"])
two = sum(1 for s in doc["sites"] if len(s["history"]) >= 2)
out.append(f"{time.time() - t0:.0f}s 상태 {doc['status']} scan {doc['scanStatus']} API {doc['apiCalls']} 자사 {len(doc['sites'])}(최신 달 {have}, 2달+ {two}) checks={doc['checks']}")
A = sorted([p for p in doc["projects"] if p["tier"] == "A"], key=lambda p: -p.get("sites", 1))
B = [p for p in doc["projects"] if p["tier"] == "B"]
out.append(f"공사 묶음 {len(doc['projects'])}(A {len(A)}, B {len(B)}) · 현장 이름 {len(doc['projectSeen'])}")
out.append("A " + " ‖ ".join(f"{p['company']}:{p['title'][:50]}[{p.get('sites', 1)}곳]" for p in A[:45]))
out.append("B 예 " + " ‖ ".join(f"{p['company']}:{p['title'][:40]}" for p in B[:20]))
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
