"""격리 탐침 23: 바레인 개찰 결과 웹서비스(GetOpenedTenderF) — 기본 인자로 1쪽, 결과 HTML 형식·입찰자·가격, EWA 발주처 값."""
import json
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
PAGE = "https://www.tenderboard.gov.bh/Tenders/OpenedBids/"
WS = "https://www.tenderboard.gov.bh/Templates/TenderBoardWebService.aspx/"
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


s = requests.Session()
b = s.get(PAGE, headers=UA, timeout=40).text
for sel in ("ddlTendertype", "ddlSortingType"):
    m = re.search(sel + r'"[^>]*>([\s\S]*?)</select>', b)
    out.append(f"{sel} options={re.findall(r'value=\"([^\"]*)\"[^>]*>([^<]*)<', m.group(1))[:12] if m else None}")
init = re.findall(r"var\s+(selectedMinistry|selectedSection)\s*=\s*([^;]+);", b)
out.append(f"init={init}")
H = {**UA, "Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest", "Referer": PAGE}
mins = s.post(WS + "GetAllMinistries", data="", headers=H, timeout=40)
ms = re.findall(r"<OptionValue>([^<]*)</OptionValue>\s*<OptionText>([^<]*)</OptionText>", mins.json().get("d", "")) if mins.ok else []
out.append(f"ministries HTTP {mins.status_code} n={len(ms)} ewa={[m for m in ms if 'Electricity' in m[1]]}")
body = {"tenderNumber": "", "ministry": "0", "category": "0", "tendertype": "0", "openedDate_filter": "", "endDate_filter": "",
        "sortingType": "0", "pageIndex": "1", "sectionName": "0"}
r = s.post(WS + "GetOpenedTenderF", data=json.dumps(body).replace('"', "'"), headers=H, timeout=60)
out.append(f"GetOpenedTenderF HTTP {r.status_code} len={len(r.text)}")
try:
    d = r.json().get("d", "")
    pager = re.search(r"<RecordCount>([^<]*)</RecordCount>", d)
    content = re.search(r"<Content>([\s\S]*?)</Content>", d)
    html = content.group(1) if content else ""
    import html as h
    html = h.unescape(html)
    out.append(f"records={pager.group(1) if pager else None} contentLen={len(html)}")
    out.append("raw=" + re.sub(r"\s+", " ", html)[:3300])
    ev = sorted(set(re.findall(r"on\w+=\"([^\"]{0,120})\"", html)))[:10]
    out.append(f"events={ev}")
    funcs = sorted(set(re.findall(r"function\s+(\w+)\s*\(", b)))
    out.append(f"page funcs={funcs[:60]}")
    links = sorted(set(re.findall(r'href="([^"]+)"', html)))[:10]
    out.append(f"links={links}")
except Exception as e:  # noqa: BLE001
    out.append(f"parse EXC {type(e).__name__} head={r.text[:300]!r}")

packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
