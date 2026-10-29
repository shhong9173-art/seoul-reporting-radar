"""격리 탐침 38: 무역위원회 — 진행 사건 상세(viewInvest.do)의 단계·일정, 위원회 일정·보도자료의 행 링크와 상세 본문."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
SITE = "https://www.ktc.go.kr"
out = []


def text(b):
    b = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", b)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b)).strip()


s = requests.Session()
s.get(SITE + "/", headers=UA, timeout=40)
H = {**UA, "Referer": SITE + "/"}
r = s.post(SITE + "/proInvestList.do", data={"menuId": "11"}, headers=H, timeout=40)
tr = [t for t in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", r.text) if "<td" in t]
out.append("row0 raw=" + re.sub(r"\s+", " ", tr[0])[:700])
calls = re.findall(r"viewInvest\(\s*'([^']+)'\s*,\s*'([^']+)'\s*\)", r.text)
out.append(f"viewInvest calls={calls[:12]}")
vf = re.search(r'<form[^>]*id="viewForm"[\s\S]*?</form>', r.text)
out.append("viewForm=" + (re.sub(r"\s+", " ", vf.group(0))[:500] if vf else "없음"))
if calls:
    mid, code = calls[0]
    d = s.post(SITE + "/viewInvest.do", data={"menuId": "11", "masterId": mid, "invstg_type_code": code}, headers=H, timeout=40)
    t = text(d.text)
    i = t.find("조사")
    out.append(f"viewInvest HTTP {d.status_code} len={len(d.text)} text=" + t[max(0, i - 200):i + 2600])
for path, mid in (("/noticeScheduleList.do", "24"), ("/reportNewsList.do", "57")):
    r = s.post(SITE + path, data={"menuId": mid}, headers=H, timeout=40)
    tr = [t for t in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", r.text) if "<td" in t]
    out.append(f"{path} row0 raw=" + re.sub(r"\s+", " ", tr[0])[:700])
    fns = sorted(set(re.findall(r"function\s+([A-Za-z_]+)\s*\(", r.text)))
    out.append(f"{path} fns={fns[:30]}")
    forms = [re.sub(r"\s+", " ", f)[:300] for f in re.findall(r"<form[^>]*>", r.text)]
    out.append(f"{path} forms={forms}")
    m = re.search(r"onclick=\"([A-Za-z_]+)\(([^)]*)\)", tr[0])
    if m:
        fn = m.group(1)
        body = re.search(r"function\s+" + fn + r"\s*\([^)]*\)\s*\{[\s\S]{0,500}", r.text)
        out.append(f"{path} {fn}=" + (re.sub(r"\s+", " ", body.group(0))[:500] if body else "본문 없음"))
packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    while x:
        room = 3800 - len(cur) - 3
        if room < 200:
            packs.append(cur); cur = ""; continue
        cur += (" ‖ " if cur else "") + x[:room]; x = x[room:]
packs.append(cur)
for i, p in enumerate(packs[:12]):
    print(f"::notice title=aw-{i:02d}::{p}")
