"""Probe 44: OSHA 403 원인 — 단순 질의·like 하나·OR 3개·OR 31개 각 1번(15초 간격). 상태·응답 머리(키 가림)만."""
import json
import os
import time
import requests

KEY = os.environ.get("DOL_API_KEY", "").strip()
B = "https://apiprod.dol.gov/v4/get/OSHA/inspection/json"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
LIKES = ["%HYUNDAI MOTOR%", "%HMGMA%", "%HL-GA%", "%HLGA%", "%KIA %", "%MOBIS%", "%HYUNDAI WIA%", "%WIA %", "%MANDO%", "%KLEMOVE%", "%HANKOOK%",
         "%NEXEN%", "%KUMHO%", "%POSCO%", "%HYUNDAI STEEL%", "%SEAH%", "%DONGKUK%", "%KOREA ZINC%", "%HYUNDAI POWER%", "%HD HYUNDAI%", "%LS ELECTRIC%",
         "%LS CABLE%", "%GREENLINK%", "%SUPERIOR ESSEX%", "%TAIHAN%", "%DOOSAN%", "%HANWHA%", "%QCELLS%", "%MISSION SOLAR%", "%OCI ENERGY%", "%HYOSUNG%"]
cases = [("plain", {"limit": 1}),
         ("like1", {"limit": 5, "filter_object": json.dumps({"field": "estab_name", "operator": "like", "value": "%HANKOOK%"})}),
         ("or3+fields", {"limit": 50, "fields": "activity_nr,estab_name,open_date", "filter_object": json.dumps({"or": [{"field": "estab_name", "operator": "like", "value": p} for p in LIKES[:3]]})}),
         ("or31", {"limit": 50, "filter_object": json.dumps({"or": [{"field": "estab_name", "operator": "like", "value": p} for p in LIKES]})})]
for label, p in cases:
    time.sleep(15)
    r = requests.get(B, params={**p, "X-API-KEY": KEY}, headers=H, timeout=90)
    try:
        n = len((r.json() or {}).get("data") or [])
    except ValueError:
        n = None
    out.append(f"{label}: HTTP {r.status_code} n={n} url-len={len(r.url)} head={r.text[:160].replace(KEY, '<KEY>')!r} retry-after={r.headers.get('retry-after')} rl={[(k, v) for k, v in r.headers.items() if 'limit' in k.lower()]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
