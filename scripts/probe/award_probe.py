"""격리 탐침 29: 새올 고시공고 행 HTML(상세 열기 인자), 상세 주소 형식, 쪽 크기 30 허용 여부(울주·당진)."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
BASE = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "30", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A", "pageIndex": "1",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": ""}
out = []
for host, kw in (("http://eminwon.ulju.ulsan.kr", "고려아연"), ("https://eminwon.dangjin.go.kr", "")):
    try:
        r = requests.post(host + PATH, data={**BASE, "not_ancmt_sj": kw}, headers={**UA, "Referer": host + PATH}, timeout=40)
        b = r.text
        rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", b)
        body_rows = [x for x in rows if "제" in x and "호" in x]
        out.append(f"{host} kw={kw} HTTP {r.status_code} rows={len(body_rows)}")
        if body_rows:
            out.append("row0=" + re.sub(r"\s+", " ", body_rows[0])[:900])
        js = sorted(set(re.findall(r"(?:href|onclick)=\"(javascript:[^\"]{0,120})\"", b)))[:8]
        out.append(f"js={js}")
        fn = re.search(r"function\s+(searchDetail|goDetail|fn_detail|viewDetail)\s*\([^)]*\)\s*\{([\s\S]{0,700})", b)
        out.append("fn=" + (re.sub(r"\s+", " ", fn.group(0))[:700] if fn else "none"))
    except Exception as e:  # noqa: BLE001
        out.append(f"{host} EXC {type(e).__name__}")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
