"""격리 탐침: 해외 낙찰·계약 공개 원천의 응답 형식만 본다. 저장하지 않고, 공개 자료의 건수·형식·낙찰사 이름만 출력한다."""
import json
import re

import requests

UA = {"User-Agent": "newsroom-official-research/1.0 (award probe)", "Accept": "application/json, text/html;q=0.8"}
out = []
KR = re.compile(r"hyosung|hyundai|ls cable|ls electric|taihan|doosan|posco|iljin|korea|kepco|samsung c&t|hanwha|lsis|daewoo|sk ecoplant|kia\b", re.I)


def note(tag, msg):
    out.append(f"{tag}: {msg}")


def short(s, n=160):
    return re.sub(r"\s+", " ", str(s or ""))[:n]


def ted(term, fields):
    q = f'FT~"{term}" AND publication-date>=20250101 SORT BY publication-date DESC'
    body = {"query": q, "fields": fields, "limit": 20, "scope": "ALL", "paginationMode": "PAGE_NUMBER", "page": 1}
    r = requests.post("https://api.ted.europa.eu/v3/notices/search", json=body, headers=UA, timeout=40)
    if r.status_code != 200:
        note("TED", f"{term} fields={fields[-2:]} HTTP {r.status_code} {short(r.text, 400)}")
        return None
    d = r.json()
    rows = d.get("notices") or []
    note("TED", f"{term} total={d.get('totalNoticeCount')} returned={len(rows)}")
    for n in rows[:20]:
        typ = n.get("notice-type")
        win = n.get("winner-name") or n.get("organisation-name-tenderer")
        if win or str(typ).startswith("can"):
            note("TED-row", f"{n.get('publication-number')} {n.get('publication-date')} type={typ} buyer={short(json.dumps(n.get('buyer-name'), ensure_ascii=False), 90)} winner={short(json.dumps(win, ensure_ascii=False), 160)} val={short(n.get('tender-value') or n.get('result-value-notice'), 60)}")
    return d


for term in ("Hyosung", "Hyundai Electric", "LS Cable", "Taihan"):
    try:
        base = ["publication-number", "publication-date", "notice-type", "buyer-name", "buyer-country"]
        if ted(term, base + ["winner-name", "tender-value"]) is None:
            ted(term, base + ["organisation-name-tenderer"])
    except Exception as e:  # noqa: BLE001
        note("TED", f"{term} {type(e).__name__} {short(e)}")

# World Bank Major Contract Awards (Socrata, public)
try:
    url = "https://finances.worldbank.org/resource/kdui-wcs3.json"
    params = {"$where": "supplier_country like '%Korea%'", "$order": "contract_signing_date DESC", "$limit": 25}
    r = requests.get(url, params=params, headers=UA, timeout=40)
    note("WB", f"HTTP {r.status_code} ctype={r.headers.get('content-type','')[:40]}")
    if r.status_code == 200:
        rows = r.json()
        if rows:
            note("WB-keys", ",".join(sorted(rows[0].keys())))
        for x in rows[:25]:
            note("WB-row", f"{short(x.get('contract_signing_date'),10)} {short(x.get('supplier'),60)} | {short(x.get('borrower_country'),20)} | {short(x.get('project_name'),60)} | {short(x.get('contract_description'),80)} | {x.get('total_contract_amount_usd') or x.get('supplier_contract_amount_usd')} | asof={short(x.get('as_of_date'),10)}")
    else:
        note("WB", short(r.text, 300))
except Exception as e:  # noqa: BLE001
    note("WB", f"{type(e).__name__} {short(e)}")

# UK Find a Tender OCDS award releases (public)
try:
    url = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
    r = requests.get(url, params={"stages": "award", "updatedFrom": "2026-10-26T00:00:00", "limit": 100}, headers=UA, timeout=60)
    note("FTS", f"HTTP {r.status_code} ctype={r.headers.get('content-type','')[:40]} bytes={len(r.content)}")
    if r.status_code == 200:
        d = r.json()
        rel = d.get("releases") or []
        sup = []
        for x in rel:
            for a in x.get("awards") or []:
                for s in a.get("suppliers") or []:
                    sup.append(s.get("name") or "")
            for p in x.get("parties") or []:
                if "supplier" in (p.get("roles") or []):
                    sup.append(p.get("name") or "")
        note("FTS", f"releases={len(rel)} supplierNames={len(sup)} next={'links' in d and bool((d.get('links') or {}).get('next'))} keys={','.join(sorted(d.keys()))}")
        hits = sorted({s for s in sup if KR.search(s)})
        note("FTS-kr", short("; ".join(hits), 600) or "none")
        buyers = sorted({(p.get('name') or '') for x in rel for p in (x.get('parties') or []) if 'buyer' in (p.get('roles') or [])})
        grid = [b for b in buyers if re.search(r"grid|electric|power|energy|transmission|SSE|scottish", b, re.I)]
        note("FTS-gridbuyers", short("; ".join(grid), 500) or "none")
    else:
        note("FTS", short(r.text, 300))
except Exception as e:  # noqa: BLE001
    note("FTS", f"{type(e).__name__} {short(e)}")

# USAspending federal contracts (public)
for name in ("HYOSUNG", "HYUNDAI POWER TRANSFORMERS", "LS ELECTRIC", "LS CABLE"):
    try:
        body = {"filters": {"recipient_search_text": [name], "award_type_codes": ["A", "B", "C", "D"],
                            "time_period": [{"start_date": "2024-10-01", "end_date": "2026-10-29"}]},
                "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Awarding Sub Agency", "Start Date", "Description"],
                "limit": 10, "page": 1, "sort": "Start Date", "order": "desc"}
        r = requests.post("https://api.usaspending.gov/api/v2/search/spending_by_award/", json=body, headers=UA, timeout=60)
        if r.status_code != 200:
            note("USA", f"{name} HTTP {r.status_code} {short(r.text, 200)}")
            continue
        rows = r.json().get("results") or []
        note("USA", f"{name} rows={len(rows)}")
        for x in rows[:6]:
            note("USA-row", f"{x.get('Start Date')} {short(x.get('Recipient Name'),50)} | {short(x.get('Awarding Sub Agency') or x.get('Awarding Agency'),45)} | {x.get('Award Amount')} | {short(x.get('Description'),80)}")
    except Exception as e:  # noqa: BLE001
        note("USA", f"{name} {type(e).__name__} {short(e)}")

# Gulf public tender boards: reachability and page shape only
for tag, url in (("BH", "https://www.tenderboard.gov.bh/"),
                 ("QA", "https://monaqasat.mof.gov.qa/TendersOnlineServices/AwardedTenders/1"),
                 ("OM", "https://etendering.tenderboard.gov.om/product/publicDash?viewFlag=AwardedTenders"),
                 ("SA", "https://tenders.etimad.sa/Tender/AllTendersForVisitor"),
                 ("KW", "https://capt.gov.kw/en/"),
                 ("ADB", "https://www.adb.org/projects/tenders/group/contracts-awarded"),
                 ("EBRD", "https://ecepp.ebrd.com/delta/noticeSearchResults.html?noticeType=CA")):
    try:
        r = requests.get(url, headers={**UA, "Accept": "text/html"}, timeout=30)
        html = r.text
        title = short(re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I).group(1), 80) if re.search(r"<title", html, re.I) else ""
        links = re.findall(r'href="([^"]*(?:[Aa]ward|Result|result|AwardedTenders|contract)[^"]*)"', html)[:8]
        note(tag, f"HTTP {r.status_code} final={short(r.url,90)} bytes={len(r.content)} title={title} awardLinks={short(' '.join(links), 400)}")
        if tag in ("QA", "OM", "ADB", "EBRD") and r.status_code == 200:
            text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            note(tag + "-text", short(text, 700))
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
