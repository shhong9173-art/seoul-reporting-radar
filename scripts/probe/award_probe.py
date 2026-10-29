"""격리 탐침 25: 새 원천 후보 접속·형식(공개 자료만, 키 값 미출력).
(a) 지자체 새올 고시공고(eminwon) — 당진·포항·광양·구미·아산·울산 남구·여수·창원
(b) 인도 BSE 공시(현대차 인도법인 544274)  (c) ADB 계약 낙찰 목록
(d) 국민연금 가입 사업장(공공데이터 3046071) — 지금 키로 되는지"""
import os
import re
import sys
import time

import requests

sys.path.insert(0, "scripts")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6"}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


def hit(label, url, method="GET", **kw):
    t0 = time.time()
    try:
        r = requests.request(method, url, headers={**UA, **kw.pop("headers", {})}, timeout=30, **kw)
        return r, f"{label}: HTTP {r.status_code} {time.time()-t0:.1f}s len={len(r.text)}"
    except Exception as e:  # noqa: BLE001
        return None, f"{label}: EXC {type(e).__name__} {time.time()-t0:.1f}s"


# (a) 새올 고시공고
Q = ("method=selectListOfrNotAncmt&methodnm=selectListOfrNotAncmtHomepage&homepage_pbs_yn=Y&subCheck=Y&ofr_pageSize=10"
     "&not_ancmt_se_code=01,02,03,04,05&title=%EA%B3%A0%EC%8B%9C%EA%B3%B5%EA%B3%A0&cha_dep_code_nm=&initValue=Y&countYn=Y&list_gubun=A&not_ancmt_sj=&not_ancmt_cn=")
for city in ("dangjin", "pohang", "gwangyang", "gumi", "asan", "namgu.ulsan", "yeosu", "changwon"):
    for host in (f"https://eminwon.{city}.go.kr", f"http://eminwon.{city}.go.kr"):
        r, line = hit(f"eminwon {city}", f"{host}/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do?{Q}")
        if r is not None:
            t = text_of(r.text)
            i = t.find("고시")
            out.append(line + f" {host[:5]} :: {t[i:i+500] if r.status_code == 200 else ''}")
            break
        out.append(line + f" {host[:5]}")
    time.sleep(0.5)

# (b) BSE
r, line = hit("bse", "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1&strPrevDate=20261001&strScrip=544274&strSearch=P&strToDate=20261030&strType=C",
              headers={"Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com", "Accept": "application/json"})
if r is not None:
    try:
        d = r.json()
        rows = d.get("Table") or []
        out.append(line + f" n={len(rows)} :: " + " ; ".join(f"{x.get('NEWS_DT')}|{x.get('HEADLINE') or x.get('NEWSSUB')}"[:160] for x in rows[:5]))
    except ValueError:
        out.append(line + f" non-json head={r.text[:150]!r}")
else:
    out.append(line)

# (c) ADB contracts awarded
r, line = hit("adb", "https://www.adb.org/projects/contracts-awarded")
if r is not None:
    t = text_of(r.text)
    k = [m.start() for m in re.finditer(r"Korea", t)][:2]
    out.append(line + f" korea={len(re.findall('Korea', t))} :: " + " ;; ".join(t[max(0, i-250): i+150] for i in k))
else:
    out.append(line)

# (d) 국민연금 사업장
key = (os.environ.get("KR_FUEL_API_KEY") or os.environ.get("DATA_GO_KR_KEY") or "").strip()
for op in ("getBassInfoSearchV2", "getBassInfoSearch"):
    r, line = hit(f"nps {op}", f"https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/{op}",
                  params={"serviceKey": key, "wkplNm": "현대자동차", "pageNo": 1, "numOfRows": 3, "dataType": "json"})
    body = (r.text if r is not None else "")
    for v in (key,):
        if v:
            body = body.replace(v, "<KEY>")
    code = re.search(r"<(?:returnReasonCode|resultCode)>([^<]+)", body) or re.search(r'"resultCode"\s*:\s*"?([^",}]+)', body)
    out.append(line + f" code={code.group(1) if code else None} head={re.sub(chr(10), ' ', body[:300])!r}")

packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
