"""Probe 49: OSHA 공장 주소 하도급 점검 — 건식 실행(저장 안 함). 회사별 주소 수·하도급 점검 수·종류·시간만(이름·주소 안 찍음)."""
import collections
import datetime as dt
import os
import sys
import time
sys.path.insert(0, "scripts")
import us_osha_watch as w

KST = dt.timezone(dt.timedelta(hours=9))
t0 = time.time()
doc = w.run(now=dt.datetime.now(KST), key=os.environ.get("DOL_API_KEY", "").strip())
c = doc["checks"][0]
ins = doc["inspections"]
site = [x for x in ins if x.get("atSite")]
out = [f"{time.time() - t0:.0f}s status={c['status']} calls={c['calls']} err={c.get('error')} kept={c['kept']} named={len(ins) - len(site)} atSite={len(site)}",
       "sites by company " + str(collections.Counter(v["company"] for v in doc["sites"].values()).most_common()),
       "atSite by company/type " + str(collections.Counter((x["company"], x["type"]) for x in site).most_common(20)),
       f"atSite with violations {sum(1 for x in site if x['violations'])} M/A {sum(1 for x in site if x['type'] in ('M', 'A'))} latest {max([x['opened'] for x in site] or [''])}"]
open("/tmp/probe_out.txt", "w").write("\n".join(out))
