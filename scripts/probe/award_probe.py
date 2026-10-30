"""Probe 3: 바레인 입찰위원회 개찰 결과(Tender Opening Results) 웹 메서드 호출 형식 — 공개 자료, 저장하지 않음."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overseas_award_watch as w  # noqa: E402
import requests  # noqa: E402

out = []
S = requests.Session()
S.headers.update(w.UA)
try:
    r = S.get(w.BH_SITE + "/Tenders/OpenedBids/", timeout=60)
    t = r.text
    out.append(f"OpenedBids HTTP {r.status_code} len {len(t)}")
    for m in re.finditer(r"TenderBoardWebService\.aspx/(\w+)", t):
        s = max(0, m.start() - 500)
        out.append(f"\n-- call {m.group(1)}: " + re.sub(r"\s+", " ", t[s: m.end() + 900]))
        if len(out) > 8:
            break
    body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)))
    i = body.find("Opening Results")
    out.append("\ntext near: " + body[i: i + 1500] if i >= 0 else "\ntext: " + body[-1500:])
except Exception as e:  # noqa: BLE001
    out.append(f"error {type(e).__name__}: {str(e)[:200]}")
# try the web method with a few common payloads
for name, payload in [("GetOpenedTender", {}), ("GetOpenedTender", {"pageNo": 1}), ("GetOpenedTender", {"page": 1, "pageSize": 20})]:
    try:
        rr = S.post(w.BH_SITE + "/Templates/TenderBoardWebService.aspx/" + name, data=json.dumps(payload),
                    headers={"Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest"}, timeout=60)
        txt = rr.text
        out.append(f"\n== POST {name} {payload} HTTP {rr.status_code} len {len(txt)}: {txt[:1200]}")
        if re.search(r"iljin", txt, re.I):
            k = re.search(r"iljin", txt, re.I).start()
            out.append("ILJIN: " + txt[max(0, k - 800): k + 500])
    except Exception as e:  # noqa: BLE001
        out.append(f"== POST {name} error {type(e).__name__}: {str(e)[:150]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:500])
