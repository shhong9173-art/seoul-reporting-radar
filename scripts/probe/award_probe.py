"""격리 탐침 33: 새 원천 후보 접속·형식(공개 자료만).
(a) 무역위원회(ktc.go.kr) 조사·판정 목록 (b) 자동차리콜센터 국내 리콜 목록(car.go.kr)
(c) 중국 결함산품관리센터 리콜(dpac.samr.gov.cn) (d) 미국 노동부 집행 자료(enforcedata.dol.gov) (e) NLRB 사건 목록"""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


def page(label, url, find=None, n=900, **kw):
    t0 = time.time()
    try:
        r = requests.get(url, headers=UA, timeout=40, **kw)
        t = text_of(r.text)
        i = t.find(find) if find and find in t else 0
        links = sorted(set(re.findall(r'href="([^"]{5,120})"', r.text)))
        out.append(f"{label}: HTTP {r.status_code} {time.time()-t0:.1f}s len={len(r.text)} :: {t[i:i+n]} :: links~{[l for l in links if re.search(r'list|view|board|bbs|Detail|detail', l)][:12]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: EXC {type(e).__name__} {time.time()-t0:.1f}s")


page("ktc home", "https://www.ktc.go.kr/", "조사")
page("ktc main", "https://www.ktc.go.kr/main.do", "조사")
page("car.go.kr recall", "https://www.car.go.kr/ri/stat/list.do", "리콜", 1500)
page("samr dpac", "https://dpac.samr.gov.cn/qczh/gnzhqc/", "现代", 900)
page("samr recall list", "https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/zljds/", "召回", 600)
page("dol enforce", "https://enforcedata.dol.gov/views/data_summary.php", "OSHA", 500)
page("nlrb", "https://www.nlrb.gov/search/case?search_term=Hyundai", "Hyundai", 900)

packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
