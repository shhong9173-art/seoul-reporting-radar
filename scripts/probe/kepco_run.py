"""Isolated real call of kr_signals_watch.kepco with KEPCO_API_KEY (no private store). Key never printed."""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kr_signals_watch as k  # noqa: E402

key = os.environ.get("KEPCO_API_KEY", "").strip()
OUT = [f"key {'set' if key else 'missing'} len={len(key)}"]
if key:
    h = k.Http()
    now = k.now_kst()
    import datetime as dt
    fr = (now.date() - dt.timedelta(days=14)).strftime("%Y%m%d")
    r, e = h.call("GET", k.KEPCO_API, params={"noticeBeginDate": fr, "noticeEndDate": now.date().strftime("%Y%m%d"), "apiKey": key, "returnType": "json"}, timeout=90)
    if e:
        OUT.append(f"raw call error {e}")
    else:
        try:
            body = r.json()
        except ValueError:
            body = None
            OUT.append(f"not json {len(r.text)} {re.sub(r'[A-Za-z0-9]{30,}', '<long>', r.text[:200])}")
        if isinstance(body, dict):
            data = body.get("data")
            OUT.append(f"keys {list(body)[:6]} rows {len(data) if isinstance(data, list) else type(data).__name__} {str(body)[:200] if not isinstance(data, list) else ''}")
            if isinstance(data, list) and data:
                OUT.append("fields " + ",".join(sorted(data[0])[:60]))
                OUT.append("companies " + json.dumps(sorted({str(d.get('companyId')) for d in data})))
                OUT.append("sample " + json.dumps({x: str(data[0].get(x))[:50] for x in ("companyId", "no", "name", "presumedPrice", "presumedAmount", "noticeDate", "progressState", "purchaseType", "competitionType", "bidType", "placeName")}, ensure_ascii=False))
    rows, events, check = k.kepco(json.loads(k.CONFIG.read_text(encoding="utf-8")), key, now, None, h)
    OUT.append(json.dumps(check, ensure_ascii=False))
    for x in rows[:12]:
        OUT.append(f"{x['noticeDate']} {x['company']} {x['state']} {x['price']} big={x['big']} | {x['name'][:70]}")
clean = [o.replace("\r", " ").replace("\n", " ").replace("%", "pct").replace("::", ": :") for o in OUT]
for i in range(0, len(clean), 4):
    print(f"::notice title=kepco-{i // 4:02d}::" + " | ".join(clean[i:i + 4])[:3900])
