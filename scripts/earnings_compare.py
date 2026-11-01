"""공시 시즌 비교표: 출입처별 원가율·판관비율·영업이익률·직원 수 (OpenDART).

같은 보고기간의 전년 동기만 비교한다(3분기 vs 전년 3분기). 반기와 사업보고서, 1분기를 섞지 않는다.
- 재무: 단일회사 전체 재무제표(fnlttSinglAcntAll) · 연결(CFS) 우선, 없으면 별도(OFS) · 표준 계정ID 우선
- 직원: 직원 현황(empSttus) · 같은 보고서 종류의 전년 값과 비교

원칙
- 공개 공시 수치다. 비율 변화는 취재 질문이지 원인·단독이 아니다.
- 매출원가 계정이 없는 회사(지주사 '영업수익·영업비용' 방식 등)는 원가율을 만들지 않는다.
- 같은 계정에 서로 다른 값이 있으면 그 지표는 미확인으로 둔다.
- 미제출(OpenDART 013)·조회 실패·고유번호 미해결은 0이 아니라 상태로 남긴다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import governance_watch as gw  # noqa: E402  (BEATS, resolve_codes)

# 지분공시는 없지만 분기·반기·사업보고서를 내는 비상장 출입처(공모 회사채 발행사) — 실적 비교표에만 더한다.
# 11-01: HD현대오일뱅크(석유화학·정유 출입처, DART 고유번호 00105174 — dart_filings로 확인).
EXTRA = [("전력·에너지", ["HD현대오일뱅크"])]

API = "https://opendart.fss.or.kr/api"
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "digests" / "earnings_compare_latest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (seoul-reporting-radar)", "Accept": "application/json"}

REPORTS = {
    "11013": {"label": "1분기", "deadline": "05-15", "interim": True},
    "11012": {"label": "반기", "deadline": "08-14", "interim": True},
    "11014": {"label": "3분기", "deadline": "11-14", "interim": True},
    "11011": {"label": "사업보고서", "deadline": "03-31", "interim": False},
}
ACCOUNTS = {
    "revenue": ({"ifrs-full_Revenue", "ifrs_Revenue", "ifrs-full_RevenueFromContractsWithCustomers"},
                {"매출액", "수익(매출액)", "매출", "영업수익"}),
    "cost": ({"ifrs-full_CostOfSales", "ifrs_CostOfSales"}, {"매출원가"}),
    "sga": ({"dart_TotalSellingGeneralAdministrativeExpenses", "ifrs-full_SellingGeneralAndAdministrativeExpense"},
            {"판매비와관리비", "판매비와 관리비", "판매비 및 관리비", "판매비및관리비"}),
    "operating": ({"dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities",
                   "ifrs_ProfitLossFromOperatingActivities"}, {"영업이익", "영업이익(손실)", "영업손익"}),
}
# Flags are reading aids, not judgments.
FLAG = {"costRatio": 3.0, "sgaRatio": 2.0, "opMargin": 3.0, "employeesPct": 5.0}
LABEL = {"costRatio": "원가율", "sgaRatio": "판관비율", "opMargin": "영업이익률"}


DEBUG = False  # annotate-only runs keep raw empSttus rows for checking
EMP_FALLBACK = {"11014": lambda y: [(y, "11012")], "11013": lambda y: [(y - 1, "11011")]}


class TransientError(RuntimeError):
    pass


def target_period(now):
    """The report whose season is now: Oct–Dec → 3분기, Jan–Apr → 전년 사업보고서, May–Jul → 1분기, Aug–Sep → 반기."""
    m = now.month
    if m >= 10:
        return now.year, "11014"
    if m <= 4:
        return now.year - 1, "11011"
    if m <= 7:
        return now.year, "11013"
    return now.year, "11012"


def amount(value):
    text = str(value if value is not None else "").replace(",", "").strip()
    if not re.fullmatch(r"-?\d+", text):
        return None
    return int(text)


def call(endpoint, params, *, get=None, sleep=time.sleep, attempts=3):
    """Return ('ok', body) | ('no_data', None). Raises TransientError / RuntimeError."""
    if get is None:
        import requests
        get = requests.get
        errors = (requests.RequestException, ValueError)
    else:
        errors = (OSError, ValueError)
    last = None
    for attempt in range(attempts):
        try:
            r = get(f"{API}/{endpoint}", params=params, headers=HEADERS, timeout=30)
            if getattr(r, "status_code", 200) >= 500:
                raise TransientError(f"HTTP {r.status_code}")
            r.raise_for_status()
            body = r.json()
            status = str(body.get("status"))
            if status == "013":
                return "no_data", None
            if status in ("020", "800", "900"):
                raise TransientError(f"DART {status}: {body.get('message')}")
            if status != "000":
                raise RuntimeError(f"DART {status}: {body.get('message')}")
            return "ok", body
        except TransientError as e:
            last = e
        except errors as e:
            last = TransientError(type(e).__name__)
        if attempt + 1 < attempts:
            sleep(2 * (attempt + 1) ** 2)
    raise last


def classify(row):
    if row.get("sj_div") not in ("IS", "CIS"):
        return None
    if str(row.get("account_detail") or "-").strip() not in ("", "-"):
        return None
    aid = str(row.get("account_id") or "").strip()
    name = re.sub(r"\s+", " ", str(row.get("account_nm") or "")).strip()
    for metric, (ids, _) in ACCOUNTS.items():
        if aid in ids:
            return metric, "id"
    for metric, (_, names) in ACCOUNTS.items():
        if name in names:
            return metric, "name"
    return None


def pick(rows, metric, slot):
    """One unambiguous value: account-ID rows first, IS before CIS; conflicting values → None."""
    for how in ("id", "name"):
        for sj in ("IS", "CIS"):
            values = {amount(r.get(slot)) for r, m, h in rows if m == metric and h == how and r.get("sj_div") == sj}
            values.discard(None)
            if len(values) == 1:
                return next(iter(values))
            if len(values) > 1:
                return None
    return None


def ratios(v):
    rev = v.get("revenue")
    if not rev or rev <= 0:
        return {}
    out = {}
    if v.get("cost") is not None:
        out["costRatio"] = round(v["cost"] / rev * 100, 2)
    if v.get("sga") is not None:
        out["sgaRatio"] = round(v["sga"] / rev * 100, 2)
    if v.get("operating") is not None:
        out["opMargin"] = round(v["operating"] / rev * 100, 2)
    return out


def financials(body, report):
    """Quarter (3 months) and cumulative figures with the same-period prior year, from ONE filing."""
    interim = REPORTS[report]["interim"]
    rows = []
    for r in body.get("list") or []:
        if not isinstance(r, dict) or str(r.get("currency") or "KRW") not in ("KRW", "원"):
            continue
        c = classify(r)
        if c:
            rows.append((r, c[0], c[1]))
    slots = ({"quarter": ("thstrm_amount", "frmtrm_q_amount"), "cumulative": ("thstrm_add_amount", "frmtrm_add_amount")}
             if interim else {"annual": ("thstrm_amount", "frmtrm_amount")})
    result, receipts = {}, {str(r.get("rcept_no")) for r, _, _ in rows if r.get("rcept_no")}
    seen_names = sorted({re.sub(r"\s+", " ", str(r.get("account_nm") or "")).strip() for r in body.get("list") or []
                         if isinstance(r, dict) and r.get("sj_div") in ("IS", "CIS")
                         and re.search(r"판매|관리비|원가|매출|영업", str(r.get("account_nm") or ""))})
    # Some issuers (e.g. 현대위아) show 판매비 and 관리비 as two face lines with no total line.
    split = [(r, n, "name") for r in body.get("list") or [] if isinstance(r, dict)
             for n in [re.sub(r"\s+", "", str(r.get("account_nm") or ""))] if n in ("판매비", "관리비")
             and r.get("sj_div") in ("IS", "CIS") and str(r.get("account_detail") or "-").strip() in ("", "-")]
    derived = {}
    for key, (now_slot, prior_slot) in slots.items():
        cur = {m: pick(rows, m, now_slot) for m in ACCOUNTS}
        pri = {m: pick(rows, m, prior_slot) for m in ACCOUNTS}
        if not any(m == "sga" for _, m, _ in rows):
            for vals, slot in ((cur, now_slot), (pri, prior_slot)):
                sell, admin = pick(split, "판매비", slot), pick(split, "관리비", slot)
                if sell is not None and admin is not None:
                    vals["sga"] = sell + admin
                    derived["sga"] = "판매비+관리비(손익계산서 두 줄 합)"
        if cur.get("revenue") is None:
            continue
        rc, rp = ratios(cur), ratios(pri)
        result[key] = {"values": cur, "prior": pri, "ratios": rc, "priorRatios": rp,
                       "deltaPp": {k: round(rc[k] - rp[k], 2) for k in rc if k in rp}}
    if derived:
        result["derived"] = derived
    main = result.get("quarter") or result.get("annual")
    if main:
        missing = [m for m in ("cost", "sga", "operating") if main["values"].get(m) is None]
        if missing:
            result["unmatched"] = {"metrics": missing, "accountNames": seen_names[:20]}
    if interim and report != "11013" and "quarter" in result and "cumulative" in result:
        if result["quarter"]["values"]["revenue"] == result["cumulative"]["values"]["revenue"]:
            result["warning"] = "3개월·누적 매출이 같음 — 기간 구분 미확인"
    return result, sorted(receipts)


TOTAL_WORD = re.compile(r"\s*(합\s*계|총\s*계|계|전\s*체)\s*")
SUBTOTAL_WORD = re.compile(r".*소\s*계.*")


def headcount(body, *, explain=False):
    """Total employees from empSttus rows, avoiding double counts of total/subtotal rows.

    Order: grand-total row(s) by 사업부문 → per-gender total rows → detail rows without any 합계/소계 row."""
    rows = [r for r in (body.get("list") or []) if isinstance(r, dict)]
    def is_total(x):
        return bool(TOTAL_WORD.fullmatch(str(x or "")))
    def is_sub(x):
        return bool(SUBTOTAL_WORD.fullmatch(str(x or "")))
    picked = [r for r in rows if is_total(r.get("fo_bbm"))]
    method = "사업부문 합계 행"
    if picked:
        grand = [r for r in picked if is_total(r.get("sexdstn"))]
        picked = grand or picked
    else:
        picked = [r for r in rows if is_total(r.get("sexdstn")) and not is_sub(r.get("fo_bbm"))]
        method = "성별 합계 행"
        if not picked:
            picked = [r for r in rows if not any(is_total(r.get(k)) or is_sub(r.get(k)) for k in ("fo_bbm", "sexdstn"))]
            method = "세부 행 합산"
    values = [amount(r.get("sm")) for r in picked]
    stlm = next((str(r.get("stlm_dt")) for r in rows if r.get("stlm_dt")), None)
    total = sum(values) if values and all(v is not None for v in values) else None
    if explain:
        return total, stlm, {"method": method, "rowsUsed": len(picked), "rows": len(rows),
                             "raw": [[r.get("fo_bbm"), r.get("sexdstn"), r.get("sm")] for r in rows][:40]}
    return total, stlm


def receipt_day(rcp):
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})\d{6}", str(rcp or ""))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def tags_for(fin, emp):
    tags = []
    q = fin.get("quarter") or fin.get("annual") or {}
    for k, limit in (("costRatio", FLAG["costRatio"]), ("sgaRatio", FLAG["sgaRatio"]), ("opMargin", FLAG["opMargin"])):
        d = (q.get("deltaPp") or {}).get(k)
        if d is not None and abs(d) >= limit:
            tags.append(f"[{LABEL[k]} {d:+.1f}%p]")
    if emp and emp.get("changePct") is not None and abs(emp["changePct"]) >= FLAG["employeesPct"]:
        tags.append(f"[직원 {emp['changePct']:+.1f}%]")
    return tags


def company_record(name, team, code, year, report, *, get, sleep):
    rec = {"company": name, "team": team, "corpCode": code, "status": None}
    try:
        basis, body = "CFS", None
        for fs in ("CFS", "OFS"):
            st, b = call("fnlttSinglAcntAll.json", {"corp_code": code, "bsns_year": str(year), "reprt_code": report,
                                                    "fs_div": fs}, get=get, sleep=sleep)
            if st == "ok":
                basis, body = fs, b
                break
            sleep(0.15)
        if body is None:
            rec["status"] = "not_filed"
            return rec
        fin, receipts = financials(body, report)
        rec.update({"basis": "연결" if basis == "CFS" else "별도", "receipts": receipts,
                    "filedOn": receipt_day(receipts[0]) if receipts else None,
                    "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipts[0]}" if receipts else None})
        rec.update(fin)
        rec["status"] = "filed" if any(k in fin for k in ("quarter", "cumulative", "annual")) else "no_comparable_accounts"
    except (TransientError, RuntimeError) as e:
        rec.update({"status": "failed", "error": str(e)[:120]})
        return rec
    # Employees: same report of this year vs the same report a year earlier. 1분기·3분기 보고서는 직원 현황을
    #생략하는 회사가 많아, 없으면 직전 반기(3분기)·사업보고서(1분기)끼리 비교하고 그 기준을 적는다.
    emp = {}
    try:
        for emp_year, emp_report in [(year, report)] + EMP_FALLBACK.get(report, lambda y: [])(year):
            counts = {}
            for y in (emp_year, emp_year - 1):
                sleep(0.15)
                st, b = call("empSttus.json", {"corp_code": code, "bsns_year": str(y), "reprt_code": emp_report},
                             get=get, sleep=sleep)
                counts[y] = headcount(b, explain=True) if st == "ok" else (None, None, None)
            now_n, now_dt, how = counts[emp_year]
            pri_n, pri_dt, _ = counts[emp_year - 1]
            emp = {"report": f"{emp_year}년 {REPORTS[emp_report]['label']}", "count": now_n, "asOf": now_dt,
                   "priorCount": pri_n, "priorAsOf": pri_dt}
            if how:
                emp["method"] = how["method"]
                if DEBUG:
                    emp["raw"] = how["raw"]
            if emp_report != report:
                emp["note"] = f"{REPORTS[report]['label']} 보고서에 직원 현황이 없어 {emp['report']} 기준"
            if now_n is not None:
                break
        if emp.get("count") is None:
            emp["note"] = "직원 현황 없음 또는 합계 미확인"
        if emp.get("count") and emp.get("priorCount"):
            emp["changePct"] = round((emp["count"] - emp["priorCount"]) / emp["priorCount"] * 100, 1)
    except (TransientError, RuntimeError) as e:
        emp["error"] = str(e)[:120]
    rec["employees"] = emp
    rec["tags"] = tags_for(fin, emp)
    return rec


def build(key, *, year, report, now=None, get=None, sleep=time.sleep, registry=None, table=None):
    if get is None:
        import requests
        base_get = requests.get
    else:
        base_get = get
    def keyed(url, params, **kw):
        return base_get(url, params={"crtfc_key": key, **params}, **kw)
    now = now or dt.datetime.now(KST)
    companies, unresolved = [], []
    for team, names in list(gw.BEATS) + EXTRA:
        codes, missing = gw.resolve_codes(names, registry, table)
        codes.pop("_spellings", None)
        unresolved += missing
        for name in names:
            if name in codes:
                companies.append(company_record(name, team, codes[name], year, report, get=keyed, sleep=sleep))
    meta = REPORTS[report]
    deadline_year = year + 1 if report == "11011" else year
    counts = {s: sum(1 for c in companies if c["status"] == s) for s in ("filed", "not_filed", "failed", "no_comparable_accounts")}
    return {
        "generatedAt": now.isoformat(timespec="seconds"),
        "period": {"year": year, "report": report, "label": f"{year}년 {meta['label']}",
                   "deadline": f"{deadline_year}-{meta['deadline']}"},
        "source": "OpenDART 단일회사 전체 재무제표(fnlttSinglAcntAll)·직원 현황(empSttus)",
        "counts": counts, "unresolvedCompanies": unresolved,
        "status": "partial" if counts["failed"] or unresolved else "complete",
        "companies": companies,
        "rules": ["같은 보고기간의 전년 동기만 비교(3개월은 전년 같은 분기, 누적은 전년 같은 누적).",
                  "연결 우선·없으면 별도. 회사마다 기준이 다를 수 있어 회사 간 비율 비교는 참고용.",
                  "매출원가 계정이 없으면 원가율을 만들지 않는다(지주사 영업수익·영업비용 방식 등).",
                  "비율 변화는 취재 질문이지 원인·단독이 아니다. 미제출·조회 실패는 0이 아니다."],
        "flags": FLAG, "confirmedScoops": 0,
    }


def annotate(report):
    """Isolated verification: print compact GitHub annotations instead of writing operating files."""
    p = report["period"]
    print(f"::notice title=earnings-summary::{p['label']} · {json.dumps(report['counts'], ensure_ascii=False)} · "
          f"미해결 {report['unresolvedCompanies']}")
    lines = []
    for c in report["companies"]:
        q = c.get("quarter") or c.get("annual") or {}
        cu = c.get("cumulative") or {}
        r, d = q.get("ratios", {}), q.get("deltaPp", {})
        e = c.get("employees") or {}
        lines.append(f"{c['company']}|{c['status']}|{c.get('basis', '')}|rev={q.get('values', {}).get('revenue')}"
                     f"|cumRev={cu.get('values', {}).get('revenue')}|원가율={r.get('costRatio')}({d.get('costRatio')})"
                     f"|판관={r.get('sgaRatio')}({d.get('sgaRatio')})|OPM={r.get('opMargin')}({d.get('opMargin')})"
                     f"|직원={e.get('count')}/{e.get('priorCount')}@{e.get('asOf')}|{c.get('warning', '')}{c.get('error', '')}")
    for i in range(0, len(lines), 6):
        print("::notice title=earnings-%d::%s" % (i // 6 + 1, " ;; ".join(lines[i:i + 6])))
    odd = []
    for c in report["companies"]:
        e = c.get("employees") or {}
        if (e.get("changePct") is not None and (abs(e["changePct"]) >= 20 or e["changePct"] == 0)) or c.get("unmatched"):
            odd.append(f"{c['company']}|{e.get('report')}|{e.get('method')}|{e.get('count')}/{e.get('priorCount')}"
                       f"|raw={json.dumps(e.get('raw'), ensure_ascii=False)[:700]}|unmatched={json.dumps(c.get('unmatched'), ensure_ascii=False)[:400]}")
    for i, line in enumerate(odd[:8]):
        print(f"::warning title=earnings-check-{i + 1}::{line}")


def main():
    ap = argparse.ArgumentParser(description="공시 시즌 비교표")
    ap.add_argument("--year", type=int)
    ap.add_argument("--report", choices=sorted(REPORTS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--annotate-only", action="store_true", help="운영 파일을 쓰지 않고 요약만 출력")
    a = ap.parse_args()
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        sys.exit("DART_API_KEY 없음 — 이전 결과 유지")
    global DEBUG
    DEBUG = a.annotate_only
    year, report = target_period(dt.datetime.now(KST))
    year, report = a.year or year, a.report or report
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    try:
        import dart_watch
        table = dart_watch.load_corp_codes(key)
    except SystemExit:
        table = None
    result = build(key, year=year, report=report, registry=registry, table=table)
    attempted = len(result["companies"])
    if a.annotate_only:
        annotate(result)
        return
    if attempted and result["counts"]["failed"] * 2 > attempted:
        sys.exit(f"조회 실패 {result['counts']['failed']}/{attempted} — 이전 결과 유지(0 아님)")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(f"{result['period']['label']} · 제출 {result['counts']['filed']}/{attempted} · 실패 {result['counts']['failed']}")


if __name__ == "__main__":
    main()
