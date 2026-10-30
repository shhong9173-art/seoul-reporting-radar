"""격리 탐침 45b: CLIK 오픈API 안내 주소 찾기, minutes.do 인자 오류 문구(키 없이)."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9"}
out = []
r = requests.get("https://clik.nanet.go.kr/", headers=UA, timeout=30)
for m in re.finditer(r"<a[^>]*>[^<]*Open API[^<]*</a>", r.text):
    out.append("anchor " + re.sub(r"\s+", " ", m.group(0))[:300])
for m in re.finditer(r"Open API", r.text):
    out.append("ctx " + re.sub(r"\s+", " ", r.text[max(0, m.start() - 300):m.start() + 50])[:350])
    if len(out) > 6:
        break
for path in ("/potal/openapi/guide.do", "/potal/guide/openapi.do", "/potal/openApi/openApiGuide.do", "/openapi/", "/openapi/bill.do", "/openapi/minutes.do?key=x&type=json"):
    try:
        g = requests.get("https://clik.nanet.go.kr" + path, headers=UA, timeout=30)
        out.append(f"{path} HTTP {g.status_code} {re.sub(r'\\s+', ' ', re.sub(r'<[^>]+>', ' ', g.text))[:200]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{path} {type(e).__name__}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
