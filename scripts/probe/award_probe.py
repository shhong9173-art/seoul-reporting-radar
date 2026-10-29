"""격리 탐침 19: 바레인 입찰위원회 /Tenders/OpenedBids/ — 목록 형식, 상세(입찰자·가격) 링크, 한국 회사 이름."""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", t))


r = requests.get("https://www.tenderboard.gov.bh/Tenders/OpenedBids/", headers=UA, timeout=40)
b = r.text
out.append(f"list HTTP {r.status_code} len={len(b)}")
hrefs = sorted(set(re.findall(r'href="([^"]*(?:Opened|Bid|Tender|tender|bid)[^"]*)"', b)))[:40]
out.append(f"hrefs={hrefs}")
forms = re.findall(r"<form[^>]*>", b)[:5]
out.append(f"forms={forms}")
ajax = sorted(set(re.findall(r"['\"](/[A-Za-z/]*(?:api|Api|Handler|ashx|svc|json)[^'\"]*)['\"]", b)))[:20]
out.append(f"ajax={ajax}")
t = text_of(b)
i = t.find("Tender")
out.append("text=" + t[i:i + 2500])
detail = next((h for h in hrefs if re.search(r"\d", h)), None)
if detail:
    url = detail if detail.startswith("http") else "https://www.tenderboard.gov.bh" + detail
    d = requests.get(url, headers=UA, timeout=40)
    dt_ = text_of(d.text)
    out.append(f"detail {url} HTTP {d.status_code} len={len(d.text)} text={dt_[dt_.find('Tender'):][:2500]}")
for name in ("ILJIN", "Iljin", "LS Cable", "Taihan", "Hyosung", "HYUNDAI", "Hyundai", "Doosan", "Korea"):
    if name in b:
        k = b.find(name)
        out.append(f"hit {name}: {text_of(b[max(0, k-300):k+300])}")

packs, cur = [], ""
for s in out:
    s = s.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(s) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ¦ " if cur else "") + s
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
