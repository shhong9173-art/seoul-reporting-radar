"""격리 탐침 20: 바레인 개찰 결과 페이지 본문 — 'Find Opened Bids' 뒤 표(입찰번호·입찰자·가격)와 상세 이동 방식."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


r = requests.get("https://www.tenderboard.gov.bh/Tenders/OpenedBids/", headers=UA, timeout=40)
b = r.text
t = text_of(b)
i = t.find("Find Opened Bids")
out.append(f"HTTP {r.status_code} len={len(b)} BHD={b.count('BHD')} rows={b.count('<tr')} onclick={len(re.findall(r'onclick=', b))} postback={len(re.findall(r'__doPostBack', b))}")
out.append("after=" + t[i:i + 3300])
m = re.findall(r"(?:onclick|href)=\"([^\"]*(?:Detail|detail|Bid|bid)[^\"]*)\"", b)[:10]
out.append(f"detail links={m}")
scripts = re.findall(r"<script[^>]*src=\"([^\"]+)\"", b)[:15]
out.append(f"scripts={scripts}")
for kw in ("ILJIN", "Iljin", "LS ", "TAIHAN", "Taihan", "HYOSUNG", "Hyosung", "HYUNDAI", "Hyundai"):
    k = b.find(kw)
    if k >= 0:
        out.append(f"hit {kw}: {text_of(b[max(0, k-400):k+300])}")

packs, cur = [], ""
for s in out:
    s = s.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(s) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + s
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
