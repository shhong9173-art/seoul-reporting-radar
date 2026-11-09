"""probe 203: Signa — OpenAPI에서 상표 검색 인자(출원인·관청·출원일·정렬) 읽고, 키로 무료 호출(계정·크레딧 가격·관청 목록) +
유럽(EM) 출원인 검색 2번(현대자동차·포스코). 키 값은 찍지 않는다. 저장 안 함."""
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
paths = spec.get("paths") or {}


def params_of(path, method="get"):
    op = (paths.get(path) or {}).get(method) or {}
    out = []
    for p in op.get("parameters") or []:
        if "$ref" in p:
            ref = p["$ref"].split("/")[-1]
            p = (spec.get("components", {}).get("parameters", {}) or {}).get(ref, {})
        sch = p.get("schema") or {}
        out.append((p.get("name"), sch.get("type") or ("enum" if sch.get("enum") else ""), str(sch.get("enum") or "")[:80], re.sub(r"\s+", " ", str(p.get("description") or ""))[:150]))
    return op, out


log("PATHS with trademark/owner/offic/account/usage/credit:", [p for p in paths if re.search(r"trademark|owner|offic|account|usage|credit|entit", p)][:60])
for path in ("/v1/trademarks", "/v1/owners", "/v1/owners/{id}/trademarks"):
    op, ps = params_of(path)
    log("PARAMS", path, "|", str(op.get("summary") or "")[:80])
    for name, typ, enum, desc in ps:
        if re.search(r"owner|applicant|office|jurisd|filing|filed|date|sort|limit|cursor|status|class|q$|fields|include", str(name), re.I):
            log("   ", name, typ, enum, "|", desc)

if not KEY:
    log("KEY 없음 — 호출 안 함")
else:
    def call(path, params=None):
        r = requests.get(BASE + path, headers=A, params=params or {}, timeout=60)
        meta = {k: v for k, v in r.headers.items() if re.search(r"ratelimit|credit|request-id", k, re.I)}
        try:
            body = r.json()
        except ValueError:
            body = {"text": r.text[:300]}
        return r.status_code, body, meta

    st, body, meta = call("/v1/account")
    log("ACCOUNT", st, json.dumps({k: body.get(k) for k in ("plan", "rate_limit_tier", "name")} if isinstance(body, dict) else body, ensure_ascii=False)[:300], meta)
    st, body, _ = call("/v1/credits/pricing")
    items = body.get("data") or body.get("items") or [] if isinstance(body, dict) else []
    for it in items:
        if re.search(r"search|read|list|owner", json.dumps(it), re.I):
            log("PRICE", it.get("name"), it.get("credits"), it.get("unit"), it.get("min_plan"), [e.get("path") for e in it.get("endpoints") or []][:4])
    st, body, _ = call("/v1/offices")
    offices = body.get("data") or [] if isinstance(body, dict) else []
    log("OFFICES", st, [(o.get("code") or o.get("id"), o.get("status") or o.get("availability")) for o in offices][:40])
    em = [o for o in offices if str(o.get("code") or o.get("id")).upper() in ("EM", "EUIPO", "KR", "US")]
    for o in em:
        log("OFFICE", json.dumps(o, ensure_ascii=False)[:500])

    # 출원인 검색: 인자 이름은 위 PARAMS 결과를 보고 다음 탐침에서 고친다 — 이번엔 문서 관례(owner 이름·office·filing_date_gte·sort) 그대로
    for owner in ("Hyundai Motor Company", "POSCO"):
        p = {"owner_name": owner, "office": "EM", "filing_date_gte": "2026-07-12", "sort": "-filing_date", "limit": 10}
        st, body, meta = call("/v1/trademarks", p)
        data = body.get("data") if isinstance(body, dict) else None
        log("SEARCH", owner, st, meta, "| keys", list(body.keys())[:12] if isinstance(body, dict) else "")
        if st != 200:
            log("   ERR", json.dumps(body, ensure_ascii=False)[:600])
            continue
        log("   n", len(data or []), "has_more", body.get("has_more"), "credits", json.dumps(body.get("_meta") or body.get("meta"), ensure_ascii=False)[:200])
        for x in (data or [])[:10]:
            owners = [o.get("name") for o in x.get("owners") or [] if isinstance(o, dict)]
            log("   -", x.get("id"), "|", x.get("mark_text") or x.get("markText"), "|", x.get("office") or x.get("office_code"),
                "| filed", x.get("filing_date"), "| app", x.get("application_number"), "| owners", owners[:2],
                "| classes", (x.get("nice_classes") or x.get("classes") or "")[:10] if isinstance(x.get("nice_classes") or x.get("classes"), list) else x.get("nice_classes"),
                "| status", json.dumps(x.get("status"), ensure_ascii=False)[:80])
        if data:
            log("   FIRST", json.dumps(data[0], ensure_ascii=False)[:1500])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
