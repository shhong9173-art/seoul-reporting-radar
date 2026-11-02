"""Probe 96: 나라장터 낙찰정보 서비스(data.go.kr 15129397, /1230000/as/ScsbidInfoService) — 물품 낙찰 목록·개찰결과를 하루 범위로 한 번씩.
건수·응답 코드·필드 이름만 남긴다(응답 원문·업체명은 남기지 않음)."""
import json
import os
import re

import requests

KEY = (os.environ.get("G2B_API_KEY") or os.environ.get("CUSTOMS_API_KEY") or "").strip()
H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
BASE = "https://apis.data.go.kr/1230000/as/ScsbidInfoService"
out = [f"key length {len(KEY)}"]
for op in ("getScsbidListSttusThng", "getOpengResultListInfoThng"):
    params = {"serviceKey": KEY, "numOfRows": "5", "pageNo": "1", "inqryDiv": "1", "inqryBgnDt": "202610300000", "inqryEndDt": "202610302359", "type": "json"}
    try:
        r = requests.get(f"{BASE}/{op}", params=params, headers=H, timeout=40)
        t = r.text
        out.append(f"{op} HTTP {r.status_code} ctype {r.headers.get('content-type', '')[:30]} len {len(t)}")
        try:
            j = r.json()
            body = (j.get("response") or {}).get("body") or {}
            head = (j.get("response") or {}).get("header") or {}
            items = body.get("items") or []
            if isinstance(items, dict):
                items = items.get("item") or []
            if isinstance(items, dict):
                items = [items]
            out.append(f"  code {head.get('resultCode')} {head.get('resultMsg')} total {body.get('totalCount')} items {len(items)}")
            if items:
                out.append("  fields " + ", ".join(sorted(items[0].keys()))[:900])
        except ValueError:
            out.append("  not JSON: " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))[:200].replace(KEY, "<KEY>"))
    except Exception as e:  # noqa: BLE001
        out.append(f"{op} {type(e).__name__} {str(e)[:80]}")
text = "\n".join(out)
if KEY:
    text = text.replace(KEY, "<KEY>")
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
