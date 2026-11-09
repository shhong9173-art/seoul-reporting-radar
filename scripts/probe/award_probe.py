"""probe 204: Signa — 검색 limit 최대값(명세), owner_name 맞추는 방식(부분·정확), 한 쪽에 몇 건(크레딧). 키 값은 찍지 않는다. 저장 안 함."""
import collections
import json
import os
import re

import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


KEY = os.environ.get("SIGNA_API_KEY", "").strip()
BASE = "https://api.signa.so"
H = {"User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/json"}
A = {**H, "Authorization": f"Bearer {KEY}"}
spec = requests.get(BASE + "/openapi.json", headers=H, timeout=60).json()
op = spec["paths"]["/v1/trademarks"]["get"]
for p in op.get("parameters") or []:
    if "$ref" in p:
        p = spec["components"]["parameters"][p["$ref"].split("/")[-1]]
    if p.get("name") in ("limit", "owner_name", "sort", "office"):
        log("SPEC", p.get("name"), json.dumps(p.get("schema"), ensure_ascii=False)[:300], "|", re.sub(r"\s+", " ", str(p.get("description") or ""))[:400])

for owner, limit in (("Hyundai Motor Company", 100), ("Kia", 50), ("LG Chem", 50), ("Hankook Tire", 50)):
    r = requests.get(BASE + "/v1/trademarks", headers=A, timeout=60,
                     params={"owner_name": owner, "office": "EM", "filing_date_gte": "2026-07-12", "sort": "-filing_date", "limit": limit})
    meta = {k: v for k, v in r.headers.items() if re.search(r"credits-(charged|remaining)", k, re.I)}
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code != 200:
        log("SEARCH", owner, limit, r.status_code, json.dumps(body, ensure_ascii=False)[:500])
        continue
    data = body.get("data") or []
    names = collections.Counter(o.get("name") for x in data for o in x.get("owners") or [] if isinstance(o, dict))
    routes = collections.Counter(x.get("filing_route") for x in data)
    log("SEARCH", owner, "limit", limit, "| n", len(data), "has_more", body.get("has_more"), meta, "| owners", dict(names.most_common(6)), "| routes", dict(routes))
    log("   pagination", json.dumps(body.get("pagination"), ensure_ascii=False)[:200], "| search_meta", json.dumps(body.get("search_meta"), ensure_ascii=False)[:300])
    for x in data[:6]:
        log("   -", x.get("application_number"), "|", x.get("mark_text"), "| filed", x.get("filing_date"), "| pub", x.get("publication_date"),
            "|", x.get("filing_route"), "| classes", x.get("nice_classes"), "|", (x.get("status") or {}).get("raw"))
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
