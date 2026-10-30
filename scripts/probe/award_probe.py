"""Probe 8: 바레인 개찰 목록(F) Content 원문 일부와 상세(입찰사·가격) 원문 — 공개 자료, 저장하지 않음."""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overseas_award_watch as w  # noqa: E402
import requests  # noqa: E402

out = []
S = requests.Session()
S.headers.update(w.UA)
H = {"Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest"}
payload = {"tenderNumber": "", "ministry": "", "category": "0", "tendertype": "0", "openedDate_filter": "", "endDate_filter": "",
           "sortingType": "0", "pageIndex": "1", "sectionName": ""}
d = S.post(w.BH_SITE + "/Templates/TenderBoardWebService.aspx/GetOpenedTenderF", data=json.dumps(payload), headers=H, timeout=60).json()["d"]
c = re.search(r"<Content>(.*?)</Content>", d, re.S)
content = html.unescape(c.group(1)) if c else ""
out.append("CONTENT[0:2600]: " + content[:2600])
hrefs = re.findall(r"""href=['"](/OpenedTenderDetails/[^'"]+)['"]""", content)
out.append("hrefs: " + " | ".join(hrefs[:10]))
if hrefs:
    det = S.get(w.BH_SITE + html.unescape(hrefs[0]).replace(" ", "%20"), timeout=60).text
    body = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", det)
    i = body.find("Bidder") if "Bidder" in body else body.find("Price")
    out.append(f"\nDETAIL len {len(det)} idx {i}: " + re.sub(r"\s+", " ", body[max(0, i - 1500): i + 2500]))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
