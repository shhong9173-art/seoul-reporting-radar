"""격리 탐침 47: 굴뚝원격감시(CleanSYS) 실시간 측정정보 API 존재·반영 여부(키 값 미출력) — 공장 가동 신호."""
import json
import os
import re
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
out = []
for url, params in (("https://apis.data.go.kr/B552584/cleansys/rltmMesureResult", {"areaNm": "충남", "factManageNm": "현대제철", "returnType": "json", "numOfRows": 5, "pageNo": 1}),
                    ("https://apis.data.go.kr/B552584/cleansys/rltmMesureResult", {"areaNm": "경북", "returnType": "json", "numOfRows": 3, "pageNo": 1}),
                    ("https://apis.data.go.kr/B552584/CleansysService/getRltmMesureResult", {"areaNm": "충남", "returnType": "json", "numOfRows": 3, "pageNo": 1})):
    try:
        r = requests.get(url, params={"serviceKey": key, **params}, timeout=40)
        body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")
        out.append(f"{url.split('B552584/')[1]} {params} HTTP {r.status_code} body={re.sub(r'\\s+', ' ', body)[:900]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{url} {type(e).__name__}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
