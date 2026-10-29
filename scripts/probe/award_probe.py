"""격리 탐침 44: ktc_watch.collect 실제 조회(압축 출력) — 쪽별 ID·진행단계, 사건 요약, 이벤트. 저장 안 함."""
import copy
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ktc_watch as k  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
out = []
http = k.Http()
pages = []
for p in range(1, 9):
    st, body = http.post(k.PROGRESS[0], {"menuId": "11", "pageIndex": str(p)})
    rows = k.parse_cases(body)
    pages.append(f"p{p}:{len(rows)}[{rows[0]['id'] if rows else '-'}..{rows[-1]['id'] if rows else '-'}]{sorted(set(r['stage'] for r in rows))}")
    time.sleep(0.7)
out.append("pages " + " ".join(pages))
now = dt.datetime.now(KST)
doc, ev, check = k.collect(None, now, http)
out.append(f"check={check} cases={len(doc['cases'])} done={doc['listComplete']} news={[n['title'][:30] for n in doc['news'][:3]]}")
out.append("cases " + " ‖ ".join(f"{c['id'][-3:]}|{c['no'][-12:]}|{c['opened']}|{c['stage']}|{(c.get('kind') or '')[:4]}|tl{len(c.get('timeline') or [])}|{'B' if c['beat'] else '-'}|{c['product'][:10]}" for c in doc["cases"]))
m0 = doc["meetings"][0]
out.append(f"agenda {m0['id']} {m0.get('meetingOn')}: " + " | ".join(f"{a['kind']} {a['text'][:60]} {'B' if a['beat'] else '-'}" for a in m0.get("agenda") or []))
prev = copy.deepcopy(doc)
gone = prev["cases"].pop(0)
tl = next(c for c in prev["cases"] if len(c.get("timeline") or []) >= 2)
tl["timeline"] = tl["timeline"][:-1]
prev["cases"].append({**prev["cases"][0], "id": "00000700", "type": "10100001", "no": "가짜 빠짐", "title": "시험용 빠짐 사건"})
prev["meetings"] = prev["meetings"][1:]
prev["news"] = prev["news"][1:]
ev2 = k.collect(prev, now + dt.timedelta(hours=1), http)[1]
out.append("events " + " ‖ ".join(f"{e['ktcKind']} {e['tier']} | {e['label']} | {e['text'][:220]}" for e in ev2))
g = http.s.get(k.SITE + "/viewInvest.do", params={"menuId": "11", "masterId": gone["id"], "invstg_type_code": gone["type"]}, headers=k.UA, timeout=40)
out.append(f"GET viewInvest HTTP {g.status_code} has={'조사번호' in g.text} title={gone['title'][:15] in g.text}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
