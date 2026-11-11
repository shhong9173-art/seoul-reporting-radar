"""무역위 새 조사 품목 → 출입처 사업보고서 'II. 사업의 내용' 대조(11-11).

무역위원회 누리집에는 신청인(국내 생산자) 이름이 없다. 11-05 '중국, 미국, 말레이시아산 아크릴산 2-에틸헥실' 새 조사는
Claude가 발제로 추천하고 기자가 LG화학에 직접 물어 신청인을 확인해 [단독]이 됐다(11-06). 그 확인 질문을 그날 바로 던질 수 있게,
새 조사 품목 낱말이 어느 출입처의 최근 사업보고서 '사업의 내용'에 나오는지 원문 문맥으로 붙인다.

지킬 것
- 사업보고서에 낱말이 있다 = 그 회사가 그 품목(또는 비슷한 이름의 다른 품목)을 다룬다는 원문 단서일 뿐, 신청인 확정이 아니다.
- 낱말이 없다 = 보고서에 안 적었을 수 있다(안 만든다는 뜻 아님). 조회 실패는 미확인.
- 한 실행에 새 조사 2건까지, 회사마다 보고서 한 번(같은 실행 안에서 재사용). 결과는 사건별로 저장해 다시 받지 않는다.
- 결과는 기자 전용 저장소(trade-remedy)에만. 공개 로그엔 건수만.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 품목 낱말 → 출입 업종 묶음(ktc_watch.BEAT에서 화학·철강만). 전선·자동차·배터리 품목은 아직 안 본다.
CHEM = re.compile(r"PET|폴리|수지|에틸|아크릴|페놀|에폭시|가소제|초산|프로필렌|부타디엔|카본블랙|스티렌|글리콜|메탄올|수산화나트륨|"
                  r"가성소다|염소|폴리실리콘|아세트|벤젠|톨루엔|자일렌|합성고무|에스테르|옥탄올|부탄올|알코올|아민|올레핀|에틸렌", re.I)
STEEL = re.compile(r"강관|강판|냉연|열연|후판|형강|봉강|철근|선재|스테인리스|도금|석도|아연|강선|철강|합금철|페로|빌릿|슬래브|무계목")
GROUPS = {"화학": ("LG화학", "롯데케미칼", "금호석유화학", "한화솔루션", "OCI홀딩스", "S-Oil", "SK이노베이션", "HD현대오일뱅크"),
          "철강": ("포스코", "현대제철", "동국제강", "세아제강", "고려아연", "영풍")}
COUNTRIES = {"중국", "미국", "말레이시아", "대만", "일본", "인도", "태국", "베트남", "인도네시아", "아랍에미리트연합", "아랍에미리트연방", "러시아",
             "싱가포르", "사우디아라비아", "브라질", "독일", "타이"}
STOP = COUNTRIES | {"제품", "조사", "및", "등", "산", "원심", "재심", "부과", "국내산업피해", "덤핑사실", "유무", "에", "대한", "의", "덤핑방지관세",
                    "종료재심사", "필름", "수지"}
STEM = re.compile(r"^(.{2,})(강관|강판|형강|봉강)$")   # '무계목강관' → '무계목'도(보고서는 '무계목 강관'처럼 띄어 쓸 수 있다)
MAX_CASES = 2
WINDOW_DAYS = 45
SNIPPET = 40


def group_of(product):
    p = str(product or "")
    if STEEL.search(p):
        return "철강"
    if CHEM.search(p):
        return "화학"
    return None


def tokens(product):
    """품목 이름 → 찾을 낱말(긴 것부터, 4개까지). '2-에틸헥실'은 '에틸헥실'도. 나라 이름·일반 낱말은 뺀다."""
    out = []
    for w in re.findall(r"[0-9A-Za-z가-힣][0-9A-Za-z가-힣\-]*", str(product or "")):
        if w.endswith("산") and w[:-1] in COUNTRIES:   # '말레이시아산'·'중국산'
            continue
        stem = STEM.match(w)
        for t in (w, re.sub(r"^\d+-", "", w), stem.group(1) if stem else ""):
            if len(t) >= 2 and t not in STOP and not t.isdigit() and t not in out:
                out.append(t)
    return sorted(out, key=len, reverse=True)[:4]


def snippets(text, token, n=2):
    out = []
    for m in re.finditer(re.escape(token), text):
        a, b = max(0, m.start() - SNIPPET), min(len(text), m.end() + SNIPPET)
        s = re.sub(r"\s+", " ", text[a:b]).strip()
        if s not in out:
            out.append(s)
        if len(out) >= n:
            break
    return out


def corp_codes():
    try:
        d = json.loads((ROOT / "digests" / "business_content_latest.json").read_text(encoding="utf-8"))
        return {c["company"]: c["corpCode"] for c in d.get("companies") or [] if c.get("company") and c.get("corpCode")}
    except (OSError, ValueError):
        return {}


def report_year(now):
    """가장 최근 사업보고서 회계연도(3월 말 제출 — 4월부터 전년도)."""
    return now.year - 1 if now.month >= 4 else now.year - 2


def case_evidence(case, key, now, codes, cache, *, list_fetch=None, doc_fetch=None, plain=None):
    import business_content as bc
    list_fetch = list_fetch or bc.api_json
    doc_fetch = doc_fetch or bc.api_bytes
    plain = plain or bc.plain
    group, toks, year = group_of(case.get("product")), tokens(case.get("product")), report_year(now)
    out = {"caseId": case["id"], "product": case.get("product"), "group": group, "tokens": toks, "year": year,
           "checkedAt": now.isoformat(timespec="seconds"), "companies": []}
    for name in GROUPS.get(group, ()):
        row = {"company": name}
        code = codes.get(name)
        if not code:
            out["companies"].append({**row, "status": "no_code"})
            continue
        try:
            if name not in cache:
                rec = bc.annual_receipt(key, code, year, fetch=list_fetch)
                if not rec.get("receiptNo"):
                    cache[name] = {"status": rec.get("status") or "no_report"}
                else:
                    rep = bc.fetch_report(key, rec["receiptNo"], fetch=doc_fetch)
                    cache[name] = {"status": rep["status"], "receiptNo": rec["receiptNo"],
                                   "text": plain(rep["section"]) if rep.get("section") else ""}
            got = cache[name]
            if got.get("status") != "found":
                out["companies"].append({**row, "status": got.get("status") or "error", **({"receiptNo": got["receiptNo"]} if got.get("receiptNo") else {})})
                continue
            hits = {t: got["text"].count(t) for t in toks if got["text"].count(t)}
            first = next(iter(hits), None)
            out["companies"].append({**row, "status": "found" if hits else "none", "receiptNo": got["receiptNo"], "hits": hits,
                                     **({"snippets": snippets(got["text"], first)} if first else {})})
        except Exception as e:  # noqa: BLE001 — 한 회사 실패가 다른 회사를 막지 않는다(미확인으로 남김)
            out["companies"].append({**row, "status": "error", "error": type(e).__name__})
    return out


def attach(doc, previous, key, now, **kw):
    """doc['ktc']['producers'][사건 id] — 최근 WINDOW_DAYS일 새 조사(이벤트 ktcKind=case, 출입 업종 품목, 화학·철강 묶음) 중 아직 안 본 것.
    반환: (새로 본 사건 수, 회사 조회 수). 키가 없으면 아무것도 안 한다."""
    k = doc.get("ktc")
    if not isinstance(k, dict):
        return 0, 0
    old = ((previous or {}).get("ktc") or {}).get("producers") or {}
    prod = {cid: v for cid, v in old.items() if isinstance(v, dict)}
    since = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    cases = [e for e in doc.get("events") or [] if e.get("pageId") == "ktc" and e.get("ktcKind") == "case" and e.get("beat")
             and str(e.get("detectedAt") or "") >= since and group_of(e.get("product")) and tokens(e.get("product"))]
    todo = [e for e in sorted(cases, key=lambda e: str(e.get("detectedAt")), reverse=True) if e["id"] not in prod][:MAX_CASES]
    if not key or not todo:
        k["producers"] = prod
        return 0, 0
    codes, cache = corp_codes(), {}
    for e in todo:
        ev = case_evidence(e, key, now, codes, cache, **kw)
        ev["line"] = line(ev)   # 오늘의 레이더(digest.mjs)는 이 줄을 그대로 붙인다
        prod[e["id"]] = ev
    k["producers"] = {cid: v for cid, v in prod.items() if str(v.get("checkedAt") or "") >= (now - timedelta(days=120)).isoformat()}
    return len(todo), len(cache)


def line(ev):
    """오늘의 레이더 한 줄: '출입처 2025 사업보고서(사업의 내용) 대조: LG화학 「아크릴산」 3곳 「…」 · 낱말 없음 6곳(안 만든다는 뜻 아님) · 미확인 1곳'."""
    if not isinstance(ev, dict) or not ev.get("companies"):
        return ""
    found = [c for c in ev["companies"] if c.get("status") == "found"]
    none = [c["company"] for c in ev["companies"] if c.get("status") == "none"]
    bad = [c["company"] for c in ev["companies"] if c.get("status") not in ("found", "none")]
    parts = [f"{c['company']} " + ", ".join(f"'{t}' {n}곳" for t, n in c["hits"].items())
             + (f" 「{c['snippets'][0]}」" if c.get("snippets") else "") + f"(접수 {c['receiptNo']})" for c in found]
    tail = ([f"낱말 없음 {len(none)}곳({'·'.join(none)}) — 안 만든다는 뜻 아님"] if none else []) + ([f"미확인 {len(bad)}곳({'·'.join(bad)})"] if bad else [])
    return (f"출입처 {ev.get('year')} 사업보고서(II. 사업의 내용) 품목 낱말 대조[{', '.join(ev.get('tokens') or [])}]: "
            + " · ".join(parts + tail) + " — 신청인 확정 아님(회사 확인)")
