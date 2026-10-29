"""격리 탐침 39: 무역위원회 — 위원회 일정 행 링크·상세 안건, 진척된 사건의 진행일정 표, 보도자료 상세 날짜."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
SITE = "https://www.ktc.go.kr"
out = []


def text(b):
    b = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", b)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b)).strip()


def after(t, key, n):
    i = t.find(key)
    return t[i:i + n] if i >= 0 else f"[{key} 없음]"


s = requests.Session()
s.get(SITE + "/", headers=UA, timeout=40)
H = {**UA, "Referer": SITE + "/"}
r = s.post(SITE + "/noticeScheduleList.do", data={"menuId": "24"}, headers=H, timeout=40)
tr = [t for t in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", r.text) if "<td" in t]
a = re.search(r"<a [^>]*>", tr[0])
out.append("sched row0 a=" + (a.group(0)[:400] if a else re.sub(r"\s+", " ", tr[0])[:400]))
href = re.search(r'href="(/[^"]+)"', tr[0])
if href:
    d = s.get(SITE + href.group(1).replace("&amp;", "&"), headers=H, timeout=40)
    t = text(d.text)
    out.append(f"sched detail HTTP {d.status_code} " + after(t, "제478차", 1400))
for mid, code in (("00000789", "10100002"), ("00000845", "10100002"), ("00000868", "10100001")):
    d = s.post(SITE + "/viewInvest.do", data={"menuId": "11", "masterId": mid, "invstg_type_code": code}, headers=H, timeout=40)
    t = text(d.text)
    out.append(f"inv {mid} " + after(t, "조사번호 구제", 260) + " ‖ " + after(t, "진행단계 진행일", 260) + " ‖ " + after(t, "단계 처리내역 공개자료", 700))
d = s.get(SITE + "/boardView.do?bbs_id=00002297&menuId=57&pageIndex=1&searchCondition=&searchKeyword=", headers=H, timeout=40)
t = text(d.text)
out.append(f"news detail HTTP {d.status_code} " + after(t, "무역위, 중국산 아연도금냉연", 600))
for i, x in enumerate(out):
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    for j in range(0, min(len(x), 3600), 1200):
        print(f"::notice title=aw-{i:02d}-{j // 1200}::{x[j:j + 1200]}")
