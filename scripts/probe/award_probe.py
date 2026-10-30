"""probe: 대만 정부전자조달(PCC) 낙찰 공고 — g0v 미러 API(pcc-api.openfun.app)에서 출입처 이름 검색, 최신성, 금액 칸. 공개 자료, 키 없음."""
import json
import time

import requests

API = "https://pcc-api.openfun.app/api/searchbycompanyname"
UA = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
TERMS = ["樂星", "LS Electric", "LS Cable", "曉星", "Hyosung", "現代電", "HYUNDAI ELECTRIC", "HD HYUNDAI", "大韓電線", "Taihan", "TAIHAN",
         "斗山", "Doosan", "浦項", "POSCO", "高麗亞鉛", "韓商"]
for q in TERMS:
    try:
        r = requests.get(API, params={"query": q}, headers=UA, timeout=40)
        d = r.json()
        recs = d.get("records") or []
        dates = sorted((str(x.get("date")) for x in recs), reverse=True)
        out.append(f"== {q}: HTTP {r.status_code} total {d.get('total_records')} pages {d.get('total_pages')} latest {dates[:3]}")
        for x in sorted(recs, key=lambda x: str(x.get("date")), reverse=True)[:4]:
            b = x.get("brief") or {}
            names = (b.get("companies") or {}).get("names") or []
            out.append(f"  {x.get('date')} {b.get('type')} | {x.get('unit_name')} | {str(b.get('title'))[:60]} | {'; '.join(map(str, names))[:120]} | amt {x.get('award_amount')} | {x.get('url')}")
    except Exception as e:  # noqa: BLE001
        out.append(f"ERR {q} {type(e).__name__} {str(e)[:100]}")
    time.sleep(1.0)
# 최신성: 어제 날짜 목록
for path in ("https://pcc-api.openfun.app/api/listbydate?date=20261029", "https://pcc-api.openfun.app/api/getinfo"):
    try:
        r = requests.get(path, headers=UA, timeout=40)
        out.append(f"== {path.split('/api/')[1]}: HTTP {r.status_code} {r.text[:400]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"ERR {path} {type(e).__name__}")
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
