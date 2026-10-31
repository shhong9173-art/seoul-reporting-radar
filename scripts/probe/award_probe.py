"""Probe 28: EDIS 감시 분류 설계 — XML 뼈대(태그만)와 범주 값 분포(문서 종류·조사 종류·단계·보안 등급)만 출력.
제목·당사자·본문·토큰은 출력하지 않는다. 저장하지 않음."""
import collections
import re
import time
import xml.etree.ElementTree as ET
import requests

out = []
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
B = "https://edis.usitc.gov/data"


def local(t):
    return t.split("}")[-1]


def skeleton(el, depth=0, seen=None):
    seen = set() if seen is None else seen
    lines = []
    for ch in el:
        k = (depth, local(ch.tag))
        if k in seen:
            continue
        seen.add(k)
        lines.append("  " * depth + local(ch.tag) + (" [ns]" if "}" in ch.tag else "") + (f" attrs={sorted(ch.attrib)}" if ch.attrib else ""))
        lines += skeleton(ch, depth + 1, seen)
    return lines


docs = []
for p in (1, 2, 3):
    r = requests.get(B + "/document", params={"pageNumber": p, "pageSize": 100}, headers=UA, timeout=60)
    root = ET.fromstring(r.text)
    if p == 1:
        out.append(f"root={root.tag} attrs={sorted(root.attrib)} ctype={r.headers.get('content-type')}")
        out += skeleton(root)[:40]
    for d in root.iter():
        if local(d.tag) == "document":
            docs.append({local(c.tag): (c.text or "").strip() for c in d})
    time.sleep(1)
out.append(f"docs={len(docs)} with id={sum(1 for d in docs if d.get('id'))}")
for k in ("documentType", "investigationType", "investigationPhase", "investigationStatus", "securityLevel"):
    c = collections.Counter(d.get(k, "") for d in docs)
    out.append(f"{k}: " + "; ".join(f"{v or '(빈값)'}={n}" for v, n in c.most_common(60)))
usitc = [d for d in docs if d.get("firmOrganization", "").upper() == "USITC"]
out.append(f"firmOrganization==USITC: {len(usitc)}; their documentType: " + "; ".join(f"{v}={n}" for v, n in collections.Counter(d.get("documentType") for d in usitc).most_common(20)))
out.append("filedBy among USITC docs (categories): " + "; ".join(f"{v}={n}" for v, n in collections.Counter(d.get("filedBy") for d in usitc).most_common(10)))
kor = [d for d in docs if re.search(r"\bKorea\b", d.get("investigationTitle", ""))]
out.append(f"Korea in investigationTitle: {len(kor)}; types " + "; ".join(f"{v}={n}" for v, n in collections.Counter(d.get("documentType") for d in kor).most_common(20)))
out.append(f"Korea phase " + "; ".join(f"{v}={n}" for v, n in collections.Counter(d.get("investigationPhase") for d in kor).most_common(10)))
dates = sorted(d.get("officialReceivedDate", "") for d in docs)
out.append(f"date range {dates[0]} .. {dates[-1]}; empty dates {sum(1 for x in dates if not x)}; sample docDate {docs[0].get('documentDate')} modified {docs[0].get('modifiedDate')}")
esc = sum(1 for d in docs if "&amp;" in d.get("onBehalfOf", "") or "&#" in d.get("onBehalfOf", ""))
out.append(f"onBehalfOf still escaped after 1 parse: {esc}")
r = requests.get(B + "/investigation/337-1494", headers=UA, timeout=60)
root = ET.fromstring(r.text)
out.append(f"investigation root={root.tag}")
out += skeleton(root)[:30]
r = requests.get(B + "/document", params={"investigationNumber": "337-1494", "pageNumber": 1}, headers=UA, timeout=60)
n = sum(1 for d in ET.fromstring(r.text).iter() if local(d.tag) == "document")
out.append(f"337-1494 page1 default size n={n}")
pub = next((d for d in docs if d.get("securityLevel") == "Public"), None)
if pub:
    r = requests.get(B + f"/attachment/{pub['id']}", headers=UA, timeout=60)
    root = ET.fromstring(r.text)
    out.append(f"attachment root={root.tag} HTTP {r.status_code}")
    out += skeleton(root)[:20]
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
