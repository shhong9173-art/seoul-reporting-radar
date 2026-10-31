"""Probe 47: 한전 전력데이터 개방포털 — 기존 KEPCO_API_KEY로 산업분류별·계약종별 전력사용량, 공통코드(시도·시군구·업종) 호출 형식.
상태·필드 이름·건수만(키는 가림). 통계 수치는 찍지 않는다."""
import json
import os
import time
import requests

KEY = os.environ.get("KEPCO_API_KEY", "").strip()
B = "https://bigdata.kepco.co.kr/openapi/v1"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = [f"key set={bool(KEY)} len={len(KEY)}"]


def call(path, **p):
    time.sleep(2)
    try:
        r = requests.get(f"{B}/{path}", params={**p, "apiKey": KEY, "returnType": "json"}, headers=H, timeout=60)
    except Exception as e:  # noqa: BLE001
        out.append(f"{path} {p}: {type(e).__name__}")
        return None
    head = r.text[:200].replace(KEY, "<KEY>") if KEY else r.text[:200]
    try:
        j = r.json()
    except ValueError:
        out.append(f"{path} {p}: HTTP {r.status_code} non-JSON head={head!r}")
        return None
    data = j.get("data") if isinstance(j, dict) else j
    keys = list(j)[:8] if isinstance(j, dict) else "list"
    first = data[0] if isinstance(data, list) and data else None
    out.append(f"{path} {p}: HTTP {r.status_code} top={keys} n={len(data) if isinstance(data, list) else None} fields={sorted(first)[:20] if isinstance(first, dict) else None} "
               f"err={ {k: j.get(k) for k in ('errCd', 'errMsg', 'resultCode', 'resultMsg', 'message') if isinstance(j, dict) and k in j} }")
    return data


for ty in ("metroCd", "cityCd", "bizCd", "cntrCd"):
    d = call("commonCode.do", codeTy=ty)
    if isinstance(d, list) and d and ty in ("metroCd", "bizCd"):
        out.append(f"   {ty} sample codes: " + json.dumps(d[:6], ensure_ascii=False)[:400])
call("powerUsage/industryType.do", year="2026", month="08", metroCd="44", cityCd="", bizCd="")
call("powerUsage/industryType.do", year="2026", month="08", metroCd="44", cityCd="270", bizCd="")
call("powerUsage/contractType.do", year="2026", month="08", metroCd="44", cityCd="", cntrCd="")
for m in ("09", "10"):
    call("powerUsage/industryType.do", year="2026", month=m, metroCd="44", cityCd="", bizCd="")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
