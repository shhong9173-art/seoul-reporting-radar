"""격리 탐침 46: 새올 고시·공고 — 빠진 출입처 공장 시·군(울산 북구·동구, 완주, 인천 동구·부평, 순천, 함평, 봉화, 부산 강서·사하, 광명, 광주 서구·광산, 구미, 청주, 원주, 예산) 주소 찾기."""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as k  # noqa: E402

CANDS = {
    "울산 북구": ["eminwon.bukgu.ulsan.kr", "eminwon.ulsanbukgu.go.kr", "eminwon.ubg.go.kr"],
    "울산 동구": ["eminwon.donggu.ulsan.kr", "eminwon.ulsandonggu.go.kr", "eminwon.dong.ulsan.kr"],
    "완주군": ["eminwon.wanju.go.kr"],
    "인천 동구": ["eminwon.icdonggu.go.kr", "eminwon.donggu.incheon.kr"],
    "인천 부평구": ["eminwon.icbp.go.kr", "eminwon.bupyeong.go.kr"],
    "순천시": ["eminwon.suncheon.go.kr"],
    "함평군": ["eminwon.hampyeong.go.kr", "eminwon.hp.go.kr"],
    "봉화군": ["eminwon.bonghwa.go.kr"],
    "부산 강서구": ["eminwon.bsgangseo.go.kr", "eminwon.gangseo.busan.kr"],
    "부산 사하구": ["eminwon.saha.go.kr", "eminwon.saha.busan.kr"],
    "광명시": ["eminwon.gm.go.kr", "eminwon.gwangmyeong.go.kr"],
    "광주 서구": ["eminwon.seogu.gwangju.kr", "eminwon.gjseogu.go.kr"],
    "광주 광산구": ["eminwon.gwangsan.go.kr"],
    "구미시": ["eminwon.gumi.go.kr"],
    "청주시": ["eminwon.cheongju.go.kr"],
    "원주시": ["eminwon.wonju.go.kr"],
    "예산군": ["eminwon.yesan.go.kr"],
}


def try_host(city, host):
    res = []
    for scheme in ("https", "http"):
        base = f"{scheme}://{host}"
        t0 = time.time()
        try:
            r = requests.post(base + k.PATH, data={**k.LIST, "pageIndex": "1"}, headers={**k.UA, "Referer": base + k.PATH}, timeout=40)
            rows = k.parse_rows(r.text)
            res.append(f"{base} HTTP {r.status_code} {time.time() - t0:.0f}s rows={len(rows)} first={(rows[0]['date'], rows[0]['title'][:30]) if rows else None}")
            if rows:
                return res
        except Exception as e:  # noqa: BLE001
            res.append(f"{base} {type(e).__name__}")
    return res


jobs = [(c, h) for c, hs in CANDS.items() for h in hs]
with ThreadPoolExecutor(8) as ex:
    results = list(ex.map(lambda ch: (ch[0], try_host(*ch)), jobs))
out = [f"{c}: " + " | ".join(r) for c, r in results]
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
