"""probe 202: Signa(상표 API, EUIPO 대체 원천) 문서 읽기 — 검색 주소·인자(출원인·관청·출원일)·크레딧. 키 호출은 인증 확인 1번만. 저장 안 함.
키 값은 어디에도 찍지 않는다(길이·앞 4글자도 안 찍음)."""
import json
import os
import re

import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


UA = {"User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"}
KEY = os.environ.get("SIGNA_API_KEY", "").strip()
log("KEY", "있음" if KEY else "없음")

# ① 문서 색인(llms.txt) — 줄 그대로(길면 앞 150줄)
for url in ("https://docs.signa.so/llms.txt",):
    try:
        r = requests.get(url, headers=UA, timeout=40)
        log("DOC", url, r.status_code, len(r.text))
        for ln in r.text.splitlines()[:150]:
            if ln.strip():
                log("  ", ln[:220])
    except Exception as e:  # noqa: BLE001
        log("DOC", url, type(e).__name__, str(e)[:120])

# ② 전체 문서(llms-full.txt) — 검색·출원인·관청·날짜·크레딧·한도 낱말 줄만
KW = re.compile(r"(/v\d/|GET |POST |search|owner|applicant|holder|office|jurisdiction|filing|filed|date_from|from_date|since|sort|credit|rate.?limit|page|cursor|limit=|EUIPO|EM\b|USPTO|KIPO|WIPO)", re.I)
try:
    r = requests.get("https://docs.signa.so/llms-full.txt", headers=UA, timeout=60)
    log("FULL", r.status_code, len(r.text))
    hits = [ln.strip() for ln in r.text.splitlines() if ln.strip() and KW.search(ln)]
    seen = set()
    for ln in hits:
        k = ln[:160]
        if k in seen:
            continue
        seen.add(k)
        log("  ", ln[:240])
        if len(seen) >= 260:
            break
except Exception as e:  # noqa: BLE001
    log("FULL", type(e).__name__, str(e)[:120])

# ③ OpenAPI 명세 — 경로·방법·인자 이름만
for url in ("https://docs.signa.so/openapi.json", "https://api.signa.so/openapi.json", "https://api.signa.so/v1/openapi.json",
            "https://docs.signa.so/api-reference/openapi.json"):
    try:
        r = requests.get(url, headers=UA, timeout=40)
        log("OPENAPI", url, r.status_code, r.headers.get("content-type", "")[:40], len(r.content))
        if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
            continue
        spec = r.json()
        log("  servers", json.dumps(spec.get("servers"), ensure_ascii=False)[:300])
        for path, ops in (spec.get("paths") or {}).items():
            for m, op in ops.items():
                if not isinstance(op, dict):
                    continue
                params = [p.get("name") for p in op.get("parameters") or [] if isinstance(p, dict)]
                body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
                ref = body.get("$ref") or ",".join((body.get("properties") or {}).keys())
                log("  ", m.upper(), path, "| params", params, "| body", str(ref)[:200], "|", str(op.get("summary") or "")[:80])
        break
    except Exception as e:  # noqa: BLE001
        log("OPENAPI", url, type(e).__name__, str(e)[:120])

open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
