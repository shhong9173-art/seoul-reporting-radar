"""격리 탐침 16: 키 없는 새 원천 후보의 접속·형식.
(a) 무공해차 통합누리집(ev.or.kr) 보조금 차종 페이지 (b) USAspending 연방 계약(출입처 미국 법인)
(c) 한수원 전자조달 (d) EU Safety Gate. 저장하지 않음, 공개 자료만."""
import json
import re
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.6"}
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


def page(label, url, method="GET", **kw):
    t0 = time.time()
    try:
        r = requests.request(method, url, headers={**UA, **kw.pop("headers", {})}, timeout=30, **kw)
        body = r.text
        title = (re.search(r"<title[^>]*>([\s\S]*?)</title>", body) or [None, ""])[1].strip()[:60]
        hits = [m.start() for m in re.finditer(r"현대|기아|아이오닉|EV[0-9]|코나|니로", body)][:1]
        snip = text_of(body[max(0, hits[0] - 300): hits[0] + 600])[:300] if hits else ""
        out.append(f"{label}: HTTP {r.status_code} {time.time()-t0:.1f}s len={len(body)} title={title!r} ctype={r.headers.get('content-type','')[:30]} snip={snip!r}")
        return r
    except Exception as e:  # noqa: BLE001
        out.append(f"{label}: EXC {type(e).__name__} {time.time()-t0:.1f}s")


# (a) ev.or.kr
for label, url in [("ev main", "https://ev.or.kr/nportal/main.do"),
                   ("ev subsidy car", "https://ev.or.kr/nportal/buySupprt/initSubsidyPaymentCheckAction.do"),
                   ("ev local price", "https://ev.or.kr/nportal/buySupprt/initPsLocalCarPirceAction.do"),
                   ("ev car list", "https://ev.or.kr/nportal/evcarInfo/initEvcarCarInfoAction.do")]:
    page(label, url)
    time.sleep(1)

# (b) USAspending: contracts to beat companies' US entities, last 12 months
for q in ["HYOSUNG", "HD HYUNDAI ELECTRIC", "LS ELECTRIC", "LS CABLE", "HYUNDAI MOTOR", "KIA", "HANWHA QCELLS", "POSCO", "SEAH", "DOOSAN"]:
    body = {"filters": {"recipient_search_text": [q], "time_period": [{"start_date": "2025-10-01", "end_date": "2026-10-29"}],
                        "award_type_codes": ["A", "B", "C", "D"]},
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Start Date", "Description"],
            "limit": 5, "page": 1, "sort": "Award Amount", "order": "desc"}
    t0 = time.time()
    try:
        r = requests.post("https://api.usaspending.gov/api/v2/search/spending_by_award/", json=body, timeout=40)
        d = r.json()
        rows = d.get("results") or []
        out.append(f"usasp {q}: HTTP {r.status_code} {time.time()-t0:.1f}s n={len(rows)} " +
                   " ; ".join(f"{x.get('Recipient Name')}|{x.get('Awarding Agency')}|{x.get('Award Amount')}|{x.get('Start Date')}|{str(x.get('Description'))[:50]}" for x in rows[:3]))
    except Exception as e:  # noqa: BLE001
        out.append(f"usasp {q}: EXC {type(e).__name__}")
    time.sleep(1)

# (c) 한수원 전자조달
page("khnp", "https://cyber.khnp.co.kr/")
page("khnp bid", "https://www.khnp.co.kr/main/contents.do?key=1494")
# (d) EU Safety Gate (motor vehicles)
page("safety gate", "https://ec.europa.eu/safety-gate-alerts/public/api/notification/carousel/?language=en")

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
