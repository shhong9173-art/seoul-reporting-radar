"""Probe 33: 국가법령정보 DRF 오류 응답의 result·msg 문구만(호출 1번). OC 값은 가린다."""
import os
import xml.etree.ElementTree as ET
import requests

OC = os.environ.get("LAW_OC", "").strip()
r = requests.get("https://www.law.go.kr/DRF/lawSearch.do", params={"OC": OC, "target": "law", "type": "XML", "query": "전기사업법"},
                 headers={"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}, timeout=40)
root = ET.fromstring(r.content)
msg = f"HTTP {r.status_code} result={root.findtext('result')!r} msg={root.findtext('msg')!r}"
open("/tmp/probe_out.txt", "w").write(msg.replace(OC, "<OC>") if OC else msg)
