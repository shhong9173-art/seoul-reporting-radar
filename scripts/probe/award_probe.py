"""Probe 9: 바레인 개찰 결과에서 송전·케이블 입찰의 한국 기업 응찰(일진전기 낙찰 보도 10-20 확인용) — 공개 자료, 저장하지 않음."""
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
KR = re.compile(r"iljin|ls\s*cable|taihan|hyosung|hd\s*hyundai|hyundai\s*electric|ls\s*electric|doosan|posco|korea|seah", re.I)
GRID = re.compile(r"\d+\s*kv|cable|transmission|substation|transformer|switchgear|overhead|\bohl\b|\bgis\b|grid|power", re.I)
ROW = re.compile(r"""<div data-ref=['"](\d+)['"] class=['"]rows['"]>(.*?)(?=<div data-ref=|$)""", re.S)
rows = []
for page in range(1, 151):
    payload = {"tenderNumber": "", "ministry": "", "category": "0", "tendertype": "0", "openedDate_filter": "", "endDate_filter": "",
               "sortingType": "0", "pageIndex": str(page), "sectionName": ""}
    try:
        d = S.post(w.BH_SITE + "/Templates/TenderBoardWebService.aspx/GetOpenedTenderF", data=json.dumps(payload), headers=H, timeout=60).json()["d"]
    except Exception as e:  # noqa: BLE001
        out.append(f"page {page} error {type(e).__name__}")
        break
    c = re.search(r"<Content>(.*?)</Content>", d, re.S)
    content = html.unescape(c.group(1)) if c else ""
    got = 0
    for ref, block in ROW.findall(content):
        cols = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip() for x in re.findall(r"<div class='column'[^>]*>(.*?)</div>", block, re.S)]
        href = re.search(r"href='([^']+)'", block)
        rows.append({"ref": ref, "cols": cols, "href": html.unescape(href.group(1)) if href else None})
        got += 1
    if not got:
        out.append(f"page {page}: 0 rows")
        break
    time.sleep(0.4)
out.append(f"rows {len(rows)} · newest {rows[0]['cols'][3] if rows else ''} · oldest {rows[-1]['cols'][3] if rows else ''} · sample cols {rows[0]['cols'] if rows else ''}")
grid = [r for r in rows if GRID.search(r["cols"][1] if len(r["cols"]) > 1 else "")]
out.append(f"grid rows {len(grid)}: " + " || ".join(f"{r['cols'][1][:70]} ({r['cols'][3]}, {r['cols'][4][:30]}, bids {r['cols'][5]})" for r in grid[:40]))
hits = []
for r in grid[:45]:
    try:
        det = S.get(w.BH_SITE + r["href"].replace(" ", "%20"), timeout=60).text
    except Exception as e:  # noqa: BLE001
        out.append(f"detail error {type(e).__name__}")
        continue
    bidders = re.findall(r"data-label='Bidder Name'>(.*?)</div><div class='column bidvalue'[^>]*><span>(.*?)</span>.*?data-label='Status'>(.*?)</div>", det, re.S)
    kr = [b for b in bidders if KR.search(b[0])]
    if kr:
        hits.append((r["cols"][1][:90], r["cols"][3], r["cols"][4][:40], len(bidders), [(html.unescape(n).strip(), v, s) for n, v, s in bidders][:12]))
    time.sleep(0.6)
out.append(f"\nKorean bidders in {len(hits)} grid tenders:")
for h in hits:
    out.append(f"- {h[0]} | opened {h[1]} | {h[2]} | bids {h[3]} | {h[4]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
