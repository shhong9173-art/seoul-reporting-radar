"""Probe 91: 전남광주통합특별시 보도자료 목록(boardId=JG_0000000003) 행 형식·게시판 이름, 경북 보도자료 목록 li 앞부분(제목 칸) 형식(공개, 한 번씩)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
try:
    r = requests.get("https://www.jeonnam-gwangju.go.kr/boardList.do", params={"boardId": "JG_0000000003", "pageId": "jngj22"}, headers=H, timeout=30)
    t = r.text
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    body = t.split("<tbody", 1)[-1].split("</tbody>", 1)[0] if "<tbody" in t else ""
    trs = re.split(r"(?=<tr[\s>])", body)[1:]
    out.append(f"jg HTTP {r.status_code} title {re.sub(r'\\s+', ' ', title.group(1))[:80] if title else '-'} trs {len(trs)} fields {sorted(set(re.findall(r'name=\"([A-Za-z_]+)\"', t)))[:20]}")
    if trs:
        out.append("  row " + re.sub(r"\s+", " ", trs[0])[:800])
    else:
        i = t.find("boardView.do")
        out.append("  ctx " + re.sub(r"\s+", " ", t[max(0, i - 300):i + 700]))
except Exception as e:  # noqa: BLE001
    out.append(f"jg {type(e).__name__} {str(e)[:60]}")
try:
    r = requests.get("https://www.gb.go.kr/page/10107/10004.do", headers=H, timeout=30)
    t = r.text
    k = t.find('<div class="classify">')
    li = t.rfind("<li", 0, k)
    out.append(f"gb HTTP {r.status_code} li-count {t.count('<div class=\"classify\">')}")
    out.append("  li " + re.sub(r"\s+", " ", t[li:li + 700]))
    pg = re.findall(r'(?:href|onclick)="([^"]*(?:page|Page)[^"]*)"[^>]*>\s*(?:<[^>]+>)?\s*2\s*<', t)
    out.append(f"  page2 {pg[:3]}")
except Exception as e:  # noqa: BLE001
    out.append(f"gb {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
