"""격리 탐침 7: kr_insolvency_watch를 실제 법원 공고·공장등록에 저장 없이 실행. 건수·등급·업종 분포만(회사 이름 출력 안 함)."""
import collections
import datetime as dt
import os
import sys
import time

sys.path.insert(0, "scripts")
import kr_insolvency_watch as k

t0 = time.time()
now = dt.datetime.now(k.KST)
key = (os.environ.get("CUSTOMS_API_KEY") or "").strip()
doc = k.run(key, now=now, previous=None, deadline=time.monotonic() + k.DEADLINE_SECONDS)
out = [f"status={doc['status']} secs={time.time()-t0:.0f} window={doc['windowStart']} counts={doc['counts']} events={len(doc['events'])}"]
bad = [c for c in doc["checks"] if c["status"] != "ok"]
out.append(f"checks ok={len(doc['checks'])-len(bad)}/{len(doc['checks'])} notOk={[(c['source'], c['status'], c.get('error') or c.get('pending')) for c in bad]}")
out.append("pages=" + str(collections.Counter(c.get("pages") for c in doc["checks"] if "pages" in c)))
tiers = collections.Counter((e["source"][:6], e["kind"], e["tier"], e.get("match")) for e in doc["events"])
out.append("tiers=" + "; ".join(f"{a}/{b}/{c}/{d}={n}" for (a, b, c, d), n in sorted(tiers.items())))
labels = collections.Counter((e.get("industry") or {}).get("label") for e in doc["events"])
out.append(f"labels={dict(labels)}")
cache = collections.Counter(v.get("match") for v in doc["industryCache"].values())
out.append(f"cache={dict(cache)}")
packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
