"""Probe: 전기위원회 제330차 개최결과 PDF 형식(공개 자료). 저장하지 않음."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_energy_watch as k  # noqa: E402

out = []
try:
    r = k._get(None, k.KOREC_RESULTS)
    rows = k.result_rows(r.text)
    out.append(f"list {r.status_code} rows {len(rows)}: " + " | ".join(f"{t}/{p}/{n}" for t, p, n in rows[:4]))
    for title, posted, name in rows[:3]:
        if "330" not in title and "329" not in title:
            continue
        raw, _ = k.korec_file(name)
        text = k.pdf_text(raw)
        held, counts, items = k.meeting_items(text)
        out.append(f"\n=== {title} posted {posted} file {name} bytes {len(raw)} textlen {len(text)} held {held} counts {counts} items {items[:12]}")
        flat = re.sub(r"[ \t]+", " ", text)
        out.append("--- TEXT HEAD ---\n" + flat[:5200])
        for m in re.finditer(r"\d{2}\.\s*\d{1,2}\.\s*\d{1,2}\.", flat):
            out.append(f"date ctx: …{flat[max(0, m.start() - 60):m.end() + 40]!r}")
except Exception as e:  # noqa: BLE001
    out.append(f"error {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:500])
