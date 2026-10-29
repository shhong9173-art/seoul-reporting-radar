"""격리 탐침 37: 무역위원회 — 진행 사건 행(viewInvest)·쪽 넘김 인자, 위원회 일정·보도자료 행과 상세 함수."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
SITE = "https://www.ktc.go.kr"
out = []


def cells(tr):
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)]


s = requests.Session()
s.get(SITE + "/", headers=UA, timeout=40)
for path, mid in (("/proInvestList.do", "11"), ("/noticeScheduleList.do", "24"), ("/reportNewsList.do", "57"), ("/comInvestList.do", "12")):
    r = s.post(SITE + path, data={"menuId": mid}, headers={**UA, "Referer": SITE + "/"}, timeout=40)
    b = r.text
    trs = [t for t in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", b) if "<td" in t]
    out.append(f"{path} HTTP {r.status_code} rows={len(trs)} first3={[cells(t)[:6] for t in trs[:3]]}")
    out.append(f"{path} onclicks={sorted(set(re.findall(r'(javascript:[A-Za-z_]+\\([^)]*\\))', b)))[:6]}")
    for fn in ("viewInvest", "goView", "fn_view", "goPage", "fn_link_page", "linkPage", "goList"):
        m = re.search(r"function\s+" + fn + r"\s*\([^)]*\)\s*\{[\s\S]{0,400}", b)
        if m:
            out.append(f"{path} {fn}=" + re.sub(r"\s+", " ", m.group(0))[:400])
    pag = sorted(set(re.findall(r"(?:fn_link_page|linkPage|goPage|fn_egov_link_page)\((\d+)\)", b)))[:5]
    hidden = sorted(set(re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"', b)))[:25]
    out.append(f"{path} pager={pag} hidden={hidden}")
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
