"""격리 탐침 43: ktc_watch.collect 실제 조회 — 기준선, 그다음 지난 상태를 일부러 줄여 새 사건·새 진행·빠짐·회의·보도자료 이벤트 확인. 저장 안 함."""
import copy
import datetime as dt
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ktc_watch as k  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
out = []
now = dt.datetime.now(KST)
t0 = time.time()
http = k.Http()
doc, ev, check = k.collect(None, now, http)
out.append(f"1st {time.time() - t0:.0f}s check={check} cases={len(doc['cases'])} listComplete={doc['listComplete']} events={len(ev)} "
           f"meetings={[(m['id'], m.get('meetingOn'), m.get('summary'), len(m.get('agenda') or []), m.get('agendaError')) for m in doc['meetings'][:3]]} news={len(doc['news'])}")
for c in doc["cases"][:30]:
    out.append(f"case {c['id']} {c['no']} | {c['title'][:40]} | {c['product'][:20]} | {c['opened']} | {c['stage']} | {c.get('country')} {c.get('kind')}/{c.get('review')} | "
               f"tl={len(c.get('timeline') or [])} last={(c.get('timeline') or [[None, None]])[-1]} pend={c.get('pending')} res={c.get('result')} beat={c['beat']} err={c.get('detailError')}")
m0 = doc["meetings"][0]
out.append(f"agenda {m0['id']}: " + " | ".join(f"{a['kind']} {a['no']} {a['text'][:70]} beat={a['beat']}" for a in m0.get("agenda") or []))
prev = copy.deepcopy(doc)
gone = prev["cases"].pop(0)  # → 새 사건
tl = next(c for c in prev["cases"] if len(c.get("timeline") or []) >= 2)
tl["timeline"] = tl["timeline"][:-1]  # → 새 진행
prev["cases"].append({**prev["cases"][0], "id": "00000700", "type": "10100001", "no": "가짜 빠짐", "title": "시험용 빠짐 사건"})  # → 빠짐
prev["meetings"] = prev["meetings"][1:]  # → 회의
prev["news"] = prev["news"][1:]  # → 보도자료
ev2 = k.collect(prev, now + dt.timedelta(hours=1), http)[1]
for e in ev2:
    out.append(f"ev {e['ktcKind']} tier={e['tier']} beat={e['beat']} | {e['label']} | {e['text'][:300]} | {e['url']}")
g = http.s.get(k.SITE + "/viewInvest.do", params={"menuId": "11", "masterId": gone["id"], "invstg_type_code": gone["type"]}, headers=k.UA, timeout=40)
out.append(f"GET viewInvest HTTP {g.status_code} has조사번호={'조사번호' in g.text} title={gone['title'][:20] in g.text}")
for i, x in enumerate(out):
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    for j in range(0, min(len(x), 2400), 1200):
        print(f"::notice title=aw-{i:02d}-{j // 1200}::{x[j:j + 1200]}")
