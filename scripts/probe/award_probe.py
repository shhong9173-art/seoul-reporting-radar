"""격리 탐침 41: 무역위원회 — 회의 개요 PDF(dltncFileDownload.do) 받아 안건 본문 읽기."""
import io
import re

import requests
from pypdf import PdfReader

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
SITE = "https://www.ktc.go.kr"
out = []
s = requests.Session()
s.get(SITE + "/", headers=UA, timeout=40)
for did, seq in (("00000311", "0000"), ("00000310", "0002")):
    ref = f"{SITE}/noticeScheduleView.do?dltnc_id={did}&menuId=24&pageIndex=1&searchCondition=&searchKeyword="
    s.get(ref, headers=UA, timeout=40)
    f = s.get(SITE + "/dltncFileDownload.do", params={"dltnc_id": did, "seq_no": seq}, headers={**UA, "Referer": ref}, timeout=60)
    out.append(f"{did} GET HTTP {f.status_code} type={f.headers.get('Content-Type')} disp={f.headers.get('Content-Disposition', '')[:80]} bytes={len(f.content)} head={f.content[:5]!r}")
    if f.content[:4] != b"%PDF":
        f = s.post(SITE + "/dltncFileDownload.do", data={"dltnc_id": did, "seq_no": seq}, headers={**UA, "Referer": ref}, timeout=60)
        out.append(f"{did} POST HTTP {f.status_code} type={f.headers.get('Content-Type')} bytes={len(f.content)} head={f.content[:5]!r}")
    if f.content[:4] == b"%PDF":
        r = PdfReader(io.BytesIO(f.content))
        txt = " ".join((p.extract_text() or "") for p in r.pages)
        out.append(f"{did} pages={len(r.pages)} text=" + re.sub(r"\s+", " ", txt)[:2400])
for i, x in enumerate(out):
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    for j in range(0, min(len(x), 3600), 1200):
        print(f"::notice title=aw-{i:02d}-{j // 1200}::{x[j:j + 1200]}")
