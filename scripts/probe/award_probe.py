"""격리 탐침 5: 세계은행 응답 날짜 순서·낙찰 칸 해석, 바레인 PDF 글자 추출. 공개 자료 건수·형식만."""
import sys
import time

import requests

sys.path.insert(0, "scripts")
import overseas_award_watch as w

out = []
for term in ("Hyosung", "Korea, Republic of", "LS Cable"):
    r = requests.get(w.WB_API, params={"format": "json", "rows": 50, "notice_type": "Contract Award", "qterm": term, "srt": "noticedate", "order": "desc"},
                     headers=w.UA, timeout=60)
    ns = r.json().get("procnotices") or []
    dates = [w.wb_date(n.get("noticedate")) for n in ns]
    parsed = [w.wb_awarded(n.get("notice_text")) for n in ns]
    hit = [(d, [x["name"][:40] + "/" + x.get("country", "")[:20] for x in p]) for d, p in zip(dates, parsed) if any(w.beat_of(x["name"]) or w.KOREA_RX.search(x.get("country") or "") for x in p)]
    out.append(f"WB {term}: n={len(ns)} first={dates[:3]} last={dates[-2:]} sortedDesc={dates == sorted(dates, reverse=True)} awardedParsed={sum(1 for p in parsed if p)} krHits={len(hit)} sample={hit[:4]}")
    noaw = [n for n, p in zip(ns, parsed) if not p][:1]
    for n in noaw:
        t = w.strip_html(n.get("notice_text"))
        i = t.lower().find("award")
        out.append(f"WB noparse {n.get('id')} {w.wb_date(n.get('noticedate'))} len={len(t)} around={t[max(0, i - 100): i + 400]}")
    time.sleep(1)

r = requests.get(w.BH_LIST, headers={**w.UA, "Accept": "text/html"}, timeout=60)
reps = w.bh_reports(r.text)
out.append(f"BH reports={len(reps)} first={[x['subject'][:40] for x in reps[:3]]}")
pr = requests.get(w.BH_SITE + reps[0]["href"].replace(" ", "%20"), headers={**w.UA, "Accept": "application/pdf"}, timeout=120)
t0 = time.time()
text = w.pdf_text(pr.content)
lines = [w.norm_space(x) for x in text.splitlines() if w.norm_space(x)]
out.append(f"BH pdf bytes={len(pr.content)} secs={time.time()-t0:.0f} chars={len(text)} lines={len(lines)} sample={' // '.join(lines[5:12])[:900]}")
import re
out.append("BH countries=" + str({k: sum(1 for x in lines if re.search(k, x, re.I)) for k in ("korea", "hyundai", "china", "india", "w\\.l\\.l", "transformer", "cable")}))

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
