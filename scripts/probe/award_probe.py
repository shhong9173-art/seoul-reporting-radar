"""격리 탐침 2: TED 낙찰 필드·통화, 바레인 낙찰 목록, 영국 FTS 하루 분량, 대법원 회생·파산 공고 목록(해외 IP 접속), 세계은행.
저장하지 않는다. 공개 자료의 건수·형식만 출력한다(회생·파산은 건수·공고 종류만, 회사 이름은 출력하지 않음)."""
import json
import re
import time

import requests

UA = {"User-Agent": "newsroom-official-research/1.0 (award probe)", "Accept": "application/json, text/html;q=0.8"}
out = []
KR = re.compile(r"hyosung|hyundai|ls cable|ls electric|taihan|doosan|posco|iljin|korea|samsung c&t|hanwha|seah|kia\b", re.I)


def note(tag, msg):
    out.append(f"{tag}: {msg}")


def short(s, n=160):
    return re.sub(r"\s+", " ", str(s or ""))[:n]


TED = "https://api.ted.europa.eu/v3/notices/search"


def ted(query, fields, limit=5):
    body = {"query": query, "fields": fields, "limit": limit, "scope": "ALL", "paginationMode": "PAGE_NUMBER", "page": 1}
    return requests.post(TED, json=body, headers=UA, timeout=40)


# 1) which extra fields exist (one notice we already know: 545946-2026, Energinet ← Hyosung)
base = ["publication-number", "notice-type"]
for f in ("winner-country", "tender-value-cur", "result-value-notice", "result-value-cur-notice", "total-value", "total-value-cur",
          "notice-title", "title-lot", "winner-decision-date", "contract-conclusion-date", "buyer-country", "description-lot", "classification-cpv",
          "deadline-receipt-tender-date-lot", "winner-identifier", "organisation-name-tenderer", "links"):
    try:
        r = ted("publication-number=545946-2026", base + [f], 1)
        if r.status_code == 200:
            n = (r.json().get("notices") or [{}])[0]
            note("TEDf", f"{f} ok={short(json.dumps(n.get(f), ensure_ascii=False), 220)}")
        else:
            note("TEDf", f"{f} HTTP {r.status_code} {short(r.text, 160)}")
    except Exception as e:  # noqa: BLE001
        note("TEDf", f"{f} {type(e).__name__}")
    time.sleep(0.3)

# 2) query syntax: award types only, winner-name field search
for q in ('winner-name~"Hyosung" AND publication-date>=20250101',
          'notice-type IN (can-standard can-social can-modif can-desg can-tran) AND FT~"Hyosung" AND publication-date>=20250101',
          'notice-type=can-standard AND FT~"Hyundai" AND publication-date>=20260901'):
    try:
        r = ted(q + " SORT BY publication-date DESC", ["publication-number", "notice-type", "winner-name"], 50)
        if r.status_code == 200:
            d = r.json()
            types = {}
            for n in d.get("notices") or []:
                types[n.get("notice-type")] = types.get(n.get("notice-type"), 0) + 1
            wins = sorted({w for n in d.get("notices") or [] for v in (n.get("winner-name") or {}).values() for w in v if KR.search(w)})
            note("TEDq", f"[{q[:70]}] total={d.get('totalNoticeCount')} types={types} krWinners={short('; '.join(wins), 300)}")
        else:
            note("TEDq", f"[{q[:70]}] HTTP {r.status_code} {short(r.text, 220)}")
    except Exception as e:  # noqa: BLE001
        note("TEDq", f"{type(e).__name__}")
    time.sleep(0.3)

# 3) Bahrain Tender Board awarded tenders
try:
    r = requests.get("https://www.tenderboard.gov.bh/Tenders/AwardedTenders/", headers={**UA, "Accept": "text/html"}, timeout=40)
    html = r.text
    forms = " ".join(re.findall(r'<form[^>]*action="([^"]*)"', html))
    note("BH", f"HTTP {r.status_code} bytes={len(r.content)} tables={html.count('<table')} rows={html.count('<tr')} forms={short(forms, 200)}")
    heads = re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)
    note("BH-th", short(" / ".join(re.sub(r"<[^>]+>", "", h).strip() for h in heads[:20]), 400))
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    for row in rows[1:6]:
        cells = [short(re.sub(r"<[^>]+>", " ", c), 70) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        note("BH-row", " | ".join(cells))
    links = sorted(set(re.findall(r'href="([^"]*(?:Award|award|Tender|tender)[^"]*)"', html)))[:15]
    note("BH-links", short(" ".join(links), 600))
    scripts = re.findall(r'(?:url|ajax|fetch)\s*[:(]\s*["\']([^"\']+)["\']', html)
    note("BH-ajax", short(" ".join(scripts[:10]), 400))
except Exception as e:  # noqa: BLE001
    note("BH", f"{type(e).__name__} {short(e)}")

# 4) UK FTS: how many award pages in one day
try:
    url = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
    params = {"stages": "award", "updatedFrom": "2026-10-27T00:00:00", "updatedTo": "2026-10-28T00:00:00", "limit": 100}
    pages, releases, kr, grid, t0 = 0, 0, set(), set(), time.time()
    nxt = None
    while pages < 25:
        r = requests.get(nxt or url, params=None if nxt else params, headers=UA, timeout=60)
        if r.status_code != 200:
            note("FTS", f"page {pages} HTTP {r.status_code} {short(r.text, 150)}")
            break
        d = r.json()
        pages += 1
        rel = d.get("releases") or []
        releases += len(rel)
        for x in rel:
            for p in x.get("parties") or []:
                roles = p.get("roles") or []
                if "supplier" in roles and KR.search(p.get("name") or ""):
                    kr.add(p.get("name"))
                if "buyer" in roles and re.search(r"national grid|ssen|scottish (?:hydro|power)|electricity north|ukpn|uk power networks|northern powergrid|western power|nged|sp energy|energy networks", p.get("name") or "", re.I):
                    grid.add(p.get("name"))
        nxt = (d.get("links") or {}).get("next")
        if not nxt or not rel:
            break
        time.sleep(0.5)
    note("FTS", f"day=10-27 pages={pages} releases={releases} secs={time.time()-t0:.0f} more={bool(nxt)} kr={short('; '.join(sorted(kr)), 300)} gridBuyers={short('; '.join(sorted(grid)), 300)}")
except Exception as e:  # noqa: BLE001
    note("FTS", f"{type(e).__name__} {short(e)}")

# 5) 대법원 회생·파산 공고 목록 from a non-Korean runner (counts and notice kinds only)
try:
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/json; charset=UTF-8",
                      "Referer": "https://ssgo.scourt.go.kr/ssgo/ssgo930/rhblBnkp.on"})
    for task, cort in (("4", "000221"), ("5", "000443")):
        body = {"dma_search": {"taskDvs": task, "srchType": "pstgBgng", "cortCd": cort, "pstgDvs": "999", "csYr": "", "csDvsCd": "",
                               "csSrno": "", "debtrNm": "", "jdbnCd": ""},
                "dma_pageInfo": {"pageNo": 1, "pageSize": 50, "totalYn": "Y"}}
        r = s.post("https://ssgo.scourt.go.kr/ssgo/ssgo930/selectRhblBnkpPbancLst.on", data=json.dumps(body), timeout=40)
        if r.status_code != 200:
            note("SC", f"{task}/{cort} HTTP {r.status_code} {short(r.text, 150)}")
            continue
        d = r.json().get("data") or {}
        rows = d.get("dlt_pbancLst") or []
        kinds = {}
        for x in rows:
            kinds[x.get("inetPbancDvsCd")] = kinds.get(x.get("inetPbancDvsCd"), 0) + 1
        note("SC", f"{task}/{cort} rows={len(rows)} total={(d.get('dma_pageInfo') or {}).get('totalCnt')} first={rows[0].get('pbancBgngYmd') if rows else ''} kinds={kinds}")
        time.sleep(1)
except Exception as e:  # noqa: BLE001
    note("SC", f"{type(e).__name__} {short(e)}")

# 6) World Bank contract awards
for tag, url in (("WB1", "https://search.worldbank.org/api/v2/contractdata?format=json&rows=3&supplier_country_name=Korea,%20Republic%20of"),
                 ("WB2", "https://search.worldbank.org/api/v2/procnotices?format=json&rows=3&notice_type=Contract%20Award&qterm=Hyosung"),
                 ("WB3", "https://finances.worldbank.org/api/views/kdui-wcs3.json")):
    try:
        r = requests.get(url, headers=UA, timeout=40)
        note(tag, f"HTTP {r.status_code} ctype={r.headers.get('content-type','')[:30]} final={short(r.url, 80)} head={short(r.text, 400)}")
    except Exception as e:  # noqa: BLE001
        note(tag, f"{type(e).__name__} {short(e)}")

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
