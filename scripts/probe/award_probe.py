"""격리 탐침 28: 새올 고시공고 제목 검색 — 출입처 이름이 고시·공고 제목에 얼마나·언제 나오는지(당진·아산·여수·울주·군산·서산·동해)."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
BASE = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "10", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A", "pageIndex": "1",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": ""}
CITIES = {"당진": ("https://eminwon.dangjin.go.kr", ["현대제철", "KG스틸", "케이지스틸", "동국제강", "현대", "제철", "공장"]),
          "아산": ("https://eminwon.asan.go.kr", ["현대자동차", "현대", "공장"]),
          "여수": ("https://eminwon.yeosu.go.kr", ["GS칼텍스", "지에스칼텍스", "한화솔루션", "디엘케미칼", "DL", "공장"]),
          "울주": ("http://eminwon.ulju.ulsan.kr", ["고려아연", "엘에스엠앤엠", "LS", "온산", "공장"]),
          "군산": ("https://eminwon.gunsan.go.kr", ["세아", "OCI", "오씨아이", "공장"]),
          "서산": ("https://eminwon.seosan.go.kr", ["현대", "한화", "공장"]),
          "동해": ("https://eminwon.dh.go.kr", ["LS", "엘에스", "공장"])}


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


def city(item):
    name, (host, kws) = item
    res = []
    for kw in kws:
        t0 = time.time()
        try:
            r = requests.post(host + PATH, data={**BASE, "not_ancmt_sj": kw, "searchKeyword": kw}, headers={**UA, "Referer": host + PATH}, timeout=40)
            t = text_of(r.text)
            total = re.search(r"전체게시물\s*:\s*([\d,]+)", t)
            rows = re.findall(r"((?:고시|공고)\s*제[\d-]+호) ¦ ([^¦]{0,70}) ¦ ([^¦]{0,15}) ¦ (\d{4}-\d{2}-\d{2})", t)
            res.append(f"{name}/{kw} HTTP {r.status_code} {time.time()-t0:.0f}s total={total.group(1) if total else None} :: "
                       + " ; ".join(f"{d} {ttl.strip()[:55]}" for _, ttl, _, d in rows[:4]))
        except Exception as e:  # noqa: BLE001
            res.append(f"{name}/{kw} EXC {type(e).__name__}")
        time.sleep(0.7)
    return res


out = []
with ThreadPoolExecutor(4) as ex:
    for lines in ex.map(city, CITIES.items()):
        out.extend(lines)
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
