"""Probe 50: 한전 전력사용량 한 번 더(같은 레이더 UA, 호출 간 10초) — 운영에서 되는 전자입찰을 대조로. 상태·필드 이름·건수만."""
import os
import time
import requests

KEY = os.environ.get("KEPCO_API_KEY", "").strip()
B = "https://bigdata.kepco.co.kr/openapi/v1"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for path, p in (("electContract.do", {"noticeBeginDate": "20261025", "noticeEndDate": "20261031"}),
                ("powerUsage/industryType.do", {"year": "2026", "month": "08", "metroCd": "44", "cityCd": "", "bizCd": ""}),
                ("powerUsage/contractType.do", {"year": "2026", "month": "08", "metroCd": "44", "cityCd": "", "cntrCd": ""})):
    time.sleep(10)
    t0 = time.time()
    try:
        r = requests.get(f"{B}/{path}", params={**p, "apiKey": KEY, "returnType": "json"}, headers=H, timeout=120)
        try:
            j = r.json()
            d = j.get("data") if isinstance(j, dict) else j
            f = d[0] if isinstance(d, list) and d else None
            out.append(f"{path}: HTTP {r.status_code} {time.time() - t0:.0f}s n={len(d) if isinstance(d, list) else None} fields={sorted(f) if isinstance(f, dict) else None}")
        except ValueError:
            out.append(f"{path}: HTTP {r.status_code} {time.time() - t0:.0f}s non-JSON len={len(r.text)}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{path}: {type(e).__name__} after {time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
