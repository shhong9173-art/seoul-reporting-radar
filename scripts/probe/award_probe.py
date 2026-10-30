"""격리 탐침 47d: kr_stack_watch.run 실제 조회 한 번(저장 안 함, 키 값 미출력) — 잡힌 사업장·배출구 수·시간."""
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_stack_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
cfg = json.loads((Path(__file__).resolve().parents[2] / "data" / "stack_watch.json").read_text(encoding="utf-8"))
t0 = time.time()
doc = w.run(cfg, now=dt.datetime.now(KST), key=(os.environ.get("KR_FUEL_API_KEY") or "").strip())
out = [f"{time.time() - t0:.0f}s 상태 {doc['status']} checks={doc['checks']} 크기 {len(json.dumps(doc, ensure_ascii=False)) // 1024}KB",
       "사업장 " + " | ".join(f"{s['company']}:{s['name']}[{len(s['stacks'])}]" for s in doc["sites"])]
missing = [c["company"] for c in cfg["companies"] if c["company"] not in {s["company"] for s in doc["sites"]}]
out.append(f"못 찾음 {missing}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
