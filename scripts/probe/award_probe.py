"""probe 208: EPO OPS — ① 토큰 발급 ② 출입처 23곳 출원인 검색 건수(최근 120일 공개, 전체/EP·WO) ③ 3곳 서지로 출원인 이름 꼴 확인.
키·토큰 값은 찍지 않는다. 저장 안 함. OPS 약관 3.2(자료 그 자체 공개 금지) — 건수·국가 분포·출원인 이름 꼴만 찍고 제목·초록은 찍지 않는다."""
import collections
import json
import os
import time

import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


KEY = os.environ.get("EPO_OPS_KEY", "").strip()
SECRET = os.environ.get("EPO_OPS_SECRET", "").strip()
BASE = "https://ops.epo.org/3.2"
UA = "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"
log("KEY present", bool(KEY), "SECRET present", bool(SECRET))

r = requests.post(BASE + "/auth/accesstoken", auth=(KEY, SECRET), data={"grant_type": "client_credentials"},
                  headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
log("TOKEN status", r.status_code)
tok = None
if r.ok:
    b = r.json()
    tok = b.get("access_token")
    log("TOKEN ok", bool(tok), "expires_in", b.get("expires_in"), "status", b.get("status"), "api_product", b.get("api_product_list"))
else:
    log("TOKEN body", r.text[:300].replace(KEY, "<k>").replace(SECRET, "<s>") if KEY and SECRET else r.text[:300])

H = {"Authorization": f"Bearer {tok}", "Accept": "application/json", "User-Agent": UA}
last_hdr = {}


def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])


def call(path, q, rng="1-100"):
    global last_hdr
    time.sleep(1.2)
    r = requests.get(BASE + path, params={"q": q}, headers={**H, "X-OPS-Range": rng}, timeout=60)
    last_hdr = {k: v for k, v in r.headers.items() if k.lower().startswith("x-") and ("throttl" in k.lower() or "quota" in k.lower())}
    if r.status_code != 200:
        return r.status_code, None, r.text[:240]
    return r.status_code, r.json(), None


NAMES = {"현대자동차": "Hyundai Motor", "기아": "Kia", "KG모빌리티": "KG Mobility", "현대모비스": "Hyundai Mobis", "HL만도": "HL Mando",
         "한국타이어": "Hankook Tire", "넥센타이어": "Nexen Tire", "금호타이어": "Kumho Tire", "현대제철": "Hyundai Steel", "포스코": "POSCO",
         "고려아연": "Korea Zinc", "HD현대일렉트릭": "HD Hyundai Electric", "LS일렉트릭": "LS Electric", "LS전선": "LS Cable", "대한전선": "Taihan",
         "효성중공업": "Hyosung Heavy", "두산에너빌리티": "Doosan Enerbility", "한화솔루션": "Hanwha Solutions", "LG화학": "LG Chem",
         "롯데케미칼": "Lotte Chemical", "금호석유화학": "Kumho Petrochemical", "S-OIL": "S-Oil", "SK이노베이션": "SK Innovation"}
WIN = 'pd within "20260712 20261110"'

if tok:
    # 날짜 형식 먼저 한 번
    for q in [f'pa="Hyundai Motor" and {WIN}', 'pa="Hyundai Motor" and pd>=20260712']:
        st, b, err = call("/rest-services/published-data/search", q, "1-5")
        tot = b and b.get("ops:world-patent-data", {}).get("ops:biblio-search", {}).get("@total-result-count")
        log("FMT", repr(q), st, "total", tot, "|", err or "")
    for comp, nm in NAMES.items():
        for scope, extra in (("all", ""), ("EPWO", " and (pn=EP or pn=WO)")):
            q = f'pa="{nm}" and {WIN}{extra}'
            st, b, err = call("/rest-services/published-data/search", q)
            if b is None:
                log("S", comp, scope, st, "|", err)
                continue
            bs = b.get("ops:world-patent-data", {}).get("ops:biblio-search", {})
            refs = as_list((bs.get("ops:search-result") or {}).get("ops:publication-reference"))
            cc = collections.Counter(((x.get("document-id") or {}).get("country") or {}).get("$") for x in refs)
            kinds = collections.Counter(((x.get("document-id") or {}).get("kind") or {}).get("$") for x in refs if
                                        ((x.get("document-id") or {}).get("country") or {}).get("$") in ("EP", "WO"))
            log("S", comp, scope, st, "total", bs.get("@total-result-count"), "got", len(refs), "|", dict(cc.most_common(8)), "|", dict(kinds))
    # 서지: 출원인 이름 꼴(제목·초록은 찍지 않음)
    for comp in ("현대자동차", "포스코", "LG화학", "기아", "S-OIL"):
        q = f'pa="{NAMES[comp]}" and {WIN} and (pn=EP or pn=WO)'
        st, b, err = call("/rest-services/published-data/search/biblio", q, "1-25")
        if b is None:
            log("B", comp, st, "|", err)
            continue
        docs = as_list(((b.get("ops:world-patent-data", {}).get("ops:biblio-search", {}).get("ops:search-result") or {})
                        .get("exchange-documents")))
        names = collections.Counter()
        dates = []
        for d in docs:
            ex = d.get("exchange-document") or {}
            for e in as_list(ex):
                bd = e.get("bibliographic-data") or {}
                for a in as_list(((bd.get("parties") or {}).get("applicants") or {}).get("applicant")):
                    if a.get("@data-format") == "original":
                        names[((a.get("applicant-name") or {}).get("name") or {}).get("$")] += 1
                for p in as_list((bd.get("publication-reference") or {}).get("document-id")):
                    if p.get("@document-id-type") == "docdb":
                        dates.append((p.get("date") or {}).get("$"))
        log("B", comp, st, "docs", len(docs), "dates", min(dates or [""]), "~", max(dates or [""]), "|", dict(names.most_common(8)))
log("QUOTA headers", json.dumps(last_hdr, ensure_ascii=False))
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
