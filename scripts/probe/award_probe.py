"""격리 탐침 40: 무역위원회 — 위원회 개최 안내 첨부 PDF(본회의 개요) 받기·본문 안건, 지난 회의 몇 건."""
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
H = {**UA, "Referer": SITE + "/"}
for did in ("00000311", "00000310"):
    d = s.get(f"{SITE}/noticeScheduleView.do?dltnc_id={did}&menuId=24&pageIndex=1&searchCondition=&searchKeyword=", headers=H, timeout=40)
    i = d.text.find("첨부파일")
    seg = re.sub(r"\s+", " ", d.text[i:i + 1500])
    out.append(f"{did} attach html=" + seg[:700])
    links = re.findall(r'(?:href|onclick)="([^"]*(?:[Dd]own|file)[^"]*)"', d.text[i:i + 3000])
    out.append(f"{did} links={links[:4]}")
    for ln in links[:2]:
        m = re.search(r"\(([^)]*)\)", ln)
        url = None
        if ln.startswith("/"):
            url = SITE + ln.replace("&amp;", "&")
        if url:
            f = s.get(url, headers={**H, "Referer": d.url}, timeout=60)
            ctype = f.headers.get("Content-Type", "")
            out.append(f"{did} get {url[:120]} HTTP {f.status_code} type={ctype} bytes={len(f.content)} head={f.content[:8]!r}")
            if f.content[:4] == b"%PDF":
                txt = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(f.content)).pages)
                out.append(f"{did} pdf text=" + re.sub(r"\s+", " ", txt)[:1800])
        else:
            out.append(f"{did} js-link {ln[:200]} args={m.group(1) if m else None}")
    fn = re.search(r"function\s+(fn_?[Ff]ile[A-Za-z_]*|fileDown[A-Za-z_]*|download[A-Za-z_]*)\s*\([^)]*\)\s*\{[\s\S]{0,400}", d.text)
    if fn:
        out.append(f"{did} fn=" + re.sub(r"\s+", " ", fn.group(0))[:400])
for i, x in enumerate(out):
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    for j in range(0, min(len(x), 3600), 1200):
        print(f"::notice title=aw-{i:02d}-{j // 1200}::{x[j:j + 1200]}")
