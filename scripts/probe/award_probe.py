"""probe 189: 공정위 의결서 목록 — 같은 사건번호 여러 줄의 정체(의결번호·사건명·조치 차이). 저장 안 함. 공개 목록."""
import collections, sys, time
import requests

sys.path.insert(0, "scripts")
import kr_signals_watch as ks  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public records)"})
t0 = time.time()


def scan(start, end, pages=None):
    out, p_ = [], 1
    while True:
        r = s.get(ks.FTC_LIST, params={"startRceptDt": start, "endRceptDt": end, "pageIndex": p_}, timeout=40)
        rows, last = ks.parse_ftc_list(r.text)
        for x in rows:
            x["_p"] = p_
        out += rows
        if not rows or (last and p_ >= last) or (pages and p_ >= pages):
            return out
        p_ += 1
        time.sleep(0.4)


for label, (a, b, pages) in {"2016": ("2016-01-01", "2016-12-31", None), "2023": ("2023-01-01", "2023-12-31", None),
                             "전체 1~30쪽": ("2016-01-01", "2026-11-05", 30)}.items():
    rows = scan(a, b, pages)
    by = collections.defaultdict(list)
    for x in rows:
        by[x["csno"]].append(x)
    dups = {k: v for k, v in by.items() if len(v) > 1}
    pair = {(x["csno"], x["blno"]) for x in rows}
    trip = {(x["csno"], x["blno"], x["name"]) for x in rows}
    same_all = sum(1 for v in dups.values() if len({(x["blno"], x["name"], x["action"], x["decidedOn"]) for x in v}) == 1)
    diff_name = sum(1 for v in dups.values() if len({x["name"] for x in v}) > 1)
    diff_bl = sum(1 for v in dups.values() if len({x["blno"] for x in v}) > 1)
    log(f"[{label}] 줄 {len(rows)} · 사건번호 {len(by)} · (사건,의결번호) {len(pair)} · (+사건명) {len(trip)} · 중복 사건 {len(dups)}"
        f" — 모두 같은 줄 {same_all} · 사건명 다름 {diff_name} · 의결번호 다름 {diff_bl}")
    for k, v in list(dups.items())[:6]:
        log(f"  {k}: " + " | ".join(f"p{x['_p']} 의결 {x['blno']} {x['decidedOn']} {x['name'][:34]} / {x['action'][:12]}" for x in v))
    time.sleep(1)
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
