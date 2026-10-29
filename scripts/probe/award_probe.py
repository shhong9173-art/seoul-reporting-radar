"""격리 탐침 24: 바레인 개찰 결과 상세(/OpenedTenderDetails/) — 입찰자·가격 칸. EWA 계열 최근 3건 + 이름 검색(Taihan, LS, Iljin, Hyosung)."""
import html as H
import json
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SITE = "https://www.tenderboard.gov.bh"
PAGE = SITE + "/Tenders/OpenedBids/"
WS = SITE + "/Templates/TenderBoardWebService.aspx/"
HJ = {**UA, "Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest", "Referer": PAGE}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


def listing(s, page=1, ministry="0", number=""):
    body = {"tenderNumber": number, "ministry": ministry, "category": "0", "tendertype": "0", "openedDate_filter": "", "endDate_filter": "",
            "sortingType": "0", "pageIndex": str(page), "sectionName": "0"}
    r = s.post(WS + "GetOpenedTenderF", data=json.dumps(body).replace('"', "'"), headers=HJ, timeout=60)
    d = r.json().get("d", "")
    content = H.unescape((re.search(r"<Content>([\s\S]*?)</Content>", d) or [None, ""])[1])
    rows = []
    for m in re.finditer(r"<div data-ref='(\d+)' class='rows'>([\s\S]*?)</div></div></div>", content):
        cells = dict(re.findall(r"data-label='([^']+)'>([\s\S]*?)</div>", m.group(2)))
        link = re.search(r"href='([^']+)'", m.group(2))
        rows.append({"ref": m.group(1), "no": re.sub(r"<[^>]+>", " ", cells.get("No./Tender Subject", ""))[:120].strip(),
                     "opened": cells.get("Date Opened"), "buyer": cells.get("Purchasing Authority"), "link": H.unescape(link.group(1)) if link else None})
    return rows


s = requests.Session()
s.get(PAGE, headers=UA, timeout=40)
KR = re.compile(r"LS CABLE|LS ELECTRIC|\bLS\b|TAIHAN|HYOSUNG|HYUNDAI|DOOSAN|POSCO|SEAH|ILJIN|GAON|KEPCO|KOREA|SAMSUNG|DAEWOO|HANWHA|KOLON|LG ", re.I)
POWER = re.compile(r"cable|transmission|kv\b|substation|transformer|switchgear|overhead|grid|GIS|power", re.I)
seen = 0
for ministry in ("Electricity and Water Authority", "Ministry Of Electricity And Water Affairs", "Electricity and Water Authority (Saudi Fund for Development)"):
    for page in range(1, 6):
        try:
            rows = listing(s, page, ministry)
        except Exception as e:  # noqa: BLE001
            out.append(f"{ministry} p{page} EXC {type(e).__name__}")
            break
        if not rows:
            break
        for r in rows:
            if not POWER.search(r["no"]) or not r["link"]:
                continue
            d = s.get(SITE + r["link"], headers=UA, timeout=60)
            seen += 1
            t = text_of(d.text)
            i = t.find("Bidder's Name")
            j = t.find("Notice:")
            bids = t[i:j] if i >= 0 else ""
            kr = sorted(set(m.group(0) for m in KR.finditer(bids)))
            out.append(f"{r['opened']} {r['buyer'][:25]} {r['no'][:70]} :: KR={kr} :: {bids[:400] if kr else bids[:120]}")
            time.sleep(0.8)
        time.sleep(0.8)
out.append(f"details opened={seen}")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
