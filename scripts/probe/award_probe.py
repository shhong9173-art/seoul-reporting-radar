"""probe 192: 출입처 주총 소집공고 세부경력 표 꼴 — 기간·내용이 줄마다 따로 붙는 표(고려아연 2026-08-11)가 얼마나 되나, 원 HTML 꼴.
공개 공시. 저장 안 함. 후보 이름은 가린다."""
import json, os, re, sys, time
from pathlib import Path
import requests

sys.path.insert(0, "scripts")
import kr_exec_watch as kx  # noqa: E402
import kr_exec_market as km  # noqa: E402
import governance_watch as gw  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


key = os.environ.get("DART_API_KEY", "")
s = requests.Session()
t0 = time.time()
registry = json.loads(Path("dart_corp_codes.json").read_text(encoding="utf-8"))
try:
    import dart_watch
    table = dart_watch.load_corp_codes(key)
except SystemExit:
    table = None
codes, _ = gw.resolve_codes([n for n, _, _ in kx.BEATS], registry, table)
codes.pop("_spellings", None)
found = []
for name, code in codes.items():
    for b, e in (("20260115", "20260410"), ("20260601", "20261106")):
        r = s.get("https://opendart.fss.or.kr/api/list.json", params={"crtfc_key": key, "corp_code": code, "bgn_de": b, "end_de": e,
                                                                      "pblntf_ty": "E", "page_count": 100}, timeout=30)
        for x in r.json().get("list") or []:
            if "소집공고" in x["report_nm"] and "정정" not in x["report_nm"]:
                found.append((name, x["rcept_no"], x["report_nm"]))
        time.sleep(0.3)
log(f"출입처 {len(codes)}곳 · 소집공고 {len(found)}건")
GLUE = re.compile(r"(?:\d{2,4}\s*[.]?\s*\d{0,2}\s*[~∼\-–]\s*(?:현재?|\d{2,4}\s*[.]?\s*\d{0,2})\s*){3,}")
seen_co = set()
for name, rc, rn in found:
    if name in seen_co and len(seen_co) < 30:
        continue
    seen_co.add(name)
    texts, err = kx.fetch_document(key, rc, get=s.get, sleep=time.sleep, want=None)
    time.sleep(0.5)
    if not texts:
        log(f"[{name} {rc}] 원문 실패 {err}")
        continue
    cs = []
    for t in texts:
        cs = km.parse_agm_candidates(t)
        if cs:
            break
    glued = [p for p in cs if GLUE.search(p.get("career", ""))]
    log(f"[{name} {rc} {rn[:14]}] 후보 {len(cs)} · 경력칸 {sum(1 for p in cs if p.get('career'))} · 붙음 {len(glued)}")
    for p in cs[:2]:
        log(f"   {p.get('name', '')[:1]}○○ {p.get('kind', '')[:8]} 경력 「{p.get('career', '')[:150]}」")
    if glued:
        t = next(t for t in texts if km.parse_agm_candidates(t))
        for part in kx.TABLE_SPLIT.split(t):
            if part[:6].upper() == "<TABLE" and re.search(r"세부\s*경력", kx.clean(part)):
                rows = kx.ROW.findall(part)
                for tr in rows[2:4]:
                    raw = re.sub(r"\s+", " ", tr)
                    raw = re.sub(r"<(TD|TE|TU|TH)\b[^>]*>", r"<\1>", raw, flags=re.I)
                    log("   RAW " + raw[:700])
                break
    if len(seen_co) >= 30 or time.time() - t0 > 900:
        break
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
