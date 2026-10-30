"""probe: 고친 파서로 광주 서구·광산구 2쪽 실제 읽기(공개 자료)."""
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as w  # noqa: E402

out = []
for city, base in (("광주 서구", "https://eminwon.seogu.gwangju.kr"), ("광주 광산구", "https://eminwon.gwangsan.go.kr")):
    try:
        rows, note = w.fetch_city(city, base, requests.post, time.sleep)
        out.append(f"== {city} rows {len(rows)} note {note} empty-title {sum(1 for r in rows if not r['title'])} dates {sorted({r['date'] for r in rows})[-3:]}")
        for r in rows[:4]:
            out.append(f"  {r['mgt']} | {r['no']} | {r['title'][:50]} | {r['dept']} | {r['date']} | {w.classify(r['title'])}")
        hits = [(r["title"][:60], w.classify(r["title"])) for r in rows if w.classify(r["title"])[0]]
        out.append(f"  graded {len(hits)}: {hits[:5]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"ERR {city} {type(e).__name__} {str(e)[:80]}")
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
