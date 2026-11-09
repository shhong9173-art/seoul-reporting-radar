"""probe 205: Signa — 출입처 23곳 영문 이름으로 출원인(owner) 찾기(이름·나라·상표 수·id), owner_name이 정확히 같아야 하는지(Kia Corporation),
'expanded_fallback' 경고 뜻. 키 값은 찍지 않는다. 저장 안 함. 크레딧: 검색 1쪽 10."""
import json
import os
import re

import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


KEY = os.environ.get("SIGNA_API_KEY", "").strip()
BASE = "https://api.signa.so"
A = {"User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/json",
     "Authorization": f"Bearer {KEY}"}
cfg = json.load(open("data/trademark_watch.json"))["euipo"]["applicants"]

r = requests.get(BASE + "/v1/trademarks", headers=A, timeout=60,
                 params={"owner_name": "Kia Corporation", "office": "EM", "filing_date_gte": "2026-01-01", "sort": "-filing_date", "limit": 5})
b = r.json() if r.ok else {}
log("KIA exact", r.status_code, len(b.get("data") or []), "| warnings", json.dumps((b.get("search_meta") or {}).get("warnings"), ensure_ascii=False)[:600])
for x in (b.get("data") or [])[:5]:
    log("   -", x.get("application_number"), x.get("mark_text"), x.get("filing_date"), [o.get("name") for o in x.get("owners") or []][:2])

for c in cfg:
    q = c["query"].strip("*")
    r = requests.get(BASE + "/v1/owners", headers=A, timeout=60, params={"q": q, "limit": 8, "sort": "-trademark_count"})
    try:
        b = r.json()
    except ValueError:
        b = {}
    if r.status_code != 200:
        log("OWNERS", c["company"], q, r.status_code, json.dumps(b, ensure_ascii=False)[:300])
        continue
    rows = []
    for o in b.get("data") or []:
        rows.append(f'{o.get("id")}|{o.get("name")}|{o.get("country_code")}|tm {o.get("trademark_count") or (o.get("stats") or {}).get("trademark_count")}'
                    f'|offices {",".join((o.get("offices") or [])[:6]) if isinstance(o.get("offices"), list) else o.get("offices")}')
    log("OWNERS", c["company"], q, "|", " ;; ".join(rows))
    if c["company"] == "현대자동차" and b.get("data"):
        log("   FIRST", json.dumps(b["data"][0], ensure_ascii=False)[:900])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
