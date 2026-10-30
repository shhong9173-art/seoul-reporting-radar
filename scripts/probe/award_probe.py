"""Probe 2: 바레인 입찰위원회 — 개찰 결과(입찰사·가격)·위원회 결정 페이지 형식, robots, 일진전기(Iljin) 흔적. 공개 자료, 저장하지 않음."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import overseas_award_watch as w  # noqa: E402

out = []
def get(url, **kw):
    return w._get(None, url, headers={**w.UA, "Accept": "text/html,application/json"}, **kw)

for path in ["/robots.txt", "/", "/Tenders/OpenedTenders/", "/Tenders/TenderBoardDecisions/", "/Tenders/Decisions/", "/Tenders/PublicTenders/", "/Tenders/AwardedTenders/"]:
    try:
        r = get(w.BH_SITE + path, timeout=60)
        t = r.text
        out.append(f"\n== {path} HTTP {r.status_code} len {len(t)} final {getattr(r, 'url', '')}")
        if path == "/robots.txt":
            out.append(t[:800])
            continue
        links = sorted(set(re.findall(r'href="([^"#]+)"', t)))
        out.append("links: " + " | ".join(l for l in links if re.search(r"tender|award|open|decision|result|session|search", l, re.I))[:1800])
        forms = re.findall(r"<form[^>]*>", t, re.I)
        out.append("forms: " + " | ".join(forms[:5])[:600])
        apis = sorted(set(re.findall(r"""['"](/[A-Za-z/]*(?:api|Api|Handler|Service)[^'"]{0,80})['"]""", t)))
        out.append("api-like: " + " | ".join(apis[:20])[:800])
        if re.search(r"iljin", t, re.I):
            i = re.search(r"iljin", t, re.I).start()
            out.append("ILJIN ctx: " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[max(0, i - 600): i + 400])))
        body = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", t)))
        out.append("text: " + body[:900])
    except Exception as e:  # noqa: BLE001
        out.append(f"== {path} error {type(e).__name__}: {str(e)[:150]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:500])
