"""격리 탐침 22: 바레인 개찰 결과 — GetContent(AJAX) 함수가 부르는 주소·인자."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
URL = "https://www.tenderboard.gov.bh/Tenders/OpenedBids/"
out = []
b = requests.get(URL, headers=UA, timeout=40).text
for m in re.finditer(r"function\s+GetContent\s*\(", b):
    out.append("GetContent=" + re.sub(r"\s+", " ", b[m.start():m.start() + 3000]))
for m in re.finditer(r"\$\.ajax\s*\(\s*\{", b):
    out.append("ajax=" + re.sub(r"\s+", " ", b[m.start():m.start() + 900]))
urls = sorted(set(re.findall(r"url\s*:\s*['\"]([^'\"]+)['\"]", b)))
out.append(f"urls={urls}")
packs, cur = [], ""
for x in out[:8]:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
