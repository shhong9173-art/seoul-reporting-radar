"""probe 207: Signa — ① 미국(US) 2년 출원 수 23곳(어느 회사를 자주 볼지) ② 유럽 0건 8곳 다른 영문 이름(옛 이름·넓은 낱말).
키 값은 찍지 않는다. 저장 안 함. 크레딧: 검색 1쪽 10."""
import collections
import json
import os

import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


KEY = os.environ.get("SIGNA_API_KEY", "").strip()
BASE = "https://api.signa.so"
A = {"User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/json",
     "Authorization": f"Bearer {KEY}"}
cfg = json.load(open("data/trademark_watch.json"))["euipo"]["applicants"]
left = None


def search(name, office, since="2024-11-01", limit=100):
    global left
    r = requests.get(BASE + "/v1/trademarks", headers=A, timeout=60,
                     params={"owner_name": name, "office": office, "filing_date_gte": since, "sort": "-filing_date", "limit": limit})
    left = r.headers.get("X-Credits-Remaining", left)
    b = r.json() if r.ok else {}
    data = b.get("data") or []
    owners = collections.Counter(o.get("name") for x in data for o in x.get("owners") or [] if isinstance(o, dict))
    last90 = sum(1 for x in data if str(x.get("filing_date") or "") >= "2026-08-11")
    return r.status_code, len(data), b.get("has_more"), last90, dict(owners.most_common(5)), [(x.get("application_number"), x.get("mark_text"), x.get("filing_date")) for x in data[:3]]


for c in cfg:
    q = c["query"].strip("*")
    st, n, more, last90, owners, ex = search(q, "US")
    log("US", c["company"], repr(q), st, "n", n, "more", more, "90d", last90, "|", owners, "|", ex)

ALT = {"한국타이어": ["Hankook", "Hankook Tire Co"], "현대제철": ["Hyundai Steel Co", "HYUNDAI STEEL"], "고려아연": ["Korea Zinc Co", "KOREA ZINC"],
       "HD현대일렉트릭": ["Hyundai Electric", "Hyundai Electric & Energy Systems"], "대한전선": ["Taihan Electric Wire", "Taihan Cable"],
       "한화솔루션": ["Hanwha Chemical", "Hanwha"], "금호석유화학": ["Kumho Petrochemical Co", "KOREA KUMHO"], "S-OIL": ["S-OIL", "SOIL Corporation"]}
for comp, names in ALT.items():
    for nm in names:
        st, n, more, last90, owners, ex = search(nm, "EM", since="2021-11-01", limit=50)
        log("EU-ALT", comp, repr(nm), st, "n", n, "more", more, "|", owners, "|", ex)
log("CREDITS LEFT", left)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
