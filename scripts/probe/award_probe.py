"""격리 탐침 31(재실행 10-30 04:32): 국민연금 가입 사업장(공공데이터 3046071) — 활용신청 반영 여부, 연산 이름·인자·응답 칸(키 값 미출력)."""
import json
import os
import re
import time

import requests
from urllib.parse import quote

key = ""
for name in ("KR_FUEL_API_KEY", "DATA_GO_KR_KEY", "CUSTOMS_API_KEY", "G2B_API_KEY"):
    key = key or (os.environ.get(name) or "").strip()
BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/"
out = []


def call(op, params):
    t0 = time.time()
    r = requests.get(BASE + op, params={"serviceKey": key, "pageNo": 1, "numOfRows": 3, "dataType": "json", **params}, timeout=40)
    body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>") if key else r.text
    code = re.search(r'"(?:resultCode|returnReasonCode)"\s*:\s*"?([^",}\s]+)', body) or re.search(r"<(?:resultCode|returnReasonCode)>([^<]+)", body)
    out.append(f"{op} {params} HTTP {r.status_code} {time.time()-t0:.1f}s code={code.group(1) if code else None} body={re.sub(chr(10), ' ', body[:900])!r}")
    time.sleep(0.5)
    try:
        return r.json()
    except ValueError:
        return None


d = call("getBassInfoSearchV2", {"wkplNm": "현대자동차"})
items = []
try:
    items = d["response"]["body"]["items"]["item"]
    items = items if isinstance(items, list) else [items]
except Exception:  # noqa: BLE001
    pass
if items:
    seq = items[0].get("seq")
    out.append(f"first item keys={sorted(items[0].keys())}")
    call("getDetailInfoSearchV2", {"seq": seq})
    call("getPdAcctoSttusInfoSearchV2", {"seq": seq})
else:
    call("getBassInfoSearchV2", {"wkpl_nm": "현대자동차"})

blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
