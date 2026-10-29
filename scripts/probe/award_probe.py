"""격리 탐침 31b(08:43 신청 뒤): 국민연금 사업장 API — 어느 공공데이터 키로 신청했는지 몰라 키 이름별로 한 번씩(키 값·길이 미출력, 같은 키끼리는 한 번만)."""
import os
import re

import requests

BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/getBassInfoSearchV2"
out, seen = [], {}
for name in ("DATA_GO_KR_KEY", "KR_FUEL_API_KEY", "G2B_API_KEY", "CUSTOMS_API_KEY"):
    key = (os.environ.get(name) or "").strip()
    if not key:
        out.append(f"{name}: 없음")
        continue
    if key in seen:
        out.append(f"{name}: {seen[key]}와 같은 키 — 다시 부르지 않음")
        continue
    seen[key] = name
    r = requests.get(BASE, params={"serviceKey": key, "pageNo": 1, "numOfRows": 1, "dataType": "json", "wkplNm": "현대자동차"}, timeout=40)
    code = re.search(r'"(?:resultCode|returnReasonCode)"\s*:\s*"?([^",}\s]+)', r.text)
    msg = re.search(r'"(?:resultMsg|returnAuthMsg)"\s*:\s*"([^"]+)"', r.text)
    out.append(f"{name}: HTTP {r.status_code} code={code.group(1) if code else None} msg={msg.group(1) if msg else None}")
print("::notice title=aw-00::" + " ¶ ".join(out))
