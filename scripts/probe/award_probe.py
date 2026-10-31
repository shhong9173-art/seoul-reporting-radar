"""Probe 22: EDIS 337-1494 최근 문서 12건의 제출 칸 전체(익명 메타데이터). 저장하지 않음."""
import html
import re
import requests

out = []
r = requests.get("https://edis.usitc.gov/data/document?investigationNumber=337-1494&pageNumber=1",
                 headers={"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}, timeout=60)
for d in re.findall(r"<document>(.*?)</document>", r.text, re.S)[:12]:
    f = {k: html.unescape(html.unescape((re.search(fr"<{k}>(.*?)</{k}>", d, re.S) or [None, ""])[1])) for k in
         ("id", "documentType", "documentTitle", "firmOrganization", "filedBy", "onBehalfOf", "documentDate", "officialReceivedDate")}
    out.append(" | ".join(f"{k}={v[:300]}" for k, v in f.items()))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
