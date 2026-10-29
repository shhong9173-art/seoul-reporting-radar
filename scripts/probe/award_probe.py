"""격리 탐침 26: 새올 고시공고 1.3KB 응답의 정체, 목록 실제 주소, BSE 공시 인자."""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6"}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


s = requests.Session()
base = "https://eminwon.dangjin.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
r = s.get(base + "?method=selectListOfrNotAncmt&methodnm=selectListOfrNotAncmtHomepage&homepage_pbs_yn=Y&subCheck=Y&ofr_pageSize=10&not_ancmt_se_code=01,02,03,04,05&initValue=Y&countYn=Y&list_gubun=A", headers=UA, timeout=30)
out.append(f"dangjin GET body={re.sub(chr(10), ' ', r.text)[:1300]!r}")
data = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "10", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A", "pageIndex": "1",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": ""}
r2 = s.post(base, data=data, headers={**UA, "Referer": base}, timeout=30)
t = text_of(r2.text)
out.append(f"dangjin POST HTTP {r2.status_code} len={len(r2.text)} text={t[:1500]}")
time.sleep(1)
# BSE variations
H = {"Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com", "Accept": "application/json, text/plain, */*", **UA}
for q in ("pageno=1&strCat=-1&strPrevDate=20260901&strScrip=544274&strSearch=P&strToDate=20261030&strType=C&subcategory=-1",
          "pageno=1&strCat=-1&strPrevDate=&strScrip=544274&strSearch=A&strToDate=&strType=C&subcategory=-1"):
    try:
        r = requests.get("https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?" + q, headers=H, timeout=30)
        try:
            d = r.json()
            rows = d.get("Table") or []
            out.append(f"bse {q[:60]} HTTP {r.status_code} n={len(rows)} " + " ; ".join(f"{x.get('NEWS_DT')}|{x.get('HEADLINE') or x.get('NEWSSUB')}"[:150] for x in rows[:6]))
        except ValueError:
            out.append(f"bse HTTP {r.status_code} head={r.text[:200]!r}")
    except Exception as e:  # noqa: BLE001
        out.append(f"bse EXC {type(e).__name__}")
    time.sleep(1)

packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
