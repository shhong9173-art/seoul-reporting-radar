"""Probe 34: DRF '필수 입력값' 오류 원인 가르기 — 우리 OC(https·http) vs 가이드 예시 OC(test) 각 1번. OC 값은 가린다."""
import os
import time
import xml.etree.ElementTree as ET
import requests

OC = os.environ.get("LAW_OC", "").strip()
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for label, base, oc in (("ours-https", "https://www.law.go.kr", OC), ("ours-http", "http://www.law.go.kr", OC), ("sample-test", "https://www.law.go.kr", "test")):
    try:
        r = requests.get(base + "/DRF/lawSearch.do", params={"OC": oc, "target": "law", "type": "XML", "query": "전기사업법"}, headers=H, timeout=40)
        root = ET.fromstring(r.content)
        out.append(f"{label}: HTTP {r.status_code} final={r.url.split('?')[0]} root={root.tag} totalCnt={root.findtext('totalCnt')} result={root.findtext('result')!r} msg={root.findtext('msg')!r}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: {type(e).__name__} {str(e)[:100]}")
    time.sleep(1)
text = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(text.replace(OC, "<OC>") if OC else text)
