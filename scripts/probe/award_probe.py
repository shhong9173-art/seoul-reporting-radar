"""Probe 82: 정책브리핑 보도자료 목록 부처 거르기 매개변수 — 기후에너지환경부(A00019) 조합 세 가지를 한 번씩, 행마다 날짜·부처만 본다(공개 목록)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
URL = "https://www.korea.kr/briefing/pressReleaseList.do"
out = []
for label, params in [("repCode", {"repCodeType": "A", "repCode": "A00019"}),
                      ("srchRepCodeType", {"srchRepCodeType": "A00019"}),
                      ("deptCode", {"deptCode": "A00019"})]:
    try:
        r = requests.get(URL, params=params, headers=H, timeout=30)
        rows = re.findall(r'pressReleaseView\.do\?newsId=(\d+)[^"]*">\s*<span class="text">\s*<strong>(.*?)</strong>.*?<span class="source">\s*<span>([\d.]+)</span>\s*<span>([^<]+)</span>', r.text, re.S)
        depts = {}
        for _, _, _, d in rows:
            depts[d.strip()] = depts.get(d.strip(), 0) + 1
        out.append(f"{label} HTTP {r.status_code} rows {len(rows)} depts {depts}")
        for nid, title, date, dept in rows[:3]:
            out.append(f"  {date} {dept.strip()} {nid} | {re.sub(r'<[^>]+>', '', title)[:60]}")
        tot = re.search(r"총\s*<[^>]*>\s*([\d,]+)|([\d,]+)\s*건", r.text)
        out.append(f"  total {tot.group(0)[:40] if tot else '-'}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{label} {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
