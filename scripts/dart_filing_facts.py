"""DART 수시공시 원문 요점과 같은 회사 직전 동종 공시 비교 (단독 후보 심사용).

- 한국거래소 수시공시(채무보증·공급계약·유형자산·타법인주식·신규시설투자·소송 등)는 '항목 | 값' 표 한 장이다
  (2026-10-27 실제 공시로 형식 확인: HD현대일렉트릭 20261026800468, 고려아연 20261023801005, 엘에스일렉트릭
  20261019800108, 한화솔루션 20260908800375·20260908800378, 대한전선 20260513801130·20250716800108,
  현대자동차 20260424800636). 표의 항목명 그대로 값을 뽑는다. 값을 만들거나 단위를 추정하지 않는다.
- '※ 관련공시' 칸은 회사가 직접 적은 이전 공시라 그대로 보여 준다.
- 직전 비교: OpenDART 공시검색(list.json, 거래소공시)으로 같은 회사의 최근 3년 같은 종류 공시를 찾아
  원문을 몇 건 읽고, 같은 상대(채무자·계약상대·발행회사)가 있으면 금액을 나란히 놓는다.
- 일상 판정은 원문 숫자로만: 같은 자회사·계열사 채무자 반복 보증이면서 자기자본 대비 5% 미만, 임원·주요주주
  거래계획 보고 같은 형식 공시. 그 밖은 판정하지 않는다(단독 여부는 기자 판단).
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from dart_contract_tables import CellTableParser, clean_label, plain  # noqa: E402

LIST_API = "https://opendart.fss.or.kr/api/list.json"
YEARS_BACK = 3
MAX_PREV_DOCS = 4
SUBSIDIARY = re.compile(r"자회사|종속|계열|손자회사|관계회사")
CELL_XML = re.compile(r"<(/?)t[eu](?![A-Za-z0-9_])", re.I)


def norm(label):
    return clean_label(label).replace("·", "ㆍ").replace(" ", "")


# (key, report-name pattern, fields shown in this order, counterparty field)
TYPES = [
    ("채무보증", r"타인에대한채무보증", ["채무자", "회사와의관계", "채권자", "채무보증금액(원)", "자기자본대비(%)",
                                     "채무보증기간 시작일", "채무보증기간 종료일", "채무보증총잔액(원)"], "채무자"),
    ("공급계약", r"단일판매ㆍ공급계약", ["체결계약명", "계약금액(원)", "매출액대비(%)", "계약상대", "회사와의관계",
                                    "판매ㆍ공급지역", "계약기간 시작일", "계약기간 종료일"], "계약상대"),
    ("유형자산취득", r"유형자산취득", ["취득물건구분", "취득물건명", "취득가액(원)", "자산총액대비(%)", "거래상대", "취득목적", "취득예정일자"], "거래상대"),
    ("유형자산처분", r"유형자산처분", ["처분물건구분", "처분물건명", "처분가액(원)", "자산총액대비(%)", "거래상대", "처분목적", "처분예정일자"], "거래상대"),
    ("타법인주식취득", r"타법인주식및출자증권취득", ["회사명", "회사와관계", "주요사업", "취득금액(원)", "자기자본대비(%)", "지분비율(%)",
                                              "취득목적", "취득예정일자"], "회사명"),
    ("타법인주식처분", r"타법인주식및출자증권처분", ["회사명", "회사와관계", "처분금액(원)", "자기자본대비(%)", "지분비율(%)", "처분목적",
                                              "처분예정일자"], "회사명"),
    ("신규시설투자", r"신규시설투자", ["투자구분", "투자대상", "투자금액(원)", "자기자본대비(%)", "투자목적",
                                  "투자기간 시작일", "투자기간 종료일"], "투자대상"),
    # a lawsuit is identified by its case number; case names like '주주대표소송' repeat across different cases
    ("소송판결", r"소송등의판결", ["사건의명칭", "사건번호", "원고ㆍ신청인", "판결ㆍ결정내용", "관할법원", "판결ㆍ결정일자"], "사건번호"),
    ("소송제기", r"소송등의제기", ["사건의명칭", "사건번호", "원고ㆍ신청인", "청구내용", "관할법원", "제기ㆍ신청일자"], "사건번호"),
    # 거래계획 보고: 표지의 '보고자 : | 이름'(2026-10-28 영풍 20261028000440 장세환), 철회 보고서는 '보 고 자: | (성 명)' 다음 칸일 수 있다
    ("거래계획", r"특정증권등거래계획", ["보고자", "성명", "거래시작일(결제일)", "거래목적"], None),
    # 형식 공시명만으로는 내용을 알 수 없는 공시: 원문의 제목 칸을 읽는다(2026-10-31 실제 공시로 형식 확인:
    # OCI홀딩스 20261029800315 수시공시의무관련사항(공정공시) '1. 정보내용 | 공시제목 | …',
    # 현대자동차 20261029800231 장래사업ㆍ경영계획(공정공시) '1. 장래계획 사항 | …'). 같은 상대 비교는 하지 않는다.
    ("공정공시", r"수시공시의무관련사항|장래사업ㆍ?경영계획|기타경영사항|투자판단관련주요경영사항",
     ["공시제목", "장래계획사항", "제목", "관련수시공시내용", "세부내용", "주요내용"], None),
]
NO_PREVIOUS = ("거래계획", "공정공시")
AMOUNT_KEY = {"채무보증": "채무보증금액(원)", "공급계약": "계약금액(원)", "유형자산취득": "취득가액(원)", "유형자산처분": "처분가액(원)",
              "타법인주식취득": "취득금액(원)", "타법인주식처분": "처분금액(원)", "신규시설투자": "투자금액(원)"}
RATIO_KEY = {"채무보증": "자기자본대비(%)", "공급계약": "매출액대비(%)", "유형자산취득": "자산총액대비(%)", "유형자산처분": "자산총액대비(%)",
             "타법인주식취득": "자기자본대비(%)", "타법인주식처분": "자기자본대비(%)", "신규시설투자": "자기자본대비(%)"}
PERIOD_PARENTS = ("계약기간", "채무보증기간", "투자기간", "보증기간")
SAME_LABEL = {"채무보증": "같은 채무자", "공급계약": "같은 계약상대", "유형자산취득": "같은 거래상대", "유형자산처분": "같은 거래상대",
              "타법인주식취득": "같은 발행회사", "타법인주식처분": "같은 발행회사", "신규시설투자": "같은 투자대상",
              "소송판결": "같은 사건(사건번호)", "소송제기": "같은 사건(사건번호)"}


def filing_type(report_name):
    t = re.sub(r"\s+", "", str(report_name or "")).replace("·", "ㆍ")
    for key, rx, *_ in TYPES:
        if re.search(rx, t):
            return key
    return None


def pairs(documents):
    """Label/value pairs in table order. Period dates keep their parent ('채무보증기간 시작일')."""
    out, related = [], None
    for doc in documents:
        if not isinstance(doc, str):
            continue
        # DART 정기·주요공시 XML(dart4.xsd)은 입력 칸을 <TE>·<TU>로 쓴다(거래계획 보고서의 '보고자 : | 이름' 등) — 칸으로 읽는다.
        doc = CELL_XML.sub(lambda m: f"<{m.group(1)}td", doc)
        p = CellTableParser()
        try:
            p.feed(doc)
            p.close()
        except (ValueError, TypeError):
            continue
        for table in p.tables:
            parent = None
            for row in table:
                if any(c.get("nested") for c in row):
                    continue
                cells = [c["text"] for c in row]
                found = []
                if len(cells) == 2:
                    found = [(cells[0], cells[1])]
                elif len(cells) == 3:
                    if norm(cells[1]) in ("시작일", "종료일"):
                        parent = norm(cells[0])
                    found = [(cells[1], cells[2])]
                elif len(cells) == 4:
                    found = [(cells[0], cells[1]), (cells[2], cells[3])]
                for label, value in found:
                    key = norm(label)
                    if key in ("시작일", "종료일") and parent and any(x in parent for x in PERIOD_PARENTS):
                        key = f"{parent} {key}"
                    value = plain(value)
                    if key == "※관련공시":  # not '※ 관련 공시법규' (the statute line)
                        related = value if value not in ("", "-") else related
                        continue
                    if key.startswith("※"):
                        continue
                    if key and value and value not in ("-", "－"):
                        out.append((key, value))
    return out, related


def won(value):
    """'53,417,160,000' → '53,417,160,000원(약 534억원)'. The exact figure always stays first."""
    digits = re.sub(r"[,\s]", "", str(value))
    if not re.fullmatch(r"\d+", digits):
        return str(value)
    n = int(digits)
    if n >= 10 ** 12:
        approx = f"약 {n / 10 ** 12:,.2f}조원"
    elif n >= 10 ** 8:
        approx = f"약 {n / 10 ** 8:,.0f}억원"
    else:
        return f"{value}원"
    return f"{value}원({approx})"


def facts(report_name, documents):
    kind = filing_type(report_name)
    got, related = pairs(documents)
    if kind is None:
        return {"type": None, "facts": [], "related": related}
    fields = next(f for k, _, f, _ in TYPES if k == kind)
    table = {}
    for k, v in got:
        table.setdefault(k, v)
    shown = []
    for f in fields:
        if f in table:
            v = table[f]
            v = won(v) if f.endswith("(원)") else (v if len(v) <= 160 else v[:157] + "…")
            shown.append([f, v])
    return {"type": kind, "facts": shown, "related": related, "raw": table}


def amount(table, kind):
    v = (table or {}).get(AMOUNT_KEY.get(kind, ""), "")
    d = re.sub(r"[,\s]", "", v)
    return int(d) if re.fullmatch(r"\d+", d) else None


def ratio(table, kind):
    v = (table or {}).get(RATIO_KEY.get(kind, ""), "")
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def party(table, kind):
    key = next((c for k, _, _, c in TYPES if k == kind), None)
    v = (table or {}).get(key or "", "")
    m = re.search(r"\(([A-Za-z][^()]{3,})\)", v)  # '유럽법인(HD Hyundai Electric Europe GmbH)' → the legal name
    return re.sub(r"[\s.,()]", "", (m.group(1) if m else v)).lower()


def previous_filings(api_key, corp_code, kind, before_day, rcept_no, *, get):
    """Same-type exchange disclosures of the same company in the last YEARS_BACK years, newest first."""
    rx = next(r for k, r, *_ in TYPES if k == kind)
    start = (before_day - dt.timedelta(days=365 * YEARS_BACK)).strftime("%Y%m%d")
    rows, page = [], 1
    while page <= 5:
        r = get(LIST_API, params={"crtfc_key": api_key, "corp_code": corp_code, "bgn_de": start, "end_de": before_day.strftime("%Y%m%d"),
                                  "pblntf_ty": "I", "page_no": page, "page_count": 100}, timeout=30)
        body = r.json() if getattr(r, "status_code", 200) == 200 else {}
        if body.get("status") == "013":
            break
        if body.get("status") != "000":
            raise RuntimeError(f"OpenDART 목록 {body.get('status') or getattr(r, 'status_code', '?')}")
        for x in body.get("list") or []:
            nm = re.sub(r"\s+", "", x.get("report_nm", "")).replace("·", "ㆍ")
            if re.search(rx, nm) and x.get("rcept_no") != rcept_no and x.get("rcept_no", "") < rcept_no:
                rows.append({"rcept_no": x["rcept_no"], "date": x.get("rcept_dt"), "report": x.get("report_nm", "").strip(),
                             "corrected": "정정" in nm})
        if page >= int(body.get("total_page") or 1):
            break
        page += 1
    return sorted(rows, key=lambda x: x["rcept_no"], reverse=True)


def day_of(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if d and len(d) == 8 else d


def compare(kind, cur, prev_docs, n_listed):
    """prev_docs: [(meta, table)] newest first. Returns (lines, routine_reason)."""
    lines, routine = [], None
    if kind == "거래계획":
        return [], "임원·주요주주 거래계획 보고(형식 공시) — 거래 규모·당사자는 원문 확인"
    if kind == "공정공시":
        return [], None
    if not n_listed:
        return [f"최근 {YEARS_BACK}년 같은 종류 거래소 공시 없음(목록 기준)"], None
    same = None
    me = party(cur, kind)
    if me:
        same = next(((m, t) for m, t in prev_docs if party(t, kind) == me), None)
    a_now = amount(cur, kind)
    if same:
        m, t = same
        a_prev = amount(t, kind)
        change = ""
        if a_now and a_prev:
            pct = (a_now - a_prev) / a_prev * 100
            change = ": " + won(f"{a_prev:,}") + " → " + won(f"{a_now:,}") + f"({pct:+.0f}%)"
        lines.append(f"{SAME_LABEL.get(kind, '같은 상대')} 직전 공시 {day_of(m['date'])}(접수 {m['rcept_no']}){change}")
    elif me and prev_docs:
        lines.append(f"최근 {YEARS_BACK}년 같은 종류 공시 {n_listed}건(정정 포함, 목록 기준) 중 원문 {len(prev_docs)}건 확인 — {SAME_LABEL.get(kind, '같은 상대')} 없음(확인한 범위 안)")
    counted = bool(me and prev_docs and not same)
    if prev_docs and not same:
        m, t = prev_docs[0]
        a_prev = amount(t, kind)
        money = " · 금액 " + won(f"{a_prev:,}") if a_prev else ""
        lines.append(f"직전 같은 종류 공시 {day_of(m['date'])}(접수 {m['rcept_no']}){money}")
    if not counted:
        lines.append(f"최근 {YEARS_BACK}년 같은 종류 공시 {n_listed}건(정정 포함, 목록 기준)")
    r = ratio(cur, kind)
    rel = (cur or {}).get("회사와의관계", "")
    if kind == "채무보증" and same and SUBSIDIARY.search(rel) and r is not None and r < 5:
        routine = f"같은 {rel} 채무자 반복 보증 · 자기자본 대비 {r}%"
    return lines, routine


def corp_code_of(company, corp_codes):
    names = corp_codes.get("companies", corp_codes) if isinstance(corp_codes, dict) else {}
    alias = {"현대차": "현대자동차", "LS일렉트릭": "엘에스일렉트릭", "LS ELECTRIC": "엘에스일렉트릭", "한국타이어": "한국타이어앤테크놀로지",
             "포스코": "포스코", "LS": "LS"}
    for n in (company, alias.get(company)):
        if n and isinstance(names.get(n), dict) and names[n].get("corp_code"):
            return names[n]["corp_code"]
    return None


def enrich(cands, api_key, corp_codes, *, fetch_documents, get, budget=40):
    """Adds c['filing'] to DART candidates. Failures are recorded, never silently treated as 'nothing'."""
    used = 0
    for c in cands:
        m = re.search(r"rcpNo=(\d{14})", str(c.get("url") or ""))
        if not m or c.get("kind") != "단서":
            continue
        report = str(c.get("title") or "").split(" · ", 1)[-1]
        kind = filing_type(report)
        if not kind:
            continue
        rcept = m.group(1)
        info = {"type": kind, "rcept_no": rcept}
        if used >= budget:
            c["filing"] = {**info, "error": "원문 조회 예산 초과 — 미확인"}
            continue
        try:
            used += 1
            docs = fetch_documents(api_key, rcept)
            f = facts(report, docs)
        except Exception as e:
            c["filing"] = {**info, "error": f"원문 조회 실패({type(e).__name__}) — 미확인"}
            continue
        info.update(facts=f["facts"], related=f["related"])
        cur = f.get("raw") or {}
        corp = corp_code_of(c.get("company"), corp_codes)
        prev_docs, listed, err = [], 0, None
        if kind not in NO_PREVIOUS and corp:
            try:
                rows = previous_filings(api_key, corp, kind, dt.date(int(rcept[:4]), int(rcept[4:6]), int(rcept[6:8])), rcept, get=get)
                listed = len(rows)
                for meta in rows[:MAX_PREV_DOCS]:
                    if used >= budget:
                        break
                    used += 1
                    try:
                        prev_docs.append((meta, facts(meta["report"], fetch_documents(api_key, meta["rcept_no"])).get("raw") or {}))
                    except Exception:
                        continue
            except Exception as e:
                err = f"직전 공시 목록 조회 실패({type(e).__name__})"
        elif kind not in NO_PREVIOUS:
            err = "회사 고유번호 없음 — 직전 비교 못 함"
        lines, routine = compare(kind, cur, prev_docs, listed) if not err else ([], None)
        if err:
            lines = [err + " — 미확인"]
        info.update(compare=lines, routine=routine)
        c["filing"] = info
    return used


def load_corp_codes():
    try:
        return json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
