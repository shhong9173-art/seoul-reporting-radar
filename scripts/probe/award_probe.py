"""probe: 광명시 새올 목록 모양(공개 자료) — 두 번까지."""
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as w  # noqa: E402

out = []
base = "https://eminwon.gm.go.kr"
for attempt in range(2):
    try:
        t0 = time.time()
        r = requests.post(base + w.PATH, data={**w.LIST, "pageIndex": "1"}, headers={**w.UA, "Referer": base + w.PATH}, timeout=75)
        t = r.text
        rows = w.parse_rows(t)
        out.append(f"HTTP {r.status_code} {time.time() - t0:.0f}s len {len(t)} rows {len(rows)} sample {[(x['mgt'], x['no'], x['title'][:30], x['date']) for x in rows[:3]]}")
        k = t.find("searchDetail", 9000)
        out.append(re.sub(r"\s+", " ", t[k - 600:k + 1800]))
        break
    except Exception as e:  # noqa: BLE001
        out.append(f"ERR {type(e).__name__} {time.time() - t0:.0f}s")
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
