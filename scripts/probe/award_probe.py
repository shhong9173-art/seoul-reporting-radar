"""격리 탐침 49: 수질TMS 배출량 API(15164812) 요청 주소 찾기 — 데이터 페이지 HTML의 swagger·apis 주소, odcloud 문서."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
out = []
r = requests.get("https://www.data.go.kr/data/15164812/openapi.do", headers=UA, timeout=40)
b = r.text
out.append(f"page HTTP {r.status_code} len={len(b)}")
for pat in (r"https?://apis\.data\.go\.kr/[A-Za-z0-9_/\-.]+", r"swagger[^\"' ]{0,200}", r"infuser\.odcloud\.kr[^\"' ]{0,120}", r"publicDataDetailPk[^\"']{0,60}",
            r"oprtinUrl[^\n]{0,200}", r"/B552584/[A-Za-z0-9_/]+", r"oprtinSeqNo[^\n]{0,80}", r"swaggerJson[^\n]{0,300}", r"var\s+swagger[^\n]{0,300}"):
    hits = sorted(set(re.findall(pat, b)))[:8]
    out.append(f"{pat[:30]} → {hits}")
i = b.find("swagger")
out.append("ctx " + re.sub(r"\s+", " ", b[max(0, i - 300):i + 600]) if i >= 0 else "swagger 없음")
for u in ("https://infuser.odcloud.kr/oas/docs?namespace=15164812/v1", "https://www.data.go.kr/catalog/15164812/openapi.json"):
    try:
        g = requests.get(u, headers=UA, timeout=40)
        out.append(f"{u} HTTP {g.status_code} {re.sub(r'\\s+', ' ', g.text)[:900]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{u} {type(e).__name__}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
