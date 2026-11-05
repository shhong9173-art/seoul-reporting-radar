"""probe 191: 금감원 공개안 제재대상사실 속 최고 경영자 언급(ceoText) 실제 확인 — 공개안(이름 가림). 저장 안 함."""
import re, sys, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public records)"})
t0 = time.time()
ids = ["fss:201900890-2", "fss:202200225-1", "fss:202000209-1", "fss:201800707-4"]
# 최근 목록 1~3쪽에서 임원 조치 있는 건 몇 개 더
for n in range(1, 4):
    r = s.get(f"{osn.FSS_LIST}&sdate=2016-01-01&edate=2026-11-05&pageIndex={n}", timeout=30)
    ids += [x["id"] for x in osn.fss_rows(r.text)]
    time.sleep(0.5)
seen, n_ceo = 0, 0
for i in ids[:28]:
    try:
        d = osn.fss_detail({"id": i}, get=lambda u, **k: s.get(u, timeout=k.get("timeout", 30), headers=k.get("headers")))
    except Exception as e:
        log(i, "예외", type(e).__name__)
        continue
    seen += 1
    if d.get("status") != "ok":
        log(i, d.get("status"))
        continue
    n_ceo += bool(d.get("ceoMentioned"))
    log(f"{i} 임원 {str(d.get('exec'))[:30]} · 위반 {d.get('violation')} · 언급 {d.get('ceoWord')} · 「{(d.get('ceoText') or '')[:130]}」")
    time.sleep(0.6)
log(f"읽음 {seen} · 언급 {n_ceo} · {time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
