"""probe 201: ① 관보 2026-22630 세율 표 줄 모양(4.20 앞뒤) ② 금속노조 지역소식(ce_B13)·지부회의/공문철(ce_B422)·노조일정(ce_B14) 목록
(robots Crawl-delay 180초를 지킨다). 저장 안 함."""
import re
import time

import requests

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


UA = {"User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"}
BUA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept-Language": "ko-KR,ko;q=0.9"}
try:
    meta = requests.get("https://www.federalregister.gov/api/v1/documents/2026-22630.json?fields[]=raw_text_url", headers=UA, timeout=40).json()
    body = requests.get(meta["raw_text_url"], headers=UA, timeout=40).text
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        if re.search(r"\.{3,}\s*\d", ln):
            log("ROW", i, "|", " || ".join(x.rstrip() for x in lines[max(0, i - 4): i + 2]))
except Exception as e:  # noqa: BLE001
    log("FR error", type(e).__name__, str(e)[:120])

for n, code in enumerate(("ce_B13", "ce_B422", "ce_B14")):
    if n:
        time.sleep(181)   # robots.txt Crawl-delay: 180
    try:
        r = requests.get(f"https://www.kmwu.kr/bbs/board.php?bo_table={code}", headers=BUA, timeout=40)
        rows = re.findall(r'href="[^"]*wr_id=(\d+)[^"]*"[^>]*>\s*(?:<[^>]+>\s*)*([^<]{2,120})<', r.text)
        dates = re.findall(r"\b(20\d\d[-.]\d\d[-.]\d\d|\d\d-\d\d)\b", r.text)
        seen, items = set(), []
        for wid, t in rows:
            t = re.sub(r"\s+", " ", t).strip()
            if wid in seen or len(t) < 4:
                continue
            seen.add(wid)
            items.append(f"{wid}:{t[:70]}")
        log("BOARD", code, r.status_code, len(r.text), "items", len(items), "dates", dates[:12], "|", " ; ".join(items[:30]))
    except Exception as e:  # noqa: BLE001
        log("BOARD", code, type(e).__name__, str(e)[:80])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
