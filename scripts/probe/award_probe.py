"""Probe 95f(영풍: 운영 조회 이름의 응답 출원인 이름 1줄, 띄어 쓴 이름 긴 기간):
같은 기간(2026-08-04~2026-11-02) 한 번씩. 건수와 응답 출원인 이름 한 줄만(공개 정보). KIPRIS 호출 10회 — 장부 밖(진단 여유분)으로 기록."""
import os
import re
from urllib.parse import urlencode

import requests

KEY = os.environ.get("KIPRIS_SERVICE_KEY", "").strip()
BASE = "https://plus.kipris.or.kr/kipo-api/kipi/trademarkInfoSearchService/getAdvancedSearch"
# 운영(trademark_watch.FLAGS)과 같은 플래그 — 그룹마다 1개 이상 true가 필수(probe 95 첫 시도는 권리구분만 넣어 코드 10)
FLAGS = ("application", "registration", "refused", "expiration", "withdrawal", "publication", "cancel", "abandonment",
         "trademark", "serviceMark", "trademarkServiceMark", "businessEmblem", "collectiveMark", "geoOrgMark",
         "internationalMark", "certMark", "geoCertMark",
         "character", "figure", "compositionCharacter", "figureComposition", "sound", "fragrance", "color",
         "dimension", "colorMixed", "hologram", "motion", "visual", "invisible")
NAMES = [("주식회사영풍", "20260804~20261102"), ("주식회사 영풍", "20240101~20261102")]
out = [f"key length {len(KEY)}"]
for n, span in NAMES:
    params = {"applicantName": n, "applicationDate": span, "numOfRows": "3", "pageNo": "1", **{f: "true" for f in FLAGS}, "ServiceKey": KEY}
    try:
        r = requests.get(BASE + "?" + urlencode(params), timeout=40)
        t = r.text
        total = re.search(r"<totalCount>(\d+)</totalCount>", t)
        code = re.search(r"<resultCode>([^<]*)</resultCode>", t)
        msg = re.search(r"<resultMsg>([^<]*)</resultMsg>", t)
        apps = re.findall(r"<applicantName>([^<]*)</applicantName>", t)[:3]
        out.append(f"{n} {span}: HTTP {r.status_code} code {code.group(1) if code else '-'} {(msg.group(1) if msg else '')[:40]} total {total.group(1) if total else '-'} applicants {apps}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{n}: {type(e).__name__}")
text = "\n".join(out)
if KEY:
    text = text.replace(KEY, "<KEY>")
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
