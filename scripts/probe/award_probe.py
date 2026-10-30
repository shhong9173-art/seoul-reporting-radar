"""격리 탐침 49d: 수질TMS 배출량 API — 변수 조합(연도·분기·날짜 형식·사업장명)으로 결과 코드 91 피하기(키 값 미출력)."""
import os
import re
import time
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
out = []
TRY = [
    {"returnType": "json"},
    {"returnType": "JSON"},
    {"returnType": "json", "msrmtYr": "2026"},
    {"returnType": "json", "msrmtYr": "2026", "msrmtQtr": "3"},
    {"returnType": "json", "msrmtYr": "2026", "msrmtQtr": "4"},
    {"returnType": "json", "msrmtYr": "2026", "msrmtQtr": "3", "bplcNm": "현대제철"},
    {"returnType": "json", "msrmtDt": "2026-10-28"},
    {"returnType": "json", "msrmtDt": "20261028"},
    {"returnType": "json", "msrmtYr": "2025", "msrmtQtr": "4"},
    {"returnType": "xml", "msrmtYr": "2026", "msrmtQtr": "3"},
]
for p in TRY:
    try:
        r = requests.get("https://apis.data.go.kr/B552584/waterTmsService/getList", params={"serviceKey": key, "pageNo": "1", "numOfRows": "3", **p}, timeout=60)
        body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")
        out.append(f"{p} HTTP {r.status_code} {re.sub(r'\\s+', ' ', body)[:700]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{p} {type(e).__name__}")
    time.sleep(0.5)
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
