"""probe: 빠진 출입처 공장 시·군의 새올 고시·공고 목록(1쪽)이 GitHub 러너에서 열리는지 — 75초 대기, 병렬. 공개 자료."""
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as w  # noqa: E402

CAND = [("인천 동구(현대제철 인천·동국제강 인천)", ["https://eminwon.icdonggu.go.kr", "http://eminwon.icdonggu.go.kr"]),
        ("인천 부평구(한국GM)", ["https://eminwon.icbp.go.kr", "http://eminwon.icbp.go.kr"]),
        ("인천 서구", ["https://eminwon.seo.incheon.kr", "http://eminwon.seo.incheon.kr"]),
        ("광주 서구(기아 오토랜드 광주)", ["https://eminwon.seogu.gwangju.kr", "http://eminwon.seogu.gwangju.kr"]),
        ("광주 광산구(금호타이어 광주)", ["https://eminwon.gwangsan.go.kr", "http://eminwon.gwangsan.go.kr"]),
        ("광명시(기아 오토랜드 광명)", ["https://eminwon.gm.go.kr", "http://eminwon.gm.go.kr"]),
        ("구미시(LS전선·LS MnM?)", ["https://eminwon.gumi.go.kr", "http://eminwon.gumi.go.kr"]),
        ("청주시(LS일렉트릭 청주)", ["https://eminwon.cheongju.go.kr", "http://eminwon.cheongju.go.kr"]),
        ("순천시(현대제철 순천)", ["https://eminwon.suncheon.go.kr", "http://eminwon.suncheon.go.kr"]),
        ("경주시", ["https://eminwon.gyeongju.go.kr", "http://eminwon.gyeongju.go.kr"]),
        ("김천시", ["https://eminwon.gc.go.kr", "http://eminwon.gc.go.kr"]),
        ("시흥시", ["https://eminwon.siheung.go.kr", "http://eminwon.siheung.go.kr"]),
        ("안산시", ["https://eminwon.iansan.net", "http://eminwon.iansan.net"]),
        ("양산시(넥센 양산)", ["https://eminwon.yangsan.go.kr"])]


def one(label, bases):
    res = []
    for base in bases:
        t = time.time()
        try:
            r = requests.post(base + w.PATH, data={**w.LIST, "pageIndex": "1"}, headers={**w.UA, "Referer": base + w.PATH}, timeout=75)
            rows = w.parse_rows(r.text) if r.status_code == 200 else []
            res.append(f"{base} HTTP {r.status_code} {time.time() - t:.0f}s rows {len(rows)} first {rows[0]['title'][:40] if rows else '-'}")
            if rows:
                break
        except Exception as e:  # noqa: BLE001
            res.append(f"{base} {type(e).__name__} {time.time() - t:.0f}s")
    return f"{label}: " + " | ".join(res)


out = []
try:
    with ThreadPoolExecutor(max_workers=7) as ex:
        out = list(ex.map(lambda c: one(*c), CAND))
except Exception:  # noqa: BLE001
    out.append("ERR " + traceback.format_exc()[-800:])
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
