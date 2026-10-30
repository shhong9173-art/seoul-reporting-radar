"""격리 탐침 49c: 수질TMS 배출량 API — swagger 요청 변수 전부·응답 칸 전부, 필수 변수 넣어 호출(키 값 미출력)."""
import datetime as dt
import json
import os
import re
from urllib.parse import quote

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
out = []
b = requests.get("https://www.data.go.kr/data/15164812/openapi.do", headers=UA, timeout=40).text
sw = json.loads(re.search(r"swaggerJson = `(\{.*?\})`", b, re.S).group(1))
params = sw["paths"]["/getList"].get("parameters", [])
out.append("변수 " + " | ".join(f"{p.get('name')}{'*' if p.get('required') else ''}:{(p.get('description') or '')[:50]}" for p in params))


def walk(d, prefix=""):
    res = []
    for k, v in (d.get("properties") or {}).items():
        if "$ref" in v:
            res += walk(sw["definitions"][v["$ref"].split("/")[-1]], prefix + k + ".")
        elif v.get("type") == "array" and "$ref" in (v.get("items") or {}):
            res += walk(sw["definitions"][v["items"]["$ref"].split("/")[-1]], prefix + k + "[].")
        elif v.get("type") == "object" and v.get("properties"):
            res += walk(v, prefix + k + ".")
        else:
            res.append(f"{prefix}{k}({(v.get('description') or '')[:24]})")
    return res


out.append("응답 " + ", ".join(walk(sw["definitions"]["getList_response"])))
req = {p["name"]: p for p in params}
day = (dt.date.today() - dt.timedelta(days=2)).strftime("%Y%m%d")
guess = {"pageNo": "1", "numOfRows": "5", "returnType": "json", "type": "json", "dataType": "JSON"}
for name, p in req.items():
    if name in guess or name == "serviceKey":
        continue
    nm = name.lower()
    if "dt" in nm or "date" in nm or "ymd" in nm or "de" == nm[-2:]:
        guess[name] = day
for extra in ({}, {k: "현대" for k in req if "nm" in k.lower() and "fact" in k.lower()}):
    try:
        r = requests.get("https://apis.data.go.kr/B552584/waterTmsService/getList", params={"serviceKey": key, **guess, **extra}, timeout=60)
        body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")
        out.append(f"call {dict((k, v) for k, v in {**guess, **extra}.items())} HTTP {r.status_code} {re.sub(r'\\s+', ' ', body)[:1500]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"call {type(e).__name__}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
