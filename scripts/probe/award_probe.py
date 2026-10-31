"""Probe 46: us_osha_watch.run 실제 건식 실행(기준선, 저장 안 함) + 점검 상세 주소가 열리는지(이름 출력 안 함). 건수·시간·상태만."""
import collections
import datetime as dt
import os
import sys
import time
sys.path.insert(0, "scripts")
import requests
import us_osha_watch as w

KST = dt.timezone(dt.timedelta(hours=9))
t0 = time.time()
doc = w.run(now=dt.datetime.now(KST), key=os.environ.get("DOL_API_KEY", "").strip())
c = doc["checks"][0]
out = [f"{time.time() - t0:.0f}s check status={c['status']} returned={c['returned']} kept={c['kept']} calls={c['calls']} err={c.get('error')}"]
ins = doc["inspections"]
out.append("by company " + str(collections.Counter(x["company"] for x in ins).most_common()))
out.append("types " + str(collections.Counter(x["type"] for x in ins)))
out.append(f"with violations {sum(1 for x in ins if x['violations'])} penalty-sum {sum(x['penaltyInitial'] for x in ins)} accidents {sum(len(x['accidents']) for x in ins)} fatal {sum(1 for x in ins for a in x['accidents'] if a['fatality'])}")
out.append(f"dropped names {len(doc['dropped'])} events {len(doc['events'])}")
if ins:
    r = requests.get(ins[-1]["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
    out.append(f"detail url: HTTP {r.status_code} len={len(r.text)} has-nr={ins[-1]['id'] in r.text} has-'Inspection'={'Inspection' in r.text}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
