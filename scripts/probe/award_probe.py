"""격리 탐침 45: 지방의회 회의록(국회도서관 지방의정포털 CLIK) — 누리집·오픈API 안내 접속, API 주소·변수 찾기. 국회 회의록 API(열린국회정보) 회의록 목록 연산 이름."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
out = []
for url in ("https://clik.nanet.go.kr/", "https://clik.nanet.go.kr/potal/guide/openApiInfo.do", "https://clik.nanet.go.kr/potal/openapi/openApiInfo.do",
            "https://clik.nanet.go.kr/openapi/minutes.do", "https://clik.nanet.go.kr/potal/main/openApi.do"):
    try:
        r = requests.get(url, headers=UA, timeout=30)
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[\s\S]*?</\1>", " ", r.text)))
        links = sorted(set(re.findall(r'href="([^"]*(?:[Aa]pi|API|openapi|OpenApi)[^"]*)"', r.text)))[:15]
        i = t.find("API")
        out.append(f"{url} HTTP {r.status_code} len={len(r.text)} links={links} text={t[max(0, i - 200):i + 900] if i >= 0 else t[:300]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{url} {type(e).__name__}: {str(e)[:120]}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
