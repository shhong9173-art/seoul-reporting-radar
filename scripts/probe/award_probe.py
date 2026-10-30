"""probe: 빈 칸을 빼는 파서로 기존 형식 시·군(당진·울주·울산 남구·아산·여수)과 광명 1쪽 다시 읽기 — 회귀 확인(공개 자료)."""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as w  # noqa: E402

PICK = ["당진시", "울주군", "울산 남구", "아산시", "여수시", "광주 서구", "광명시"]


def one(c):
    city, base, _ = c
    try:
        t = w.fetch_page(base, 1, requests.post, time.sleep)
        rows = w.parse_rows(t)
        bad = [r for r in rows if not r["title"] or not r["date"]]
        return f"{city}: rows {len(rows)} bad {len(bad)} no {sum(1 for r in rows if r['no'])} dept {sum(1 for r in rows if r['dept'])} | {rows[0]['title'][:30] if rows else '-'} | {rows[0]['dept'] if rows else '-'} | {rows[0]['date'] if rows else '-'}"
    except Exception as e:  # noqa: BLE001
        return f"{city}: ERR {type(e).__name__}"


with ThreadPoolExecutor(7) as ex:
    out = list(ex.map(one, [c for c in w.CITIES if c[0] in PICK]))
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
