"""Probe 89: 울산·충남 보도자료 목록 쪽 넘김 매개변수 — 쪽 번호 링크·form 칸 이름(공개, 사이트당 한 번)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for name, url in [("울산", "https://www.ulsan.go.kr/u/rep/bbs/list.ulsan?bbsId=BBS_0000000000000027&mId=001004003001000000"),
                  ("충남", "https://www.chungnam.go.kr/cnportal/cnapcPressList/cnapcPress/list.do?menuNo=500498")]:
    try:
        r = requests.get(url, headers=H, timeout=30)
        t = r.text
        i = t.find("paging") if "paging" in t else t.find("page")
        pg = re.findall(r'<a[^>]+(?:href|onclick)="([^"]*(?:[Pp]age|goPage|fn_)[^"]*)"[^>]*>\s*2\s*<', t)
        names = sorted(set(re.findall(r'name="([A-Za-z_]+)"', t)))
        out.append(f"{name} HTTP {r.status_code} page2 links {pg[:3]} fields {names[:30]}")
        j = t.find(">2<")
        out.append("  ctx " + re.sub(r"\s+", " ", t[max(0, j - 400):j + 100]))
    except Exception as e:  # noqa: BLE001
        out.append(f"{name} {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
