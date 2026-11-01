"""Probe 86: 정책브리핑 보도자료 목록 — 청 단위 코드(관세청 B00003·조달청 B00013) 거르기가 되는지, 첫 쪽 제목·날짜(공개 목록, 각 한 번)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
URL = "https://www.korea.kr/briefing/pressReleaseList.do"
ROW = re.compile(r'pressReleaseView\.do\?newsId=(\d+)[^"]*">\s*<span class="text">\s*<strong>(.*?)</strong>.*?<span class="source">\s*<span>([\d.\-]+)</span>\s*<span>([^<]+)</span>', re.S)
out = []
for name, c in (("관세청", "B00003"), ("조달청", "B00013")):
    rr = requests.get(URL, params={"repCodeType": c[0], "repCode": c}, headers=H, timeout=30)
    rows = ROW.findall(rr.text)
    tot = re.search(r"총\s*<strong>([\d,]+)", rr.text)
    out.append(f"{name} {c} HTTP {rr.status_code} rows {len(rows)} total {tot.group(1) if tot else '-'} depts {sorted({d.strip() for *_, d in rows})}")
    for nid, title, date, _ in rows[:20]:
        out.append(f"  {date} {nid} | {re.sub(r'<[^>]+>', '', title).strip()[:70]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
