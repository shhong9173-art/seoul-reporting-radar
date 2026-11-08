"""probe 200: 단독 강화 조사 — ① 관보 2026-22630(강관 반덤핑 최종) 세율 표를 왜 못 읽었나 ② 금속노조 누리집의 지부·지회 게시판
③ NHTSA vPIC 2027·2028 모델 목록(현대·기아·제네시스) ④ 환경영향평가 정보지원시스템(EIASS)·노조 지부 누리집 robots. 저장 안 함."""
import json
import re
import sys
import time

import requests

sys.path.insert(0, "scripts")
OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


UA = {"User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"}
BUA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
       "Accept-Language": "ko-KR,ko;q=0.9"}


def get(url, **kw):
    t = time.time()
    try:
        r = requests.get(url, timeout=40, **kw)
        return r, f"{time.time() - t:.1f}s"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__} {str(e)[:60]}"


# ① 관보 강관 반덤핑 최종: 세율 표
try:
    import trade_remedy_watch as trw
    for doc in ("2026-22630", "2026-22626"):
        r, t = get(f"https://www.federalregister.gov/api/v1/documents/{doc}.json?fields[]=raw_text_url&fields[]=title", headers=UA)
        meta = r.json() if r is not None and r.status_code == 200 else {}
        log("FR", doc, r.status_code if r is not None else t, meta.get("title", "")[:90])
        if meta.get("raw_text_url"):
            r2, t2 = get(meta["raw_text_url"], headers=UA)
            body = r2.text if r2 is not None else ""
            lines = trw.text_lines(body)
            log("  rate_table:", json.dumps(trw.rate_table(lines, meta.get("title", "")), ensure_ascii=False)[:600])
            log("  named:", json.dumps(trw.named_companies(lines), ensure_ascii=False)[:300])
            flat = "\n".join(lines)
            i = flat.lower().find("final results of review")
            j = flat.lower().find("weighted-average dumping margin")
            k = max(i, 0)
            log("  around 'Final Results of Review':", flat[k:k + 1400].replace("\n", " | "))
            if j >= 0:
                log("  around 'weighted-average dumping margin':", flat[j:j + 700].replace("\n", " | "))
            app = flat.find("Appendix")
            log("  appendix:", flat[app:app + 1500].replace("\n", " | ") if app >= 0 else "없음")
        time.sleep(1)
except Exception as e:  # noqa: BLE001
    log("FR error", type(e).__name__, str(e)[:200])

# ② 금속노조 누리집 게시판 목록(지부·지회 소식이 있는지)
r, t = get("https://www.kmwu.kr/robots.txt", headers=BUA)
log("kmwu robots", r.status_code if r is not None else t, (r.text[:300].replace("\n", " | ") if r is not None else ""))
r, t = get("https://www.kmwu.kr/", headers=BUA)
if r is not None:
    links = sorted(set(re.findall(r'href="([^"]*(?:bo_table|board|bbs)[^"]*)"[^>]*>\s*([^<]{1,30})<', r.text)))
    log("kmwu home", r.status_code, len(r.text), "board links:", " ; ".join(f"{u} [{x.strip()}]" for u, x in links[:80]))
else:
    log("kmwu home", t)
time.sleep(1)

# ③ NHTSA vPIC: 모델 목록(새 이름이 미국 차대번호 체계에 먼저 들어오는지)
for make in ("hyundai", "kia", "genesis"):
    for my in (2026, 2027, 2028):
        r, t = get(f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear/make/{make}/modelyear/{my}?format=json", headers=UA)
        if r is not None and r.status_code == 200:
            res = r.json().get("Results") or []
            log("vPIC", make, my, len(res), ", ".join(sorted({x.get("Model_Name", "") for x in res}))[:500])
        else:
            log("vPIC", make, my, r.status_code if r is not None else t)
        time.sleep(0.5)
r, t = get("https://vpic.nhtsa.dot.gov/robots.txt", headers=UA)
log("vPIC robots", r.status_code if r is not None else t, (r.text[:300].replace("\n", " | ") if r is not None else ""))
r, t = get("https://vpic.nhtsa.dot.gov/mid/", headers=BUA)
log("vPIC mid", r.status_code if r is not None else t, (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:600] if r is not None else ""))

# ④ EIASS·노조 지부 누리집 후보(robots·첫 화면만)
for url in ("https://www.eiass.go.kr/robots.txt", "https://www.eiass.go.kr/", "https://www.hhu.or.kr/robots.txt", "https://www.hhu.or.kr/",
            "http://www.hhu.or.kr/", "https://hmunion.or.kr/", "https://www.kiaunion.or.kr/"):
    r, t = get(url, headers=BUA)
    if r is not None:
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
        log("site", url, r.status_code, len(r.text), r.url[:80], "|", txt[:400])
    else:
        log("site", url, t)
    time.sleep(1)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
