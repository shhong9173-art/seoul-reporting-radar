"""격리 탐침 10: kr_energy_watch를 실제 원천에 저장 없이 실행. 공개 회의 결과의 사업명·안건명·건수만."""
import datetime as dt
import sys
import time

sys.path.insert(0, "scripts")
import kr_energy_watch as k

t0 = time.time()
doc = k.run(now=dt.datetime.now(k.KST), previous=None)
out = [f"status={doc['status']} secs={time.time()-t0:.0f} items={len(doc['items'])} checks={doc['checks']}"]
for x in doc["items"][:60]:
    out.append(f"{x['tier']} {x['source'][:6]} {x['kind']} {x.get('meeting','')[:22]} held={x.get('held')} grp={x.get('company')} res={x.get('result')} :: {x['title'][:110]}")
packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
