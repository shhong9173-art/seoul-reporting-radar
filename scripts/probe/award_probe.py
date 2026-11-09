"""probe 206: Signa — 출입처 23곳 owner_name 맞추기 확인(유럽 EM, 출원일 2년). 짧은 이름이 0건이면 정식 영문 이름으로 한 번 더.
키 값은 찍지 않는다. 저장 안 함. 크레딧: 검색 1쪽 10(최대 46번)."""
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
FULL = {"Hankook Tire": "Hankook Tire & Technology Co., Ltd.", "Nexen Tire": "Nexen Tire Corporation", "Kumho Tire": "Kumho Tire Co., Inc.",
        "Hyundai Steel": "Hyundai Steel Company", "Korea Zinc": "Korea Zinc Company, Ltd.", "HD Hyundai Electric": "HD Hyundai Electric Co., Ltd.",
        "LS Electric": "LS Electric Co., Ltd.", "LS Cable": "LS Cable & System Ltd.", "Taihan": "Taihan Cable & Solution Co., Ltd.",
        "Hyosung Heavy": "Hyosung Heavy Industries Corporation", "Doosan Enerbility": "Doosan Enerbility Co., Ltd.",
        "Hanwha Solutions": "Hanwha Solutions Corporation", "LG Chem": "LG Chem, Ltd.", "Lotte Chemical": "Lotte Chemical Corporation",
        "Kumho Petrochemical": "Korea Kumho Petrochemical Co., Ltd.", "S-Oil": "S-Oil Corporation", "SK Innovation": "SK Innovation Co., Ltd.",
        "Hyundai Mobis": "Hyundai Mobis Co., Ltd.", "HL Mando": "HL Mando Corporation", "KG Mobility": "KG Mobility Corp.", "POSCO": "POSCO Holdings Inc."}
cfg = json.load(open("data/trademark_watch.json"))["euipo"]["applicants"]
left = None


def search(name):
    global left
    r = requests.get(BASE + "/v1/trademarks", headers=A, timeout=60,
                     params={"owner_name": name, "office": "EM", "filing_date_gte": "2024-11-01", "sort": "-filing_date", "limit": 5})
    left = r.headers.get("X-Credits-Remaining", left)
    b = r.json() if r.ok else {}
    data = b.get("data") or []
    owners = collections.Counter(o.get("name") for x in data for o in x.get("owners") or [] if isinstance(o, dict))
    return r.status_code, len(data), b.get("has_more"), dict(owners.most_common(4)), [(x.get("application_number"), x.get("mark_text"), x.get("filing_date")) for x in data[:3]]


for c in cfg:
    q = c["query"].strip("*")
    st, n, more, owners, ex = search(q)
    log("Q", c["company"], repr(q), st, "n", n, "more", more, "|", owners, "|", ex)
    if st == 200 and n == 0 and q in FULL:
        st, n, more, owners, ex = search(FULL[q])
        log("   FULL", repr(FULL[q]), st, "n", n, "more", more, "|", owners, "|", ex)
log("CREDITS LEFT", left)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
