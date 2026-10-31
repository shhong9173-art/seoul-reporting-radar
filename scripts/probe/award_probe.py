"""Probe 53: NHTSA 제조사 통신(TSB) 평면 파일 — 필드 설명 파일과 압축 파일 주소 후보 HEAD(크기·날짜만)."""
import time
import requests

H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
r = requests.get("https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS.txt", headers=H, timeout=60)
out.append(f"TSBS.txt HTTP {r.status_code} len={len(r.text)}")
out.append(r.text[:3000])
for name in ("FLAT_TSBS.zip", "TSBS_RECEIVED_2025-2026.zip", "TSBS_RECEIVED_2020-2024.zip", "FLAT_TSBS_2025-2026.zip", "MFR_COMMS_RECEIVED_2025-2026.zip"):
    time.sleep(2)
    try:
        h = requests.head(f"https://static.nhtsa.gov/odi/ffdd/tsbs/{name}", headers=H, timeout=60, allow_redirects=True)
        out.append(f"{name}: HTTP {h.status_code} size={h.headers.get('content-length')} modified={h.headers.get('last-modified')}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{name}: {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
