"""격리 탐침 31c: 국민연금 사업장 API V2 — 검색 인자 이름·응답 칸·월 자료·상세·기간별 현황(키 값 미출력)."""
import json
import os
import re
import time
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/"
out = []


def call(op, params, rows=3):
    r = requests.get(BASE + op, params={"serviceKey": key, "pageNo": 1, "numOfRows": rows, "dataType": "json", **params}, timeout=40)
    body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")
    time.sleep(0.6)
    try:
        d = json.loads(body)
    except ValueError:
        out.append(f"{op} {params} HTTP {r.status_code} 비JSON {body[:300]!r}")
        return None, []
    b = (d.get("response") or {}).get("body") or {}
    items = (b.get("items") or {}).get("item") or [] if isinstance(b.get("items"), dict) else (b.get("items") or [])
    items = items if isinstance(items, list) else [items]
    hdr = (d.get("response") or {}).get("header") or {}
    out.append(f"{op} {params} HTTP {r.status_code} code={hdr.get('resultCode')} total={b.get('totalCount')} n={len(items)}")
    return b, items


_, it = call("getBassInfoSearchV2", {"wkplNm": "현대자동차"})
for x in it[:3]:
    out.append("item " + json.dumps(x, ensure_ascii=False)[:600])
call("getBassInfoSearchV2", {"wkpl_nm": "현대자동차"})
call("getBassInfoSearchV2", {"bzowrRgstNo": "101811"})
call("getBassInfoSearchV2", {"bzowr_rgst_no": "101811"})
_, it2 = call("getBassInfoSearchV2", {"wkplNm": "현대제철"}, rows=10)
out.append("현대제철 " + " | ".join(f"{x.get('wkplNm')}·{x.get('dataCrtYm')}·{x.get('bzowrRgstNo')}·{x.get('wkplJnngStcd')}·{str(x.get('wkplRoadNmDtlAddr'))[:20]}" for x in it2))
if it:
    seq = it[0].get("seq")
    _, d = call("getDetailInfoSearchV2", {"seq": seq})
    for x in d[:1]:
        out.append("detail " + json.dumps(x, ensure_ascii=False)[:700])
    _, p = call("getPdAcctoSttusInfoSearchV2", {"seq": seq})
    for x in p[:2]:
        out.append("period " + json.dumps(x, ensure_ascii=False)[:500])
    ym = it[0].get("dataCrtYm")
    if ym:
        _, p2 = call("getPdAcctoSttusInfoSearchV2", {"seq": seq, "dataCrtYm": ym})
        for x in p2[:1]:
            out.append("period ym " + json.dumps(x, ensure_ascii=False)[:500])
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
