"""probe: 광주 서구 새올 목록 — 표가 어디에 어떤 모양으로 있는지(공개 자료)."""
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_local_notice_watch as w  # noqa: E402

out = []
base = "https://eminwon.seogu.gwangju.kr"
try:
    r = requests.post(base + w.PATH, data={**w.LIST, "pageIndex": "1"}, headers={**w.UA, "Referer": base + w.PATH}, timeout=75)
    t = r.text
    out.append(f"HTTP {r.status_code} len {len(t)} tr {len(re.findall('<tr', t))} td {len(re.findall('<td', t))}")
    for kw in ("not_ancmt_mgt_no", "searchDetail", "javascript:", "<table", "srchList", "고시", "2026-10"):
        idx = [m.start() for m in re.finditer(re.escape(kw), t)][:3]
        out.append(f"{kw}: {len(re.findall(re.escape(kw), t))} at {idx}")
    i = t.find("function srchList")
    out.append("srchList: " + re.sub(r"\s+", " ", t[i:i + 900]))
    j = t.find("<table")
    out.append("table: " + re.sub(r"\s+", " ", t[j:j + 1500]))
except Exception as e:  # noqa: BLE001
    out.append(f"ERR {type(e).__name__}")
blob = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
