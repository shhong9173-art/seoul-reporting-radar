"""Probe 29: edis_watch.collect 실제 API 건식 실행(저장 안 함). 첫 실행(기준선) + 하루 전으로 되돌린 두 번째 실행.
건수·상태·문서 종류(범주)만 출력. 제목·당사자·회사·발췌·토큰은 출력하지 않는다."""
import collections
import datetime as dt
import os
import sys
import time
sys.path.insert(0, "scripts")
import requests
import edis_watch as w

out = []
KST = dt.timezone(dt.timedelta(hours=9))
now = dt.datetime.now(KST)
tok = os.environ.get("EDIS_API_TOKEN", "").strip()
t0 = time.time()
ed, ev, ck = w.collect(None, now, get=requests.get, token=tok)
out.append(f"run1 {time.time() - t0:.0f}s check={ck}")
def summary(ed, ev, tag):
    docs = [x for x in ed["docs"] if x["firstSeen"] == ed["checkedAt"]]
    out.append(f"{tag}: docs new={len(docs)} tiers={dict(collections.Counter(x['tier'] for x in docs))} events={dict(collections.Counter(e['tier'] for e in ev))}")
    out.append(f"   A/B types: " + "; ".join(f"{t}/{k}={n}" for (t, k), n in collections.Counter((x['tier'], x['documentType']) for x in docs if x['tier'] in 'AB').most_common(20)))
    out.append(f"   why: " + "; ".join(f"{k}={n}" for k, n in collections.Counter(x['why'] for x in docs).most_common()))
    out.append(f"   bodies: pages={sum(1 for x in docs if 'pages' in x)} snippets={[len(x.get('snippets') or []) for x in docs if 'pages' in x]} errors={dict(collections.Counter(x.get('bodyError') for x in docs if x.get('bodyError')))}")
    out.append(f"   companies matched (count only): {sum(1 for x in docs if x['companies'])}; watched n={len(ed['watched'])}; lastReceived={ed['lastReceived']}; tokenNote set={bool(ed.get('tokenNote'))}")
summary(ed, ev, "run1")
prev = dict(ed)
prev["lastReceived"] = (dt.datetime.strptime(ed["lastReceived"], "%Y/%m/%d %H:%M:%S") - dt.timedelta(days=1)).strftime("%Y/%m/%d %H:%M:%S")
prev["seen"] = [i for i in ed["seen"] if i not in {x["id"] for x in ed["docs"] if x["officialReceivedDate"] >= prev["lastReceived"]}]
prev["docs"] = [x for x in ed["docs"] if x["officialReceivedDate"] < prev["lastReceived"]]
t0 = time.time()
ed2, ev2, ck2 = w.collect(prev, now + dt.timedelta(minutes=1), get=requests.get, token=tok)
out.append(f"run2 (rewound 1 day) {time.time() - t0:.0f}s check={ck2}")
summary(ed2, ev2, "run2")
out.append("event text lengths: " + str([len(e["text"]) for e in ev2][:20]))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
