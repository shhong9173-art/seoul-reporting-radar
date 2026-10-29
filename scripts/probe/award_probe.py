"""격리 탐침 4: overseas_award_watch를 실제 원천에 저장 없이 실행. 건수·원천 상태·출입처별 건수만 출력."""
import collections
import datetime as dt
import sys
import time

sys.path.insert(0, "scripts")
import overseas_award_watch as w

t0 = time.time()
now = dt.datetime.now(w.KST)
doc = w.run(now=now, previous=None)
out = [f"status={doc['status']} secs={time.time()-t0:.0f} items={len(doc['items'])} window={doc['windowStart']}"]
for c in doc["checks"]:
    out.append(f"{c['source']}/{c['query']}: {c['status']} ret={c.get('returned')} tot={c.get('total')} m={c.get('matched')} {c.get('error') or c.get('note') or ''}")
by = collections.Counter((x["source"], x.get("company") or "기타한국", x["tier"]) for x in doc["items"])
out.append("by=" + "; ".join(f"{s}/{c}/{t}={n}" for (s, c, t), n in sorted(by.items())))
out.append("dates=" + " ".join(sorted({str(x.get('published'))[:7] for x in doc['items']})))
packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
