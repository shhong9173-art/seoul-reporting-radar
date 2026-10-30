"""probe: overseas_award_watch.pcc()를 실제 g0v 미러로 — 최근 400일 창에서 출입처 낙찰과 상세(금액·원산지). 공개 자료, 저장하지 않음."""
import datetime as dt
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overseas_award_watch as w  # noqa: E402

out = []
try:
    now = dt.datetime.now(w.KST)
    import time; items, checks = w.pcc(now - dt.timedelta(days=400), set(), sleep=time.sleep)
    out.append("checks " + "; ".join(f"{c['query']} {c['status']} {c.get('returned', c.get('error'))}/{c.get('matched', '')}" for c in checks))
    for it in sorted(items, key=lambda x: x["published"], reverse=True):
        out.append(f"{it['published']} {w.tier_of(it)} {it['kind']} {it['company']} | {it['buyer']} | {it['title'][:200]} | {it['currency']} {it['value']} ({it.get('priceKind')}) "
                   f"| 결정 {it.get('concluded')} | {it.get('category')} | err {it.get('detailError')} | {it['url']}")
except Exception:  # noqa: BLE001
    out.append("ERR " + traceback.format_exc()[-1500:])
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
