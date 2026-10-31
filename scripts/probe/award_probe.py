"""Probe 51: 한전 산업분류별 전력사용량 — 시도 코드별 시·군·구 이름, 업종 이름, 최신 달. 이름·건수만(사용량 수치는 찍지 않음)."""
import os
import time
import requests

KEY = os.environ.get("KEPCO_API_KEY", "").strip()
B = "https://bigdata.kepco.co.kr/openapi/v1/powerUsage/industryType.do"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []


def call(metro, year, month):
    time.sleep(8)
    try:
        r = requests.get(B, params={"year": year, "month": month, "metroCd": metro, "cityCd": "", "bizCd": "", "apiKey": KEY, "returnType": "json"},
                         headers=H, timeout=120)
        return (r.json() or {}).get("data") or [], None
    except Exception as e:  # noqa: BLE001
        return None, type(e).__name__


for metro in ("44", "47", "46", "31", "41", "29", "48"):
    d, err = call(metro, "2026", "08")
    if err:
        out.append(f"metro {metro}: {err}")
        continue
    cities = sorted({x.get("city") for x in d})
    bizs = sorted({repr(x.get("biz")) for x in d})
    out.append(f"metro {metro}: n={len(d)} metroName={sorted({x.get('metro') for x in d})} cities={cities}")
    if metro == "44":
        out.append(f"   biz names={bizs}")
        out.append(f"   sample types={ {k: type(v).__name__ for k, v in d[0].items()} }")
for y, m in (("2026", "09"), ("2026", "10"), ("2025", "08")):
    d, err = call("44", y, m)
    out.append(f"44 {y}-{m}: {err or 'n=' + str(len(d))}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
