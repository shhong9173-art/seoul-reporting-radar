"""격리 탐침 32: 울산 남구 새올 목록 형식, 포항·광양·평택·양산·창녕 접속(새올 60초·본 누리집)."""
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
LIST = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "30", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": "", "pageIndex": "1"}
out = []
try:
    r = requests.post("https://eminwon.ulsannamgu.go.kr" + PATH, data=LIST, headers={**UA, "Referer": "https://eminwon.ulsannamgu.go.kr" + PATH}, timeout=60)
    b = r.text
    trs = [t for t in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", b) if "<td" in t]
    out.append(f"namgu HTTP {r.status_code} len={len(b)} trs={len(trs)} searchDetail={len(re.findall('searchDetail', b))} title={re.search(r'<title>([^<]*)', b).group(1) if re.search(r'<title>([^<]*)', b) else None}")
    out.append("namgu rows=" + re.sub(r"\s+", " ", " || ".join(trs[1:3]))[:1500])
    if not trs:
        out.append("namgu body=" + re.sub(r"\s+", " ", re.sub(r"<script[\s\S]*?</script>", "", b))[:1500])
except Exception as e:  # noqa: BLE001
    out.append(f"namgu EXC {type(e).__name__}")
for name, eminwon, home in (("포항", "https://eminwon.pohang.go.kr", "https://www.pohang.go.kr/"), ("광양", "https://eminwon.gwangyang.go.kr", "https://www.gwangyang.go.kr/"),
                            ("평택", "https://eminwon.pyeongtaek.go.kr", "https://www.pyeongtaek.go.kr/"), ("양산", "https://eminwon.yangsan.go.kr", "https://www.yangsan.go.kr/"),
                            ("창녕", "https://eminwon.cng.go.kr", "https://www.cng.go.kr/")):
    for label, fn in (("eminwon60", lambda: requests.post(eminwon + PATH, data=LIST, headers={**UA, "Referer": eminwon + PATH}, timeout=60)),
                      ("home", lambda: requests.get(home, headers=UA, timeout=30))):
        t0 = time.time()
        try:
            r = fn()
            out.append(f"{name} {label} HTTP {r.status_code} {time.time()-t0:.0f}s len={len(r.text)} rows={len(re.findall('searchDetail', r.text))}")
        except Exception as e:  # noqa: BLE001
            out.append(f"{name} {label} EXC {type(e).__name__} {time.time()-t0:.0f}s")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
