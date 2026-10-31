"""Probe 35: 승인 뒤 DRF 재호출 — 우리 OC로 법령·행정규칙·해석례 목록 각 1번(+질의 없는 행정규칙 1번). result·msg·건수만. OC 값은 가린다."""
import os
import time
import xml.etree.ElementTree as ET
import requests

OC = os.environ.get("LAW_OC", "").strip()
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = [f"OC len={len(OC)} has-space={' ' in OC} has-@={'@' in OC}"]
for label, params in (("law q", {"target": "law", "query": "전기사업법"}),
                      ("admrul q", {"target": "admrul", "query": "자동차"}),
                      ("admrul no-q", {"target": "admrul", "display": 5}),
                      ("expc q", {"target": "expc", "query": "전기"})):
    try:
        r = requests.get("https://www.law.go.kr/DRF/lawSearch.do", params={"OC": OC, "type": "XML", **params}, headers=H, timeout=40)
        root = ET.fromstring(r.content)
        out.append(f"{label}: HTTP {r.status_code} root={root.tag} totalCnt={root.findtext('totalCnt')} result={root.findtext('result')!r} msg={root.findtext('msg')!r}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: {type(e).__name__} {str(e)[:100]}")
    time.sleep(1)
text = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(text.replace(OC, "<OC>") if OC else text)
