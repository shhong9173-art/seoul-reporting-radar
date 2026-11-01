"""Probe 93: USPTO 상표 일일 XML(TRTDXFAP)을 키 없이 받을 수 있는지 — ODP 목록 API·웹 페이지·옛 bulkdata 주소에 각 한 번(공개 데이터, 응답 코드·크기만)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for url in ("https://api.uspto.gov/api/v1/datasets/products/TRTDXFAP",
            "https://api.uspto.gov/api/v1/datasets/products/TRTDXFAP?latest=true",
            "https://data.uspto.gov/bulkdata/datasets/trtdxfap",
            "https://bulkdata.uspto.gov/data/trademark/dailyxml/applications/",
            "https://data.uspto.gov/ui/datasets/products/TRTDXFAP"):
    try:
        r = requests.get(url, headers=H, timeout=40, allow_redirects=True)
        t = r.text
        files = re.findall(r"apc\d{6}[^\"'<> ]*\.zip", t)
        out.append(f"{url} -> HTTP {r.status_code} final {r.url[:90]} ctype {r.headers.get('content-type','')[:40]} len {len(t)} zips {len(files)} {files[:3]}")
        if r.status_code != 200 or len(t) < 600:
            out.append("  head " + re.sub(r"\s+", " ", t[:300]))
    except Exception as e:  # noqa: BLE001
        out.append(f"{url} {type(e).__name__} {str(e)[:80]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
