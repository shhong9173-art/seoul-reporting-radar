"""Probe 85: 정책브리핑 보도자료 목록 — 부처 코드표(chkRepCode)와 국토교통부·기후에너지환경부 거른 첫 쪽 제목·날짜(공개 목록, 각 한 번)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
URL = "https://www.korea.kr/briefing/pressReleaseList.do"
out = []
r = requests.get(URL, headers=H, timeout=30)
codes = re.findall(r'name="chkRepCode" type="checkbox" value="([A-Z]\d+)" id="[^"]*"\s*/>\s*<label for="[^"]*"\s*>\s*([^<]+?)\s*<', r.text)
out.append("codes " + ", ".join(f"{n}={c}" for c, n in codes))
code = {n: c for c, n in codes}
ROW = re.compile(r'pressReleaseView\.do\?newsId=(\d+)[^"]*">\s*<span class="text">\s*<strong>(.*?)</strong>.*?<span class="source">\s*<span>([\d.\-]+)</span>\s*<span>([^<]+)</span>', re.S)
for name in ("국토교통부", "기후에너지환경부"):
    c = code.get(name)
    if not c:
        out.append(f"{name} code 없음")
        continue
    rr = requests.get(URL, params={"repCodeType": c[0], "repCode": c}, headers=H, timeout=30)
    rows = ROW.findall(rr.text)
    tot = re.search(r"총\s*<strong>([\d,]+)", rr.text)
    out.append(f"{name} {c} HTTP {rr.status_code} rows {len(rows)} total {tot.group(1) if tot else '-'} depts {sorted({d.strip() for *_, d in rows})}")
    for nid, title, date, _ in rows[:20]:
        out.append(f"  {date} {nid} | {re.sub(r'<[^>]+>', '', title).strip()[:70]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
