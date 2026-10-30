"""격리 탐침 47b: 굴뚝자동측정기기(CleanSYS) 반영 확인·응답 칸 — 출입처 사업장 이름 검색, 배출구·측정 시각(키 값 미출력)."""
import json
import os
import re
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
BASE = "https://apis.data.go.kr/B552584/cleansys/rltmMesureResult"
out = []
for params in ({"factManageNm": "현대제철"}, {"factManageNm": "고려아연"}, {"factManageNm": "영풍"}, {"areaNm": "충남", "factManageNm": "현대제철"}):
    try:
        r = requests.get(BASE, params={"serviceKey": key, "type": "json", "numOfRows": 100, "pageNo": 1, **params}, timeout=60)
        body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")
        code = re.search(r'"(?:resultCode|returnReasonCode)"\s*:\s*"?([^",}\s]+)', body)
        try:
            d = json.loads(body)
            b = (d.get("response") or {}).get("body") or {}
            items = b.get("items") or []
            items = items.get("item") if isinstance(items, dict) else items
            items = items if isinstance(items, list) else ([items] if items else [])
        except ValueError:
            b, items = {}, []
        names = sorted({(x.get("fact_manage_nm"), x.get("area_nm")) for x in items})[:12]
        stacks = sorted({(x.get("fact_manage_nm"), x.get("stack_code")) for x in items})
        out.append(f"{params} HTTP {r.status_code} code={code.group(1) if code else None} total={b.get('totalCount')} n={len(items)} 사업장={names} 배출구수={len(stacks)} 첫줄={json.dumps(items[0], ensure_ascii=False)[:700] if items else body[:300]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{params} {type(e).__name__}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
