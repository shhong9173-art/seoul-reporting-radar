"""격리 탐침 35: 무역위원회 goMenu·goViewMainBbs 함수(실제 주소), 위원회일정·진행 사건 목록."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
SITE = "https://www.ktc.go.kr"
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


s = requests.Session()
b = s.get(SITE + "/", headers=UA, timeout=40).text
srcs = [SITE + x if x.startswith("/") else x for x in re.findall(r'<script[^>]*src="([^"]+)"', b)]
found = {}
for blob in [b] + [s.get(u, headers=UA, timeout=30).text for u in srcs if "ktc" in u or u.startswith(SITE)][:12]:
    for fn in ("goMenu", "goViewMainBbs", "mainBbsTab"):
        m = re.search(r"function\s+" + fn + r"\s*\([^)]*\)\s*\{[\s\S]{0,700}", blob)
        if m and fn not in found:
            found[fn] = re.sub(r"\s+", " ", m.group(0))[:700]
out.append(f"funcs={found}")
forms = re.findall(r"<form[^>]*>", b)[:5]
out.append(f"forms={forms}")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
