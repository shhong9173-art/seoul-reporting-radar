"""격리 탐침 6: 대법원 회생·파산 공고 목록(ssgo)의 해외 러너 접속 재시도·다른 법원 호스트, 바레인 7월 보고서 글자 추출. 건수·상태만."""
import json
import socket
import sys
import time

import requests

sys.path.insert(0, "scripts")
out = []


def note(m):
    out.append(m)


for host in ("ssgo.scourt.go.kr", "www.scourt.go.kr", "ecfs.scourt.go.kr", "slb.scourt.go.kr", "safind.scourt.go.kr"):
    try:
        ips = sorted({a[4][0] for a in socket.getaddrinfo(host, 443)})
    except Exception as e:  # noqa: BLE001
        ips = [type(e).__name__]
    t0 = time.time()
    try:
        r = requests.get(f"https://{host}/", timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        note(f"{host} ips={ips} HTTP {r.status_code} {time.time()-t0:.1f}s")
    except Exception as e:  # noqa: BLE001
        note(f"{host} ips={ips} {type(e).__name__} {time.time()-t0:.1f}s")

body = {"dma_search": {"taskDvs": "4", "srchType": "pstgBgng", "cortCd": "000221", "pstgDvs": "999", "csYr": "", "csDvsCd": "", "csSrno": "", "debtrNm": "", "jdbnCd": ""},
        "dma_pageInfo": {"pageNo": 1, "pageSize": 10, "totalYn": "Y"}}
for attempt in range(3):
    t0 = time.time()
    try:
        r = requests.post("https://ssgo.scourt.go.kr/ssgo/ssgo930/selectRhblBnkpPbancLst.on", data=json.dumps(body), timeout=45,
                          headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json; charset=UTF-8", "Accept": "application/json"})
        d = r.json().get("data") or {}
        note(f"ssgo list try{attempt} HTTP {r.status_code} rows={len(d.get('dlt_pbancLst') or [])} total={(d.get('dma_pageInfo') or {}).get('totalCnt')} {time.time()-t0:.1f}s")
        break
    except Exception as e:  # noqa: BLE001
        note(f"ssgo list try{attempt} {type(e).__name__} {time.time()-t0:.1f}s")
        time.sleep(5)

try:
    r = requests.get("https://www.scourt.go.kr/portal/notice/mainfo/MaNoticeList.work?business=01", timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    note(f"M&A list HTTP {r.status_code} bytes={len(r.content)} rows={r.text.count('MaNoticeView.work')}")
except Exception as e:  # noqa: BLE001
    note(f"M&A list {type(e).__name__}")

import overseas_award_watch as w
r = requests.get(w.BH_LIST, headers={**w.UA, "Accept": "text/html"}, timeout=60)
reps = w.bh_reports(r.text)
for rep in reps[1:3]:
    pr = requests.get(w.BH_SITE + rep["href"].replace(" ", "%20"), headers={**w.UA, "Accept": "application/pdf"}, timeout=120)
    text = w.pdf_text(pr.content)
    lines = [w.norm_space(x) for x in text.splitlines() if w.norm_space(x)]
    note(f"BH {rep['subject'][:40]} bytes={len(pr.content)} chars={len(text)} lines={len(lines)} sample={' // '.join(lines[8:14])[:500]}")

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
