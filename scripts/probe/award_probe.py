"""격리 탐침 42: 무역위원회 — 목록 쪽수(총 건수·goPageLink), 상세 표 원형(관리정보·진행일정), 보도자료 목록 날짜 유무."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
SITE = "https://www.ktc.go.kr"
out = []
s = requests.Session()
s.get(SITE + "/", headers=UA, timeout=40)
H = {**UA, "Referer": SITE + "/"}


def squeeze(x):
    x = re.sub(r"<!--[\s\S]*?-->", "", x)
    x = re.sub(r'\s(class|style|scope|width|summary|title)="[^"]*"', "", x)
    return re.sub(r"\s+", " ", x)


for path, mid in (("/proInvestList.do", "11"), ("/comInvestList.do", "12"), ("/noticeScheduleList.do", "24"), ("/reportNewsList.do", "57")):
    r = s.post(SITE + path, data={"menuId": mid}, headers=H, timeout=40)
    b = r.text
    tot = re.findall(r"(?:총|전체)\s*<?[^>]*>?\s*([\d,]+)\s*<?[^>]*>?\s*건", b)[:3]
    pages = sorted(set(re.findall(r"goPageLink\((\d+)\)", b)))
    trs = [t for t in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", b) if "<td" in t]
    last = squeeze(trs[-1])[:300] if trs else ""
    i = b.find("paging")
    out.append(f"{path} total={tot} goPageLink={pages[:8]} rows={len(trs)} lastrow={last} pagingHtml={squeeze(b[i:i + 300]) if i >= 0 else '없음'}")
    if path == "/proInvestList.do":
        r2 = s.post(SITE + path, data={"menuId": mid, "pageIndex": "2"}, headers=H, timeout=40)
        ids2 = re.findall(r"viewInvest\('(\d+)'", r2.text)
        out.append(f"{path} page2 ids={ids2[:12]}")
for mid, code in (("00000845", "10100002"), ("00000875", "10100001")):
    d = s.post(SITE + "/viewInvest.do", data={"menuId": "11", "masterId": mid, "invstg_type_code": code}, headers=H, timeout=40)
    b = d.text
    i = b.find("관리정보")
    j = b.find("질의서/답변서") if "질의서/답변서" in b else b.find("조사결과")
    out.append(f"inv {mid} raw=" + squeeze(b[i:j])[:2400])
for i, x in enumerate(out):
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    for j in range(0, min(len(x), 3600), 1200):
        print(f"::notice title=aw-{i:02d}-{j // 1200}::{x[j:j + 1200]}")
