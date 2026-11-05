"""probe 184: (a) 개인정보위 결과의 공표 PDF 중 줄을 못 나눈 것(앞 500자), (b) 공정위 의결서 목록 과거 쪽(2016~) 형식·사건명에서 피심인 뽑기.
저장 안 함. 공표 대상은 법인·기관, 사건명은 공개 목록."""
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
log("# 개인정보위 PDF 줄 수")
try:
    ids = []
    for n in range(1, 5):
        r = s.get(f"{osn.PIPC_LIST}&pageIndex={n}", timeout=30)
        got = [x for x in dict.fromkeys(re.findall(r"selectBoardArticle\.do[^\"']*?nttId=(\d+)", r.text)) if x not in ids]
        if not got:
            break
        ids += got
    for ntt in ids:
        v = s.get(osn.PIPC_VIEW + ntt, timeout=30)
        for fid, sn in re.findall(r"fn_egov_downFile\w*\(\s*'([^']+)'\s*,\s*'([^']+)'", v.text)[:3]:
            f = s.get(osn.PIPC_FILE.format(fid, sn), headers={"Referer": osn.PIPC_VIEW + ntt}, timeout=40)
            txt = osn.attachment_text(f.content)
            if txt is None:
                log(f" {ntt} unread {f.content[:4]!r}")
                continue
            rows = osn.pipc_rows(txt)
            log(f" {ntt} {f.content[:4]!r} rows {len(rows)} orgs {[r['org'][:20] for r in rows][:8]}")
            if not rows:
                log("   head:", re.sub(r"\s+", " ", txt)[:600])
        time.sleep(0.3)
except Exception as e:
    log(" pipc error", type(e).__name__, str(e)[:120])

log("\n# 공정위 목록 2016~")
try:
    for page in (1, 250, 496, 497):
        t1 = time.time()
        r = s.get(ks.FTC_LIST, params={"startRceptDt": "2016-01-01", "endRceptDt": "2026-11-05", "pageIndex": page}, timeout=40)
        rows, last = ks.parse_ftc_list(r.text)
        log(f" page {page} rows {len(rows)} last {last} {time.time() - t1:.1f}s {len(r.text)}B")
        for x in rows[:6]:
            log("   ", x["decidedOn"], "|", x["name"][:70], "|", x["action"], "|", x["csno"])
        time.sleep(0.5)
except Exception as e:
    log(" ftc error", type(e).__name__, str(e)[:120])
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
