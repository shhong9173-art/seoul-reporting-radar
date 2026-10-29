"""격리 탐침 18: 바레인 입찰위원회 — 낙찰 보고서 외에 '개찰 결과(입찰자·가격)' 공개 페이지가 있는지, 일진전기·LS·대한전선 이름이 보이는지."""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
out = []


def page(label, url):
    t0 = time.time()
    try:
        r = requests.get(url, headers=UA, timeout=40)
        body = r.text
        title = (re.search(r"<title[^>]*>([\s\S]*?)</title>", body) or [None, ""])[1].strip()[:60]
        links = sorted(set(re.findall(r'href="(/Tenders/[^"#?]{3,80})', body)))[:40]
        hits = re.findall(r"[^<>]{0,80}(?:ILJIN|Iljin|LS Cable|Taihan|TAIHAN|LS CABLE|Hyosung|HYOSUNG|Hyundai|HYUNDAI)[^<>]{0,80}", body)[:5]
        out.append(f"{label}: HTTP {r.status_code} {time.time()-t0:.1f}s len={len(body)} title={title!r} links={links} hits={hits}")
        return body
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: EXC {type(e).__name__} {time.time()-t0:.1f}s")
        return ""


home = page("home", "https://www.tenderboard.gov.bh/")
for label, url in [("awarded", "https://www.tenderboard.gov.bh/Tenders/AwardedTenders/"),
                   ("opened", "https://www.tenderboard.gov.bh/Tenders/OpenedTenders/"),
                   ("opened2", "https://www.tenderboard.gov.bh/Tenders/Opened%20Tenders/"),
                   ("bids", "https://www.tenderboard.gov.bh/Tenders/TenderBids/"),
                   ("public", "https://www.tenderboard.gov.bh/Tenders/Public%20Tenders/")]:
    page(label, url)
    time.sleep(1)

packs, cur = [], ""
for s in out:
    s = s.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(s) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + s
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
