"""격리 탐침 27: 새올 고시공고(POST 목록)가 출입처 공장이 있는 시·군에서 되는지 — 주소별 HTTP·전체 건수·첫 제목."""
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
DATA = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "10", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A", "pageIndex": "1",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": ""}
HOSTS = {
    "당진": ["eminwon.dangjin.go.kr"], "포항": ["eminwon.pohang.go.kr"], "광양": ["eminwon.gwangyang.go.kr"], "아산": ["eminwon.asan.go.kr"],
    "여수": ["eminwon.yeosu.go.kr"], "창원": ["eminwon.changwon.go.kr"], "군산": ["eminwon.gunsan.go.kr"], "익산": ["eminwon.iksan.go.kr"],
    "평택": ["eminwon.pyeongtaek.go.kr"], "화성": ["eminwon.hscity.go.kr", "eminwon.hwaseong.go.kr"], "광명": ["eminwon.gm.go.kr", "eminwon.gwangmyeong.go.kr"],
    "서산": ["eminwon.seosan.go.kr"], "보령": ["eminwon.brcn.go.kr", "eminwon.boryeong.go.kr"], "금산": ["eminwon.geumsan.go.kr"],
    "청주": ["eminwon.cheongju.go.kr"], "천안": ["eminwon.cheonan.go.kr"], "동해": ["eminwon.dh.go.kr", "eminwon.donghae.go.kr"],
    "양산": ["eminwon.yangsan.go.kr"], "창녕": ["eminwon.cng.go.kr", "eminwon.changnyeong.go.kr"], "곡성": ["eminwon.gokseong.go.kr"],
    "봉화": ["eminwon.bonghwa.go.kr"], "구미": ["eminwon.gumi.go.kr"], "울주": ["eminwon.ulju.ulsan.kr", "eminwon.ulju.go.kr"],
    "울산남구": ["eminwon.ulsannamgu.go.kr", "eminwon.namgu.ulsan.kr"], "울산북구": ["eminwon.bukgu.ulsan.kr"], "울산동구": ["eminwon.donggu.ulsan.kr"],
    "인천부평": ["eminwon.icbp.go.kr"], "부산강서": ["eminwon.bsgangseo.go.kr"], "광주광산": ["eminwon.gwangsan.go.kr"], "대전대덕": ["eminwon.daedeok.go.kr"],
    "온산(울주)": [], "영주": ["eminwon.yeongju.go.kr"], "진천": ["eminwon.jincheon.go.kr"], "음성": ["eminwon.eumseong.go.kr"],
}


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


def try_city(item):
    city, hosts = item
    res = []
    for h in hosts:
        for scheme in ("https", "http"):
            t0 = time.time()
            try:
                r = requests.post(f"{scheme}://{h}{PATH}", data=DATA, headers={**UA, "Referer": f"{scheme}://{h}{PATH}"}, timeout=20)
                t = text_of(r.text)
                total = re.search(r"전체게시물\s*:\s*([\d,]+)", t)
                first = re.search(r"(고시|공고)\s*제[\d-]+호 ¦ ([^¦]{0,60})", t)
                res.append(f"{city} {scheme}://{h} HTTP {r.status_code} {time.time()-t0:.1f}s total={total.group(1) if total else None} first={first.group(2).strip() if first else None}")
                if total:
                    return res
                break
            except Exception as e:  # noqa: BLE001
                res.append(f"{city} {scheme}://{h} EXC {type(e).__name__} {time.time()-t0:.1f}s")
    return res


out = []
with ThreadPoolExecutor(6) as ex:
    for lines in ex.map(try_city, HOSTS.items()):
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
