"""격리 탐침 34: 무역위원회 누리집 메뉴 주소(위원회 일정·조사 진행·종결·보도자료·공지·의결서), 목록 형식."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


b = requests.get("https://www.ktc.go.kr/", headers=UA, timeout=40).text
pairs = re.findall(r'<a[^>]*href="([^"#]+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{2,30})', b)
menu = []
for href, label in pairs:
    label = re.sub(r"\s+", " ", label).strip()
    if re.search(r"일정|진행|종결|보도|공지|의결|판정|고시|공고|회의록|사건", label):
        menu.append((label, href))
out.append(f"menu={sorted(set(menu))[:40]}")
targets = [h for l, h in menu if re.search(r"일정|진행|보도|의결", l)][:4]
for h in targets:
    url = h if h.startswith("http") else "https://www.ktc.go.kr" + (h if h.startswith("/") else "/" + h)
    try:
        r = requests.get(url, headers=UA, timeout=40)
        t = text_of(r.text)
        i = max(t.find("번호"), 0)
        rows = re.findall(r'href="([^"]*(?:view|View|detail|Detail)[^"]*)"', r.text)[:3]
        out.append(f"{url} HTTP {r.status_code} len={len(r.text)} rowlinks={rows} :: {t[i:i+1300]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{url} EXC {type(e).__name__}")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
