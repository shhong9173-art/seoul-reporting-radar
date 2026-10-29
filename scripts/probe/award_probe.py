"""격리 탐침 36: 무역위원회 menuMap(메뉴 번호→주소)과 진행 사건·위원회 일정·보도자료·의결서 목록 형식."""
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
mm = dict(re.findall(r"menuMap\.(?:put|set)\(\s*['\"]?(\d+)['\"]?\s*,\s*\[\s*['\"]([^'\"]+)['\"]", b))
out.append(f"menuMap n={len(mm)} sel={ {k: mm.get(k) for k in ('11', '12', '14', '15', '16', '23', '24', '45', '46', '57', '109')} }")
for mid in ("11", "24", "57", "16"):
    u = mm.get(mid)
    if not u:
        continue
    try:
        r = s.post(SITE + u, data={"menuId": mid}, headers={**UA, "Referer": SITE + "/"}, timeout=40)
        t = text_of(r.text)
        i = t.find("번호") if "번호" in t else 0
        js = sorted(set(re.findall(r"(?:href|onclick)=\"(javascript:[^\"]{0,90})\"", r.text)))
        js = [j for j in js if re.search(r"View|view|Detail|detail", j)][:4]
        out.append(f"menu {mid} {u} HTTP {r.status_code} len={len(r.text)} js={js} :: {t[i:i+1500]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"menu {mid} EXC {type(e).__name__}")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
