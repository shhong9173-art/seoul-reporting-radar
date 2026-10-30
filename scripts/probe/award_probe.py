"""격리 탐침 49b: 수질TMS 배출량 API — 페이지 swagger의 요청 변수·응답 칸, 실제 호출(키 값 미출력)."""
import json
import os
import re
from urllib.parse import quote

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
out = []
b = requests.get("https://www.data.go.kr/data/15164812/openapi.do", headers=UA, timeout=40).text
m = re.search(r"swaggerJson = `(\{.*?\})`", b, re.S)
if m:
    try:
        sw = json.loads(m.group(1))
        for path, ops in sw.get("paths", {}).items():
            for verb, op in ops.items():
                if not isinstance(op, dict):
                    out.append(f"path {path} {verb} {str(op)[:300]}")
                    continue
                params = [(p.get("name"), p.get("required"), (p.get("description") or "")[:40]) for p in op.get("parameters", [])]
                out.append(f"path {path} {verb} params={params}")
        defs = sw.get("definitions") or {}
        for name, d in defs.items():
            props = d.get("properties") or {}
            out.append(f"def {name}: " + ", ".join(f"{k}({(v.get('description') or '')[:20]})" for k, v in props.items()))
    except Exception as e:  # noqa: BLE001
        out.append(f"swagger 해석 실패 {type(e).__name__} {str(e)[:100]} 원문 {m.group(1)[:2500]}")
else:
    out.append("swagger 없음")
for params in ({}, {"fact_nm": "현대"}, {"factNm": "현대"}):
    try:
        r = requests.get("https://apis.data.go.kr/B552584/waterTmsService/getList",
                         params={"serviceKey": key, "pageNo": 1, "numOfRows": 3, "returnType": "json", "type": "json", **params}, timeout=60)
        body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")
        out.append(f"call {params} HTTP {r.status_code} {re.sub(r'\\s+', ' ', body)[:900]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"call {params} {type(e).__name__}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
