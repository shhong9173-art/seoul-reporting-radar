"""Probe 36: 없는 OC(무작위)와 우리 OC의 응답 비교 — 우리 OC가 법제처에 '없는 값'으로 보이는지. 각 1번. OC 값은 가린다."""
import os
import time
import xml.etree.ElementTree as ET
import requests

OC = os.environ.get("LAW_OC", "").strip()
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = [f"OC len={len(OC)} lower==orig={OC.lower() == OC} digits={sum(c.isdigit() for c in OC)}"]
for label, oc in (("random-nonexistent", "qzx7k2w9vj"), ("ours", OC), ("ours-lower", OC.lower())):
    r = requests.get("https://www.law.go.kr/DRF/lawSearch.do", params={"OC": oc, "target": "law", "type": "XML", "query": "전기사업법"}, headers=H, timeout=40)
    root = ET.fromstring(r.content)
    out.append(f"{label}: result={root.findtext('result')!r} msg={root.findtext('msg')!r} totalCnt={root.findtext('totalCnt')}")
    time.sleep(1)
text = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(text.replace(OC, "<OC>") if OC else text)
