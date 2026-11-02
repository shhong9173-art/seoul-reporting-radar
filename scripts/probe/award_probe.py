"""Probe 94: 공장등록 API(B550624 fctryRegistInfo) 응답 — 월 08:10 실행에서 43곳 모두 ReadTimeout·결과코드 None. 지금 한 번(공개, 회사 하나)."""
import os
import re
import time

import requests

KEY = (os.environ.get("DATA_GO_KR_KEY") or os.environ.get("CUSTOMS_API_KEY") or "").strip()
H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = [f"key length {len(KEY)}"]
for typ in ("json",):
    t0 = time.time()
    try:
        r = requests.get("https://apis.data.go.kr/B550624/fctryRegistInfo/getFctryPrdctnService_v2",
                         params={"serviceKey": KEY, "pageNo": 1, "numOfRows": 5, "type": typ, "cmpnyNm": "현대제철"}, headers=H, timeout=60)
        t = r.text.replace(KEY, "<KEY>") if KEY else r.text
        out.append(f"{typ} HTTP {r.status_code} {time.time()-t0:.1f}s len {len(t)} ctype {r.headers.get('content-type','')[:40]}")
        out.append("  head " + re.sub(r"\s+", " ", t[:400]))
    except Exception as e:  # noqa: BLE001
        out.append(f"{typ} {type(e).__name__} {time.time()-t0:.1f}s {str(e)[:80]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
