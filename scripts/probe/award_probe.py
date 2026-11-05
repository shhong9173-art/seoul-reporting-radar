"""probe 190: 공정위 지에스리테일 — 목록 검색 전체 줄과 원문 요약 실패 원인(공개 의결서). 저장 안 함."""
import sys, time, traceback
import datetime as dt
import requests

sys.path.insert(0, "scripts")
import kr_signals_watch as ks  # noqa: E402
import official_sanctions as osn  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public records)"})
t0 = time.time()
now = dt.datetime(2026, 11, 5, 23, 0)
for kw in ("지에스리테일", "GS리테일"):
    rows_all = []
    for p_ in range(1, 8):
        r = s.get(ks.FTC_LIST, params={"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": p_, "searchKrwd": kw}, timeout=40)
        rows, last = ks.parse_ftc_list(r.text)
        rows_all += [(p_, x) for x in rows]
        if not rows or (last and p_ >= last):
            break
        time.sleep(0.5)
    log(f"[{kw}] 줄 {len(rows_all)} · 마지막 쪽 {last}")
    for p_, x in rows_all:
        log(f"  p{p_} {x['csno']} {x['blno']} {x['decidedOn']} 문서 {'O' if x.get('doc') else 'X'} · {x['action'][:24]} · {x['name'][:50]} · 피심인 {osn.ftc_respondents(x['name'])}")
    time.sleep(1)
for cid, org in (("ftc:2019제하2424", "지에스리테일"), ("ftc:2020서경1005", "지에스리테일")):
    t1 = time.time()
    try:
        d = osn.ftc_case_detail({"id": cid, "org": org}, get=s.get, now=now, pause=time.sleep)
        log(f"[원문 {cid}] {time.time() - t1:.0f}s status {d.get('status')} err {d.get('error')} 금액 {d.get('amount')} 대표 {d.get('ceos')} 제목 {str(d.get('title'))[:40]} note {d.get('note')}")
    except Exception:
        log(f"[원문 {cid}] 예외 {traceback.format_exc()[-300:]}")
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
