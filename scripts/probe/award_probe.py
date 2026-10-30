"""probe: carsales.collect를 실제 현대차·기아 IR 엑셀로 돌려 계열 수·최근 달 신호(공개 자료)를 본다. 저장하지 않음."""
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import carsales as cs  # noqa: E402
import kr_stats_watch as w  # noqa: E402

out = []
try:
    now = dt.datetime.now(w.KST)
    block, events, check = cs.collect(None, now, w.Http(), baseline=True)
    out.append(f"check {json.dumps(check, ensure_ascii=False)}")
    out.append(f"series {len(block['series'])} size {len(json.dumps(block, ensure_ascii=False))} latest {block['latest']}")
    for u, f in block["files"].items():
        out.append(f"file {f['maker']} {f['kind']} {f['year']} latest {f['latest']} lm {f['lastModified']} {u[-60:]}")
    by = {}
    for s in block["series"]:
        by[(s["maker"], s["kind"], s["scope"])] = by.get((s["maker"], s["kind"], s["scope"]), 0) + 1
    out.append("scopes " + "; ".join(f"{k[0]}/{k[1]}/{k[2]}={v}" for k, v in sorted(by.items())))
    for key, ym in sorted(block["latest"].items()):
        maker, kind = key.split(":")
        for back in (0, 1, 2, 3):
            m = cs.ym_add(ym, -back)
            sig = cs.signals(block["series"], maker, kind, m)
            out.append(f"== {key} {m}: {len(sig)}")
            for x in sig[:9]:
                out.append(f"  {x['tier']} {x['signal']} | {x['text']}")
except Exception:  # noqa: BLE001
    out.append("ERR " + traceback.format_exc()[-1200:])
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
