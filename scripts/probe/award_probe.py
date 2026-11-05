"""probe 183: (a) 공정위 의결서 목록(case.ftc.go.kr ltfr.do) 검색 폼 이름·쪽 크기·과거 범위·회사 이름 검색, (b) 개인정보위 결과의 공표 HWP·HWPX 첨부 글자.
저장 안 함. 공개 공표 대상(법인·기관)과 사건명만. 사람 이름처럼 보이는 것은 가린다."""
import re, sys, time
import requests

sys.path.insert(0, "scripts")
import official_sanctions as osn  # noqa: E402
import kr_signals_watch as ks  # noqa: E402

OUT = []
MASK = re.compile(r"(?<![가-힣])[가-힣]{2,3}(?=\s*(?:씨|님))")


def log(*a):
    OUT.append(MASK.sub("○○", " ".join(str(x) for x in a)))


UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
t0 = time.time()
s = requests.Session()
s.headers.update(UA)
log("# 공정위 ltfr.do")
try:
    r = s.get(ks.FTC_LIST, timeout=30)
    h = r.text
    log(" HTTP", r.status_code, len(h))
    names = sorted(set(re.findall(r'<(?:input|select)[^>]+name="([^"]+)"', h)))
    log(" form names:", names[:60])
    rows, last = ks.parse_ftc_list(h)
    log(" default rows", len(rows), "last", last, "first", (rows[0]["decidedOn"], rows[0]["name"][:60], rows[0]["action"]) if rows else None)
    for params in ({"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": 1},
                   {"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": 1, "pageUnit": 100},
                   {"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": 1, "searchKrwd": "우리은행"},
                   {"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": 1, "searchWrd": "우리은행"},
                   {"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": 1, "csname": "우리은행"},
                   {"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": 1, "srchCsNm": "우리은행"}):
        rr = s.get(ks.FTC_LIST, params=params, timeout=40)
        rows, last = ks.parse_ftc_list(rr.text)
        extra = {k: v for k, v in params.items() if k not in ("startRceptDt", "endRceptDt", "pageIndex")}
        log(f"  {extra} HTTP {rr.status_code} rows {len(rows)} last {last} first {(rows[0]['decidedOn'], rows[0]['name'][:50], rows[0]['action']) if rows else None}"
            f" any우리 {sum('우리' in x['name'] for x in rows)}")
except Exception as e:
    log(" ftc error", type(e).__name__, str(e)[:120])

log("\n# 개인정보위 HWP·HWPX")
try:
    ids = []
    for n in range(1, 5):
        r = s.get(f"{osn.PIPC_LIST}&pageIndex={n}", timeout=30)
        got = [x for x in dict.fromkeys(re.findall(r"selectBoardArticle\.do[^\"']*?nttId=(\d+)", r.text)) if x not in ids]
        if not got:
            break
        ids += got
    shown = 0
    for ntt in ids:
        v = s.get(osn.PIPC_VIEW + ntt, timeout=30)
        for fid, sn in re.findall(r"fn_egov_downFile\w*\(\s*'([^']+)'\s*,\s*'([^']+)'", v.text)[:3]:
            f = s.get(osn.PIPC_FILE.format(fid, sn), headers={"Referer": osn.PIPC_VIEW + ntt}, timeout=40)
            if f.content[:4] in (b"\xd0\xcf\x11\xe0", b"PK\x03\x04"):
                txt = osn.attachment_text(f.content)
                log(f"\n {ntt} magic {f.content[:4]!r} chars {len(txt or '')} rows {len(osn.pipc_rows(txt or ''))}")
                log("  head:", re.sub(r"\s+", " ", txt or "")[:900])
                shown += 1
    log(" shown", shown)
except Exception as e:
    log(" pipc error", type(e).__name__, str(e)[:120])
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
