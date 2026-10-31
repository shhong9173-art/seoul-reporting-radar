"""Probe 23: EDIS 337-1494 재검토 청원(898408·897042) onBehalfOf 전체와 한화 이름 여부. 저장하지 않음."""
import html
import re
import requests

out = []
for doc in ("898408", "897042", "899140", "897778"):
    r = requests.get(f"https://edis.usitc.gov/data/document/{doc}",
                     headers={"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}, timeout=60)
    t = html.unescape(html.unescape(r.text))
    who = (re.search(r"<onBehalfOf>(.*?)</onBehalfOf>", t, re.S) or [None, ""])[1]
    out.append(f"{doc}: HTTP {r.status_code} onBehalfOf({len(who)}자)={who}")
    out.append(f"   hanwha={bool(re.search(r'hanwha|q ?cells', who, re.I))} · attachments={re.findall(r'<attachmentListUri>(.*?)</attachmentListUri>', t)[:1]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
