"""격리 탐침 3: TED 낙찰국 검색 문법, 영국 FTS 낙찰 릴리스 구조, 세계은행 낙찰 공고 필드. 저장하지 않음. 공개 자료 형식만."""
import json
import re
import time

import requests

UA = {"User-Agent": "newsroom-official-research/1.0 (award probe)", "Accept": "application/json"}
out = []


def note(tag, msg):
    out.append(f"{tag}: {msg}")


def short(s, n=160):
    return re.sub(r"\s+", " ", str(s or ""))[:n]


TED = "https://api.ted.europa.eu/v3/notices/search"
CAN = "notice-type IN (can-standard can-social can-modif can-desg can-tran)"
for q in (f"{CAN} AND winner-country=KOR AND publication-date>=20260701",
          f"{CAN} AND winner-country IN (KOR) AND publication-date>=20260701"):
    try:
        body = {"query": q + " SORT BY publication-date DESC", "fields": ["publication-number", "publication-date", "winner-name", "winner-country", "buyer-name"],
                "limit": 50, "scope": "ALL", "paginationMode": "PAGE_NUMBER", "page": 1}
        r = requests.post(TED, json=body, headers=UA, timeout=40)
        if r.status_code == 200:
            d = r.json()
            wins = []
            for n in d.get("notices") or []:
                names = [w for v in (n.get("winner-name") or {}).values() for w in v]
                wins.append(f"{n.get('publication-number')} {short('/'.join(sorted(set(names))), 80)} ← {short('/'.join(v[0] for v in (n.get('buyer-name') or {}).values()), 50)}")
            note("TEDk", f"[{q[60:110]}] total={d.get('totalNoticeCount')} {short(' ; '.join(wins), 2500)}")
        else:
            note("TEDk", f"[{q[60:110]}] HTTP {r.status_code} {short(r.text, 250)}")
    except Exception as e:  # noqa: BLE001
        note("TEDk", f"{type(e).__name__}")
    time.sleep(3)

try:
    r = requests.get("https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages",
                     params={"stages": "award", "updatedFrom": "2026-10-27T00:00:00", "limit": 5}, headers=UA, timeout=60)
    d = r.json()
    rel = d.get("releases") or []
    if rel:
        x = rel[0]
        note("FTS-rel", f"keys={','.join(sorted(x.keys()))} id={x.get('id')} ocid={x.get('ocid')} tag={x.get('tag')} date={x.get('date')}")
        note("FTS-tender", short(json.dumps({k: (x.get('tender') or {}).get(k) for k in ('id', 'title', 'value', 'classification', 'status')}, ensure_ascii=False), 400))
        aw = (x.get("awards") or [{}])[0]
        note("FTS-award", f"keys={','.join(sorted(aw.keys()))} sample={short(json.dumps({k: aw.get(k) for k in ('id', 'title', 'status', 'date', 'value', 'suppliers', 'datePublished')}, ensure_ascii=False), 500)}")
        p = (x.get("parties") or [{}])[0]
        note("FTS-party", f"keys={','.join(sorted(p.keys()))} roles={p.get('roles')} addr={short(json.dumps(p.get('address'), ensure_ascii=False), 120)}")
        note("FTS-ids", " ".join(str(y.get('id')) for y in rel))
        note("FTS-links", short(json.dumps(d.get("links")), 300))
except Exception as e:  # noqa: BLE001
    note("FTS", f"{type(e).__name__} {short(e)}")

try:
    r = requests.get("https://search.worldbank.org/api/v2/procnotices",
                     params={"format": "json", "rows": 3, "notice_type": "Contract Award", "qterm": "Hyosung", "srt": "noticedate", "order": "desc"},
                     headers=UA, timeout=40)
    d = r.json()
    ns = d.get("procnotices") or []
    note("WB", f"HTTP {r.status_code} total={d.get('total')}")
    for n in ns[:3]:
        note("WB-keys", ",".join(sorted(n.keys())))
        note("WB-n", short(json.dumps({k: n.get(k) for k in ('id', 'noticedate', 'project_ctry_name', 'project_name', 'bid_description', 'contact_organization', 'submission_date')}, ensure_ascii=False), 400))
        txt = n.get("notice_text") or ""
        i = txt.lower().find("hyosung")
        note("WB-text", f"len={len(txt)} around={short(re.sub(r'<[^>]+>', ' ', txt[max(0, i - 300): i + 300]), 500)}")
    r2 = requests.get("https://search.worldbank.org/api/v2/procnotices",
                      params={"format": "json", "rows": 1, "notice_type": "Contract Award", "srt": "noticedate", "order": "desc", "fl": "id,noticedate"},
                      headers=UA, timeout=40)
    note("WB-all", f"HTTP {r2.status_code} total={r2.json().get('total')} latest={short(json.dumps(r2.json().get('procnotices')), 150)}")
except Exception as e:  # noqa: BLE001
    note("WB", f"{type(e).__name__} {short(e)}")

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur)
        cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
