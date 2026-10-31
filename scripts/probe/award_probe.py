"""Probe 27: EDIS 감시 설계용 — 토큰 만료(JWT exp만), 최근 문서 전체 목록의 순서·쪽 크기, 조사 목록(상태별) 크기와 Korea 제목.
토큰 값·문서 내용은 출력하지 않는다. 저장하지 않음."""
import base64
import datetime as dt
import json
import os
import re
import requests

out = []
tok = os.environ.get("EDIS_API_TOKEN", "").strip()
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
try:
    body = tok.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    out.append("jwt claims keys=" + repr(sorted(claims)) + " iat=" + str(dt.datetime.utcfromtimestamp(claims.get("iat", 0))) + " exp=" + str(dt.datetime.utcfromtimestamp(claims.get("exp", 0))))
except Exception as e:  # noqa: BLE001
    out.append(f"jwt decode: {type(e).__name__}")
B = "https://edis.usitc.gov/data"
for q in ("/document?pageNumber=1", "/document?pageNumber=1&pageSize=100", "/document?pageNumber=2"):
    r = requests.get(B + q, headers=UA, timeout=60)
    docs = re.findall(r"<document>(.*?)</document>", r.text, re.S)
    dates = [(re.search(r"<officialReceivedDate>(.*?)</officialReceivedDate>", d) or [None, ""])[1] for d in docs]
    out.append(f"{q}: HTTP {r.status_code} n={len(docs)} first={dates[:2]} last={dates[-2:]}")
for st in ("Preinstitution", "Active"):
    r = requests.get(B + f"/investigation?investigationStatus={st}&pageNumber=1", headers=UA, timeout=60)
    inv = re.findall(r"<investigation>(.*?)</investigation>", r.text, re.S)
    out.append(f"investigation {st}: HTTP {r.status_code} n_page1={len(inv)} total_tag={re.findall(r'<(?:totalCount|total|count)>(\d+)<', r.text)[:2]}")
    for i in inv[:3]:
        out.append("   " + " | ".join((re.search(fr"<{k}>(.*?)</{k}>", i, re.S) or [None, ""])[1][:90] for k in ("investigationNumber", "investigationPhase", "investigationType", "investigationTitle")))
    kor = [i for i in inv if re.search(r"Korea", i)]
    out.append(f"   Korea in titles on page1: {len(kor)}")
r = requests.get(B + "/investigation?investigationStatus=Active&investigationType=Sec%20337&pageNumber=1", headers=UA, timeout=60)
out.append(f"active 337 page1 n={len(re.findall(r'<investigation>', r.text))} HTTP {r.status_code}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
