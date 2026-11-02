"""Probe 97d: EUIPO 상표 검색 — 운영 토큰 호스트가 러너에서 502라, API 게이트웨이가 클라이언트 ID·비밀 머리글만으로 받는지 한 번
(현대자동차 출원 최근 5건, 응답 코드·건수·필드 이름만). 키 값은 남기지 않는다."""
import os
import re

import requests

CID = os.environ.get("EUIPO_CLIENT_ID", "").strip()
SEC = os.environ.get("EUIPO_CLIENT_SECRET", "").strip()
out = []
try:
    r = requests.get("https://api.euipo.europa.eu/trademark-search/trademarks",
                     params={"query": 'applicants.name=="*HYUNDAI MOTOR*"', "size": 10, "sort": "applicationDate:desc"},
                     headers={"X-IBM-Client-Id": CID, "X-IBM-Client-Secret": SEC, "Accept": "application/json"}, timeout=40)
    ct = r.headers.get("content-type", "")
    if ct.startswith("application/json"):
        j = r.json()
        items = j.get("trademarks") or j.get("content") or []
        out.append(f"HTTP {r.status_code} keys {sorted(j.keys())[:12]} items {len(items)} total {j.get('totalElements')} detail {str(j.get('detail') or j.get('title') or '')[:160]}")
        if items:
            out.append("fields " + ", ".join(sorted(items[0].keys()))[:600])
    else:
        out.append(f"HTTP {r.status_code} ctype {ct[:40]} " + re.sub(r"\s+", " ", r.text[:200]))
except Exception as e:  # noqa: BLE001
    out.append(f"{type(e).__name__} {str(e)[:100]}")
text = "\n".join(out)
for v in (CID, SEC):
    if v:
        text = text.replace(v, "<X>")
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
