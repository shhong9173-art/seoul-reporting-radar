"""Probe 6: 바레인 개찰 결과 검색 파라미터 형식(JS) — 공개 자료, 저장하지 않음."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overseas_award_watch as w  # noqa: E402
import requests  # noqa: E402

out = []
S = requests.Session()
S.headers.update(w.UA)
t = S.get(w.BH_SITE + "/Tenders/OpenedBids/", timeout=60).text
for key in ["openedDate_filter", "endDate_filter", "SortingType", "ddlTendertype", "ddlCategory", "Category_value", "pageIndex", "datepicker", "dateFormat", "OnSuccess"]:
    for m in list(re.finditer(re.escape(key), t))[:3]:
        out.append(f"[{key}] " + re.sub(r"\s+", " ", t[max(0, m.start() - 300): m.end() + 300]))
sel = re.findall(r"<select[^>]*id=\"([^\"]+)\"[^>]*>(.*?)</select>", t, re.S)
for sid, opts in sel:
    out.append(f"select {sid}: " + " | ".join(re.sub(r"\s+", " ", o) for o in re.findall(r"<option[^>]*>.*?</option>", opts, re.S)[:12]))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:500])
