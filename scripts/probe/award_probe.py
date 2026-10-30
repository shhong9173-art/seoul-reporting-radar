"""격리 탐침 46b: 새올 행 모양 — 광명(제목 빈칸), 광주 서구(행 0), 인천 동구(HTTP 400)."""
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as k  # noqa: E402

out = []
for base in ("https://eminwon.gm.go.kr", "https://eminwon.seogu.gwangju.kr", "http://eminwon.icdonggu.go.kr"):
    try:
        r = requests.post(base + k.PATH, data={**k.LIST, "pageIndex": "1"}, headers={**k.UA, "Referer": base + k.PATH}, timeout=40)
        trs = [t for t in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", r.text) if "searchDetail" in t or "<td" in t]
        out.append(f"{base} HTTP {r.status_code} len={len(r.text)} trs={len(trs)} sd={len(re.findall('searchDetail', r.text))} row1={re.sub(r'\\s+', ' ', trs[1] if len(trs) > 1 else (trs[0] if trs else r.text[:600]))[:900]}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{base} {type(e).__name__}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
