"""Probe 41: law_rules_watch.collect 실제 건식 실행(기준선, 저장 안 함) + 사람용 law.go.kr 주소 확인. 건수·등급·부처 분포·주소 상태만."""
import collections
import datetime as dt
import os
import re
import sys
import time
sys.path.insert(0, "scripts")
import requests
import law_rules_watch as w
from kr_official_watch import TEAMS, BEAT_MINISTRIES, teams_of

KEY = os.environ.get("G2B_API_KEY", "").strip()
KST = dt.timezone(dt.timedelta(hours=9))
now = dt.datetime.now(KST)
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
t0 = time.time()
sec, check = w.collect(None, now, KEY, get=lambda u, **k: requests.get(u, headers=H, **k), teams_of=teams_of, ministries=BEAT_MINISTRIES)
out.append(f"{time.time() - t0:.0f}s check={ {k: v for k, v in check.items() if k != 'error'} } err={check.get('error')}")
items = sec["items"]
out.append(f"kept {len(items)} by kind/tier {dict(collections.Counter((x['kind'], x['tier']) for x in items))}")
for days in (7, 14, 30):
    cut = (now.date() - dt.timedelta(days=days)).isoformat()
    sub = [x for x in items if x["date"] >= cut]
    out.append(f"date within {days}d: {len(sub)} {dict(collections.Counter((x['kind'], x['tier']) for x in sub))}")
out.append("org (B) " + str(collections.Counter(x["org"] for x in items if x["tier"] == "B").most_common(10)))
out.append("type " + str(collections.Counter((x["kind"], x["type"]) for x in items).most_common(10)))
out.append("change " + str(collections.Counter(x["change"] for x in items).most_common(8)))
out.append("teams " + str(collections.Counter(t for x in items for t in x["teams"]).most_common()))
out.append(f"seen {len(sec['seen'])}")
cands = []
for x in items:
    if x["kind"] == "행정규칙" and len([c for c in cands if c[0] == "admrul"]) < 2:
        cands += [("admrul", x["url"], x["title"]), ("admrul-seq", f"https://www.law.go.kr/admRulLsInfoP.do?admRulSeq={x['id'].split(':')[1]}", x["title"])]
    if x["kind"] == "법령" and not any(c[0] == "law" for c in cands):
        cands.append(("law", x["url"], x["title"]))
    if x["kind"] == "법령해석례" and not any(c[0] == "expc" for c in cands):
        cands += [("expc", x["url"], x["title"]), ("expc-noLSW", x["url"].replace("/LSW/", "/"), x["title"])]
for label, url, title in cands:
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        key = re.sub(r"\s+", "", title)[:12]
        out.append(f"url {label}: HTTP {r.status_code} len={len(r.text)} title-in-page={key in re.sub(r'\s+', '', r.text)} final-path={re.sub(r'[0-9]', '9', r.url.split('law.go.kr')[-1])[:60]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"url {label}: {type(e).__name__}")
    time.sleep(1)
open("/tmp/probe_out.txt", "w").write("\n".join(out))
