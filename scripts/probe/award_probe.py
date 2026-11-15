"""probe 252: 보고기간 후 사건·매각예정 주석 읽기가 실제 3분기보고서에서 되는지. 한화솔루션(이미 보도된 건)은 줄 글자, 나머지는 건수·길이만."""
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT = []
import kr_exec_watch as kx  # noqa: E402
import kr_report_notes as n  # noqa: E402

key = os.environ.get("DART_API_KEY")
DOCS = [("한화솔루션", "20261112000489", True)]
try:
    import json
    import datetime as dt
    import dart_watch
    import earnings_compare as ec
    import governance_watch as gw
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    table = dart_watch.load_corp_codes(key)
    now = dt.datetime.now(ec.KST)
    names = ["두산에너빌리티", "포스코홀딩스", "롯데케미칼", "금호타이어", "세아제강", "동국제강", "현대위아", "한국타이어앤테크놀로지"]
    codes, _ = gw.resolve_codes(names, registry, table)
    for name in names:
        st, body = ec.call("list.json", {"corp_code": codes[name], "bgn_de": "20261101", "end_de": now.strftime("%Y%m%d"), "pblntf_ty": "A", "page_count": "20"},
                           get=lambda u, params, **kw: requests.get(u, params={"crtfc_key": key, **params}, **kw), sleep=time.sleep)
        rcept, _ = n.report_of((body or {}).get("list") or [], 2026, "11014")
        if rcept:
            DOCS.append((name, rcept, False))
except Exception as e:  # noqa: BLE001
    OUT.append(f"목록 실패 {type(e).__name__}: {str(e)[:120]}")
for name, rcept, show in DOCS:
    t0 = time.time()
    texts, err = kx.fetch_document(key, rcept, get=requests.get, sleep=time.sleep, want="제재")
    if not texts:
        OUT.append(f"{name}: 원문 실패 {err}")
        continue
    sec = max((n.sections(t) for t in texts[:3]), key=len)
    titles = [n.clean(m.group(1)) for m in n.TITLE.finditer(texts[0])]
    note_titles = [t for t in titles if n.AFTER_TITLE.search(t) or n.HELD_TITLE.search(t)]
    parts = [f"{name} {time.time() - t0:.0f}초 · 제목 표시 {len(titles)}개 · 주석 제목 {note_titles[:4]}"]
    for k in ("after", "held", "sanction", "suit", "consol"):
        v = sec.get(k, "없음")
        parts.append(f"{k}: " + ("없음" if v == "없음" else "생략" if v is None else f"{len(v)}줄(길이 {sorted(len(x) for x in v)[:1]}~{sorted(len(x) for x in v)[-1:]})"))
    OUT.append(" | ".join(parts))
    if show:
        for k in ("after", "held"):
            for x in (sec.get(k) or [])[:6]:
                OUT.append(f"   {k}: {x[:330]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
