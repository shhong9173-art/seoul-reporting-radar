"""격리 탐침 30: 새올 고시공고 데이터 행 원본 HTML(당진·울주·여수·화성), 상세 GET 주소가 열리는지."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
LIST = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "30", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": "", "pageIndex": "1"}
out = []
for base in ("https://eminwon.dangjin.go.kr", "https://eminwon.asan.go.kr", "https://eminwon.yeosu.go.kr"):
    try:
        r = requests.post(base + PATH, data=LIST, headers={**UA, "Referer": base + PATH}, timeout=45)
        trs = re.findall(r"<tr[^>]*>[\s\S]*?</tr>", r.text)
        data = [t for t in trs if "<td" in t]
        rows_with = [t for t in data if re.search(r"\d{4}-\d{2}-\d{2}", t)]
        out.append(f"{base} trs={len(trs)} datarows={len(data)} dated={len(rows_with)} row=" + re.sub(r"\s+", " ", rows_with[0] if rows_with else "")[:900])
        m = re.search(r"searchDetail\(\s*['\"]([0-9A-Za-z_-]+)['\"]", r.text)
        if m:
            mgt = m.group(1)
            u = (f"{base}{PATH}?method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst&not_ancmt_mgt_no={mgt}"
                 "&homepage_pbs_yn=Y&subCheck=Y&jndinm=OfrNotAncmtEJB&context=NTIS")
            d = requests.get(u, headers=UA, timeout=45)
            t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", d.text))
            out.append(f"detail GET mgt={mgt} HTTP {d.status_code} len={len(d.text)} err={'장애' in d.text} text={t[t.find('제목'):t.find('제목')+400]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{base} EXC {type(e).__name__}")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
