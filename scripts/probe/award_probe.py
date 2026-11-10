"""probe 209: EPO OPS 미국(US) 공개 — 출입처 6곳 최근 35일 US 공개 건수, 우선권 갈래(KR·PCT·US 등) 분포, 미국 먼저 출원(우선권이 US뿐) 건수와 출원인 이름 꼴.
키·토큰 값은 찍지 않는다. 저장 안 함. OPS 약관 3.2 — 건수·갈래·출원인 이름 꼴만, 제목·번호는 찍지 않는다.
공정 이용: 응답마다 X-Throttling-Control을 읽어 검색 red·black·403이면 그 자리에서 멈춘다. 간격 idle 3초·busy 5초·overloaded 10초."""
import collections
import os
import re
import time

import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


KEY = os.environ.get("EPO_OPS_KEY", "").strip()
SECRET = os.environ.get("EPO_OPS_SECRET", "").strip()
BASE = "https://ops.epo.org/3.2"
UA = "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"


def as_list(x):
    return x if isinstance(x, list) else ([x] if x else [])


def t(v):
    return v.get("$") if isinstance(v, dict) else v


r = requests.post(BASE + "/auth/accesstoken", auth=(KEY, SECRET), data={"grant_type": "client_credentials"},
                  headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"}, timeout=60)
log("TOKEN", r.status_code)
tok = r.json().get("access_token") if r.ok else None
H = {"Authorization": f"Bearer {tok}", "Accept": "application/json", "User-Agent": UA}
NAMES = [("현대자동차", "Hyundai Motor"), ("현대모비스", "Hyundai Mobis"), ("LG화학", "LG Chem"), ("포스코", "POSCO"),
         ("한화솔루션", "Hanwha Solutions"), ("HD현대일렉트릭", "HD Hyundai Electric")]
WIN = 'pd within "20261006 20261110"'
stop = False


def kind(num):
    n = re.sub(r"[^0-9A-Za-z]", "", str(num or "")).upper()
    if re.fullmatch(r"KR(?:10|20)?(?:19|20)\d{9}U?", n):
        return "KR"
    if n.startswith("WO"):
        m = re.match(r"WO\d{4}([A-Z]{2})", n)
        return "WO-KR" if m and m.group(1) == "KR" else "WO"
    return n[:2] or "?"


for comp, nm in NAMES:
    if stop or not tok:
        log("SKIP", comp, "stopped" if stop else "no token")
        continue
    q = f'pa="{nm}" and {WIN} and pn=US'
    pos, total, docs, kinds, firstkind = 1, None, 0, collections.Counter(), collections.Counter()
    us_first_names, kinds_by_type = collections.Counter(), collections.Counter()
    while True:
        r = requests.get(BASE + "/rest-services/published-data/search/biblio", params={"q": q},
                         headers={**H, "X-OPS-Range": f"{pos}-{pos + 99}"}, timeout=90)
        th = r.headers.get("X-Throttling-Control", "")
        m = re.search(r"search=(\w+):(\d+)", th)
        color, pm = (m.group(1), int(m.group(2))) if m else (None, None)
        state = (re.match(r"\s*(\w+)", th) or [None, None])[1]
        if r.status_code == 404:
            total = 0
            break
        if r.status_code != 200:
            log("S", comp, "HTTP", r.status_code, (re.search(r"<code>([^<]+)</code>", r.text) or [None, ""])[1], "| throttle", state, color)
            stop = r.status_code == 403
            break
        bs = r.json().get("ops:world-patent-data", {}).get("ops:biblio-search", {})
        total = int(bs.get("@total-result-count") or 0)
        for ed in as_list((bs.get("ops:search-result") or {}).get("exchange-documents")):
            for e in as_list(ed.get("exchange-document")):
                docs += 1
                bd = e.get("bibliographic-data") or {}
                kinds_by_type[e.get("@kind")] += 1
                pk = []
                for p in as_list((bd.get("priority-claims") or {}).get("priority-claim")):
                    ids = {d.get("@document-id-type"): d for d in as_list(p.get("document-id")) if isinstance(d, dict)}
                    num = t((ids.get("epodoc") or {}).get("doc-number")) or ((t((ids.get("docdb") or {}).get("country")) or "") + (t((ids.get("docdb") or {}).get("doc-number")) or ""))
                    pk.append(kind(num))
                kinds[",".join(sorted(set(pk))) or "none"] += 1
                if pk and set(pk) <= {"US"}:
                    for a in as_list(((bd.get("parties") or {}).get("applicants") or {}).get("applicant")):
                        if a.get("@data-format") == "original":
                            us_first_names[t((a.get("applicant-name") or {}).get("name"))] += 1
        if color in ("red", "black"):
            stop = True
            log("THROTTLE stop", state, color)
            break
        if pos + 100 > total or pos >= 201:
            break
        time.sleep(10 if state == "overloaded" else 5 if state == "busy" else 3)
        pos += 100
    log("S", comp, "total", total, "read", docs, "| kinds(pub)", dict(kinds_by_type.most_common(6)), "| priority sets", dict(kinds.most_common(8)),
        "| US-only applicants", dict(us_first_names.most_common(6)))
    time.sleep(10)
log("LAST throttle", th if tok else "")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
