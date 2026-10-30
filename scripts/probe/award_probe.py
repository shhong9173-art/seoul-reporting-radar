"""Probe 4: 바레인 개찰 결과 목록 쪽 넘김·상세(입찰사·가격) 형식, 송전·케이블 개찰에서 한국 기업 — 공개 자료, 저장하지 않음."""
import html
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overseas_award_watch as w  # noqa: E402
import requests  # noqa: E402

out = []
S = requests.Session()
S.headers.update(w.UA)
H = {"Content-Type": "application/json; charset=utf-8", "X-Requested-With": "XMLHttpRequest"}
KR = re.compile(r"iljin|ls\s*cable|taihan|hyosung|hyundai|ls\s*electric|doosan|posco|korea|seah", re.I)
GRID = re.compile(r"400\s*kv|220\s*kv|132\s*kv|66\s*kv|cable|transmission|substation|transformer|switchgear|overhead|\bohl\b|gis\b", re.I)

def rows_of(frag):
    out = []
    for m in re.finditer(r"""<div class=['"]rows['"][^>]*>(.*?)(?=<div class=['"]rows['"]|</Content>|$)""", frag, re.S):
        block = m.group(1)
        href = re.search(r"""href=['"]([^'"]+)['"]""", block)
        cols = [html.unescape(re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"""<div class=['"]column['"][^>]*>(.*?)</div>""", block, re.S)]
        out.append({"href": html.unescape(href.group(1)) if href else None, "cols": [re.sub(r"\s+", " ", c) for c in cols]})
    return out

r0 = S.post(w.BH_SITE + "/Templates/TenderBoardWebService.aspx/GetOpenedTender", data="{}", headers=H, timeout=60)
f0 = r0.json().get("d") or ""
out.append(f"GetOpenedTender rows {len(rows_of(f0))} raw rows-tag count {f0.count('rows')} sample {rows_of(f0)[:3]}")
rf = S.post(w.BH_SITE + "/Templates/TenderBoardWebService.aspx/GetOpenedTenderF", data=json.dumps({"tenderNumber": "", "ministry": "", "category": "0", "tendertype": "0", "openedDate_filter": "", "endDate_filter": "", "sortingType": "0", "pageIndex": "2", "sectionName": ""}), headers=H, timeout=60)
out.append(f"F raw HTTP {rf.status_code} len {len(rf.text)}: {rf.text[:500]}")
allrows = rows_of(f0)
for page in range(1, 61):
    payload = {"tenderNumber": "", "ministry": "", "category": "0", "tendertype": "0", "openedDate_filter": "", "endDate_filter": "",
               "sortingType": "0", "pageIndex": str(page), "sectionName": ""}
    try:
        r = S.post(w.BH_SITE + "/Templates/TenderBoardWebService.aspx/GetOpenedTenderF", data=json.dumps(payload), headers=H, timeout=60)
        frag = html.unescape(r.json().get("d") or "")
    except Exception as e:  # noqa: BLE001
        out.append(f"page {page} error {type(e).__name__}: {str(e)[:120]}")
        break
    rs = rows_of(frag)
    if page <= 2:
        out.append(f"page {page} HTTP {r.status_code} rows {len(rs)} sample: {rs[:2]}")
    if not rs:
        out.append(f"page {page}: no rows (stop) raw {frag[:300]!r}")
        break
    allrows += rs
    time.sleep(0.5)
out.append(f"total rows {len(allrows)}; dates first/last: {allrows[0]['cols'][3:4] if allrows else ''} / {allrows[-1]['cols'][3:4] if allrows else ''}")
grid = [x for x in allrows if GRID.search(" ".join(x["cols"]))]
out.append(f"grid-like rows {len(grid)}: " + " || ".join(" | ".join(x["cols"][1:5]) for x in grid[:25]))
for x in grid[:10]:
    if not x["href"]:
        continue
    try:
        d = S.get(w.BH_SITE + x["href"].replace(" ", "%20"), timeout=60).text
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", d))))
        i = max(text.find("Bidder"), text.find("Company"), text.find("Supplier"), 0)
        k = KR.search(text)
        out.append(f"\n-- detail {x['cols'][1][:60]} | {x['cols'][3:5]} len {len(d)} kr {bool(k)}: " + text[max(0, i - 200): i + 1200])
        if k:
            out.append("   KR ctx: " + text[max(0, k.start() - 300): k.start() + 300])
        time.sleep(0.5)
    except Exception as e:  # noqa: BLE001
        out.append(f"detail error {type(e).__name__}")
kr_rows = [x for x in allrows if KR.search(" ".join(x["cols"]))]
out.append(f"\nrows naming Korean firms in list: {len(kr_rows)} {[x['cols'][1:5] for x in kr_rows[:5]]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:500])
