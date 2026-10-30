"""probe: 무역협회 수입규제DB 실제 목록·상세를 kita_watch 파서로(공개 자료, robots 허용). 목록 1 + 상세 최대 10회."""
import datetime as dt
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kita_watch as k  # noqa: E402

out = []
try:
    http = k.Http()
    cards = k.parse_cards(http.post(k.LIST, {"pageIndex": "1", "pageUnit": "50", "searchOrder": "2"}))
    out.append(f"cards {len(cards)}")
    for c in cards[:8]:
        out.append(f"  {c}")
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    s1, ev1, c1 = k.collect(None, now, http)
    out.append(f"baseline check {c1} events {len(ev1)} cases {len(s1['cases'])}")
    prev = {**s1, "cases": dict(s1["cases"])}
    # 시뮬레이션: 위에서 셋은 '처음 본 사건', 다음 다섯은 '갱신일이 바뀐 사건'으로
    for c in cards[:3]:
        prev["cases"].pop(c["tirId"], None)
    for c in cards[3:8]:
        prev["cases"][c["tirId"]] = dict(prev["cases"][c["tirId"]], updated="2000-01-01")
    s2, ev2, c2 = k.collect(prev, now, http)
    out.append(f"sim check {c2} events {len(ev2)}")
    for e in ev2:
        out.append(f"  {e['tier']} {e['kitaKind']} | {e['text'][:420]} | {e['url']}")
except Exception:  # noqa: BLE001
    out.append("ERR " + traceback.format_exc()[-1500:])
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
