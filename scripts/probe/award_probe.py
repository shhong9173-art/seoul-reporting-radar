"""probe 188: 공정위 의결서 목록 건수 — 접수연도 창별 총수(쪽 수·마지막 쪽 줄 수)와 한 창 전체의 사건번호 중복. 저장 안 함. 공개 목록."""
import re, sys, time
import requests

sys.path.insert(0, "scripts")
import kr_signals_watch as ks  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public records)"})
t0 = time.time()


def page(start, end, n):
    r = s.get(ks.FTC_LIST, params={"startRceptDt": start, "endRceptDt": end, "pageIndex": n}, timeout=40)
    rows, last = ks.parse_ftc_list(r.text)
    total = re.search(r"총\s*([\d,]+)\s*건|전체\s*([\d,]+)", r.text)
    return rows, last, (total.group(1) or total.group(2)) if total else None


tot = 0
for y in range(2014, 2027):
    try:
        rows, last, shown = page(f"{y}-01-01", f"{y}-12-31", 1)
        n_last = len(page(f"{y}-01-01", f"{y}-12-31", last)[0]) if last and last > 1 else len(rows)
        est = (last - 1) * 10 + n_last if last else len(rows)
        tot += est if y >= 2016 else 0
        dec = [x["decidedOn"] for x in rows]
        log(f" 접수 {y}: 쪽 {last} 마지막 쪽 {n_last}줄 → 약 {est}건 · 표시 총수 {shown} · 첫 쪽 의결일 {min(dec) if dec else None}~{max(dec) if dec else None}")
    except Exception as e:
        log(f" {y} error {type(e).__name__}")
    time.sleep(0.4)
log(f" 2016~ 접수 창 합계 약 {tot}건")
# 전체(2016-01-01~) 목록 정렬 기준·중복: 1~40쪽 사건번호
seen, dup, n = {}, 0, 0
for p_ in range(1, 41):
    rows, last, _ = page("2016-01-01", "2026-11-05", p_)
    for x in rows:
        n += 1
        if x["csno"] in seen:
            dup += 1
        seen[x["csno"]] = p_
    time.sleep(0.3)
log(f" 전체 목록 1~40쪽: 줄 {n} · 고유 사건번호 {len(seen)} · 중복 {dup} · last {last}")
# 접수일 창 2016 전체 스캔
rows_all, p_ = [], 1
while True:
    rows, last, _ = page("2016-01-01", "2016-12-31", p_)
    rows_all += rows
    if not rows or (last and p_ >= last):
        break
    p_ += 1
    time.sleep(0.3)
ids = [x["csno"] for x in rows_all]
log(f" 접수 2016 창 전체: 줄 {len(ids)} · 고유 {len(set(ids))} · 빈 사건번호 {sum(1 for i in ids if not i)}")
dec = sorted(x["decidedOn"] for x in rows_all if x.get("decidedOn"))
log(f"   의결일 범위 {dec[0] if dec else None}~{dec[-1] if dec else None}")
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
