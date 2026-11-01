"""Probe 88: 시·도 보도자료 목록 원본 행 형식(울산·전남·충남·경북) — 파서 설계용, 목록 첫 쪽 한 번씩(공개)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for name, url in [("울산", "https://www.ulsan.go.kr/u/rep/bbs/list.ulsan?bbsId=BBS_0000000000000027&mId=001004003001000000"),
                  ("전남", "https://www.jeonnam.go.kr/M7116/boardList.do?menuId=jeonnam0202000000"),
                  ("충남", "https://www.chungnam.go.kr/cnportal/cnapcPressList/cnapcPress/list.do?menuNo=500498"),
                  ("경북", "https://www.gb.go.kr/page/link.do?mn=10107&pageNo=10004")]:
    try:
        r = requests.get(url, headers=H, timeout=30)
        t = r.text
        body = t.split("<tbody", 1)[-1].split("</tbody>", 1)[0] if "<tbody" in t else ""
        trs = re.split(r"(?=<tr[\s>])", body)[1:]
        out.append(f"{name} HTTP {r.status_code} final {r.url[:120]} len {len(t)} trs {len(trs)}")
        if trs:
            out.append("  row " + re.sub(r"\s+", " ", trs[0])[:900])
        else:
            i = t.find("보도")
            out.append("  noTbody ctx " + re.sub(r"\s+", " ", t[i:i + 600]))
        dates = re.findall(r"20\d\d[-.]\d\d[-.]\d\d", t)
        out.append(f"  dates {dates[:5]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{name} {type(e).__name__} {str(e)[:60]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
