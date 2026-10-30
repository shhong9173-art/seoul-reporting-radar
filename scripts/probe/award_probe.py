"""Probe: 바레인 입찰위원회 낙찰 목록·보고서에서 일진전기(Iljin) — 공개 자료. 저장하지 않음."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overseas_award_watch as w  # noqa: E402

out = []
try:
    r = w._get(None, w.BH_LIST, headers={**w.UA, "Accept": "text/html"})
    html = r.text
    out.append(f"list HTTP {r.status_code} len {len(html)}")
    reps = w.bh_reports(html)
    out.append("reports: " + " | ".join(f"{x['subject'][:60]} -> {x['href'][-70:]}" for x in reps[:8]))
    # other links on the page (per-tender award pages? search forms?)
    links = sorted(set(re.findall(r'href="([^"#]+)"', html)))
    out.append("page links sample: " + " | ".join(l for l in links if re.search(r"award|tender|result|session|opening", l, re.I))[:1500])
    out.append("iljin on list page: " + str(bool(re.search(r"iljin", html, re.I))))
    for rep in reps[:4]:
        url = w.BH_SITE + rep["href"].replace(" ", "%20")
        try:
            pr = w._get(None, url, headers={**w.UA, "Accept": "application/pdf"}, timeout=120)
            size = len(pr.content)
            text = w.pdf_text(pr.content) if pr.status_code == 200 and size <= w.BH_MAX_BYTES else ""
            hits = [m.start() for m in re.finditer(r"iljin|korea|transmission|400\s*kv|220\s*kv|cable", text, re.I)]
            out.append(f"\n== {rep['subject'][:70]} HTTP {pr.status_code} bytes {size} text {len(text.strip())} hits {len(hits)}")
            out.append("   head: " + re.sub(r"\s+", " ", text[:600]))
            for h in hits[:8]:
                out.append("   ctx: " + re.sub(r"\s+", " ", text[max(0, h - 200): h + 250]))
        except Exception as e:  # noqa: BLE001
            out.append(f"   {rep['subject'][:50]} error {type(e).__name__}: {str(e)[:120]}")
except Exception as e:  # noqa: BLE001
    out.append(f"error {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
