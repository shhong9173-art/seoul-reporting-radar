"""Probe 15: 한국천문연구원 특일 정보(공휴일) API가 공유 키(DATA_GO_KR_KEY)로 되는지 — 키 값은 출력하지 않는다."""
import os
import time
import requests

out = []
key = os.environ.get("DATA_GO_KR_KEY", "").strip()
out.append(f"key set: {bool(key)}")
for base in ["https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo",
             "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo"]:
    for ym in [("2026", "12"), ("2027", "02")]:
        try:
            r = requests.get(base, params={"serviceKey": key, "solYear": ym[0], "solMonth": ym[1], "_type": "json", "numOfRows": 50}, timeout=30)
            body = r.text.replace(key, "***") if key else r.text
            out.append(f"{base[:5]} {ym} HTTP {r.status_code} type {r.headers.get('content-type')} :: {body[:600]}")
        except Exception as e:  # noqa: BLE001
            out.append(f"{base[:5]} {ym} {type(e).__name__} {str(e)[:120]}")
        time.sleep(1)
    if any("HTTP 200" in x and "locdate" in x for x in out):
        break
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300].replace(key, "***") if key else "\n".join(out)[:300])
