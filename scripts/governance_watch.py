"""지분·지배구조 변동 감시 (OpenDART 지분공시 종합정보).

출입처별로 최근 N일의
  - 주식등의 대량보유상황보고(5% 보고, majorstock.json)
  - 임원·주요주주 특정증권등 소유상황보고(elestock.json)
를 모아 digests/governance_latest.json 에 쓴다.

원칙
- 공개 공시다. 지분 변동 자체는 단독이 아니다. 배경(경영권·승계·매각·담보)과 회사 설명을 따로 확인한다.
- 조회 실패는 0건이 아니다. 회사별 상태(checked/no_data/failed)를 남긴다.
- 기관투자자의 약식·단순투자 보고는 'routine'으로 표시해 뒤로 미룬다(삭제하지 않는다).
- 보고자의 관계(오너 일가·계열사 등)는 원문에 적힌 것만 쓰고 추정하지 않는다.
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

API = "https://opendart.fss.or.kr/api"
KST = dt.timezone(dt.timedelta(hours=9))
OUT = ROOT / "digests" / "governance_latest.json"

# Direct beats that file stake reports (listed companies + listed parents).
# Names are matched to DART corp codes from dart_corp_codes.json, then corpCode.xml.
BEATS = [
    ("자동차", ["현대자동차", "기아", "현대모비스", "현대위아", "HL만도", "KG모빌리티", "한국타이어앤테크놀로지",
              "넥센타이어", "금호타이어"]),
    ("철강·비철", ["포스코홀딩스", "현대제철", "KG스틸", "세아홀딩스", "세아제강", "동국제강", "동국씨엠", "고려아연", "영풍"]),
    ("전력·에너지", ["HD현대일렉트릭", "엘에스일렉트릭", "대한전선", "LS", "두산에너빌리티", "GS", "S-Oil", "SK이노베이션"]),
    ("화학·소재", ["한화솔루션", "OCI", "OCI홀딩스", "태광", "동성케미칼", "LG화학", "롯데케미칼", "금호석유화학"]),
]
INSTITUTION = re.compile(r"국민연금|자산운용|투자신탁|투자자문|증권|은행|보험|공제회|BlackRock|블랙록|Vanguard|뱅가드|"
                         r"Capital|Investment|Asset|Fund|Trust|Norges|GIC|템플턴|피델리티|Fidelity", re.I)
CONTROL = re.compile(r"경영(권|참가|참여)|보유목적|목적\s*변경|최대주주|특수관계|특별관계자|담보|처분|증여|상속|합병|분할|"
                     r"계약|교환사채|공개매수")
# Boilerplate reasons removed before CONTROL is applied ("단순추가취득/처분" is not a control event).
PLAIN_REASON = re.compile(r"단순\s*(추가)?\s*취득\s*(/|및|·)?\s*(처분)?|단순\s*처분|장내\s*(매수|매도)")
TOP_EXEC = re.compile(r"회장|부회장|사장|대표이사")
GROUP_MIN = 5  # same company, same day, this many insider reports → one grouped line
# Beat name → other exact spellings tried only against DART's corpCode table (never fuzzy).
DART_SPELLINGS = {"동성케미칼": ["동성케미컬"], "S-Oil": ["에쓰-오일", "에쓰오일"]}


class TransientError(RuntimeError):
    pass


def num(value):
    """'1,234' / '-0.50' / '－' → float or None."""
    text = str(value if value is not None else "").replace(",", "").replace("－", "-").strip()
    if text in ("", "-", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def day(value):
    text = str(value or "").strip()
    m = re.fullmatch(r"(\d{4})[-.]?(\d{2})[-.]?(\d{2})", text[:10])
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def fetch(endpoint, key, corp_code, *, get=None, sleep=time.sleep, attempts=3):
    """Return (status, rows). status: checked | no_data. Raises TransientError on failure."""
    if get is None:
        import requests
        get = requests.get
        errors = (requests.RequestException, ValueError)
    else:
        errors = (OSError, ValueError)
    last = None
    for attempt in range(attempts):
        try:
            r = get(f"{API}/{endpoint}", params={"crtfc_key": key, "corp_code": corp_code}, timeout=30)
            if getattr(r, "status_code", 200) >= 500:
                raise TransientError(f"HTTP {r.status_code}")
            r.raise_for_status()
            body = r.json()
            status = str(body.get("status"))
            if status == "013":
                return "no_data", []
            if status in ("020", "800", "900"):
                raise TransientError(f"DART {status}: {body.get('message')}")
            if status != "000":
                raise RuntimeError(f"DART {status}: {body.get('message')}")
            rows = body.get("list") or []
            return "checked", [x for x in rows if isinstance(x, dict)]
        except TransientError as e:
            last = e
        except errors as e:
            last = TransientError(type(e).__name__)
        if attempt + 1 < attempts:
            sleep(2 * (attempt + 1) ** 2)
    raise last


def stake_item(company, team, row, start):
    date = day(row.get("rcept_dt"))
    if not date or date < start:
        return None
    reporter = str(row.get("repror") or "").strip()
    change = num(row.get("stkrt_irds"))
    reason = re.sub(r"\s+", " ", str(row.get("report_resn") or "")).strip()
    kind = str(row.get("report_tp") or "").strip()
    institution = bool(INSTITUTION.search(reporter))
    tags = []
    # ±1%p is the legal trigger for a regular 5% report, so it only flags non-institution holders.
    if change is not None and abs(change) >= 1 and not institution:
        tags.append(f"[지분율 {change:+.2f}%p]")
    words = list(dict.fromkeys(re.sub(r"\s+", "", m.group(0)) for m in CONTROL.finditer(PLAIN_REASON.sub(" ", reason))))
    if words:
        tags.append(f"[사유: {'·'.join(words[:3])}]")  # the filing's own words, not an interpretation
    routine = institution or "약식" in kind
    return {
        "company": company, "team": team, "kind": "대량보유(5%)", "date": date,
        "receiptNo": str(row.get("rcept_no") or ""), "reporter": reporter, "reportType": kind,
        "shares": num(row.get("stkqy")), "sharesChange": num(row.get("stkqy_irds")),
        "ratio": num(row.get("stkrt")), "ratioChange": change, "reason": reason[:200],
        "tags": tags, "routine": routine and not tags,
        "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row.get('rcept_no')}" if row.get("rcept_no") else None,
    }


def insider_item(company, team, row, start):
    date = day(row.get("rcept_dt"))
    if not date or date < start:
        return None
    reporter = str(row.get("repror") or "").strip()
    role = " ".join(str(row.get(k) or "").strip() for k in ("isu_exctv_rgist_at", "isu_exctv_ofcps", "isu_main_shrholdr")
                    if str(row.get(k) or "").strip() not in ("", "-"))
    change_rate = num(row.get("sp_stock_lmp_irds_rate"))
    change_cnt = num(row.get("sp_stock_lmp_irds_cnt"))
    moved = bool(change_cnt)
    tags = []
    if INSTITUTION.search(reporter):
        # Institutions as 10%+ holders: same bar as 5% reports.
        if change_rate is not None and abs(change_rate) >= 1:
            tags.append(f"[지분율 {change_rate:+.2f}%p]")
    else:
        if change_rate is not None and abs(change_rate) >= 0.1:
            tags.append(f"[지분율 {change_rate:+.2f}%p]")
        if ("주요주주" in role or "10%" in role) and change_rate is not None and abs(change_rate) >= 0.01:
            tags.append("[주요주주]")
        if moved and TOP_EXEC.search(role):
            tags.append("[최고경영진]")
    return {
        "company": company, "team": team, "kind": "임원·주요주주", "date": date,
        "receiptNo": str(row.get("rcept_no") or ""), "reporter": reporter, "role": role[:80],
        "shares": num(row.get("sp_stock_lmp_cnt")), "sharesChange": change_cnt,
        "ratio": num(row.get("sp_stock_lmp_rate")), "ratioChange": change_rate,
        "tags": tags, "routine": not tags,
        "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row.get('rcept_no')}" if row.get("rcept_no") else None,
    }


def resolve_codes(names, registry, table=None):
    """Exact names only: the committed beat registry first, then DART corpCode.xml (unique match)."""
    out, missing = {}, []
    companies = (registry or {}).get("companies", {})
    for name in names:
        entry = companies.get(name)
        if entry and re.fullmatch(r"\d{8}", str(entry.get("corp_code") or "")):
            out[name] = entry["corp_code"]
            continue
        rows = (table or {}).get(name) or []
        spelled = name
        for alt in DART_SPELLINGS.get(name, []):
            if not rows and (table or {}).get(alt):
                rows, spelled = table[alt], alt
        listed = {r[0] for r in rows if len(r) > 1 and r[1]}
        codes = listed or {r[0] for r in rows}
        if len(codes) == 1:
            out[name] = next(iter(codes))
            if spelled != name:
                out.setdefault("_spellings", {})[name] = spelled
        else:
            missing.append(name)
    return out, missing


def group_insiders(items):
    """Same company + same day + GROUP_MIN or more insider reports → one grouped line.

    Members are kept (routine unless tagged on their own); only a summary is added."""
    buckets = {}
    for it in items:
        if it["kind"] == "임원·주요주주":
            buckets.setdefault((it["company"], it["date"]), []).append(it)
    groups = []
    for (company, date), members in buckets.items():
        if len(members) < GROUP_MIN:
            continue
        net = sum(m["sharesChange"] or 0 for m in members)
        buyers = sum(1 for m in members if (m["sharesChange"] or 0) > 0)
        sellers = sum(1 for m in members if (m["sharesChange"] or 0) < 0)
        groups.append({
            "company": company, "team": members[0]["team"], "kind": "임원 집단 보고", "date": date,
            "receiptNo": None, "groupKey": f"insider-group|{company}|{date}",
            "reporter": f"임원·주요주주 {len(members)}명", "role": "",
            "sharesChange": net, "ratioChange": None, "buyers": buyers, "sellers": sellers,
            "members": [m["receiptNo"] for m in members],
            "reason": f"매수 {buyers}명·매도 {sellers}명 · 순증감 {net:+,.0f}주(보고서별 합계, 취득 경위는 원문 확인)",
            "tags": [f"[같은 날 {len(members)}명 보고]"], "routine": False,
            "url": members[0]["url"],
        })
    return groups


def build(key, *, now=None, days=30, get=None, sleep=time.sleep, registry=None, table=None):
    now = now or dt.datetime.now(KST)
    start = (now - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    checks, items = [], []
    missing_all, spellings = [], {}
    for team, names in BEATS:
        codes, missing = resolve_codes(names, registry, table)
        spellings.update(codes.pop("_spellings", {}))
        missing_all += missing
        for name, code in codes.items():
            for endpoint, builder in (("majorstock.json", stake_item), ("elestock.json", insider_item)):
                try:
                    status, rows = fetch(endpoint, key, code, get=get, sleep=sleep)
                except (TransientError, RuntimeError) as e:
                    checks.append({"company": name, "endpoint": endpoint, "status": "failed", "error": str(e)[:120]})
                    continue
                kept = [it for it in (builder(name, team, r, start) for r in rows) if it]
                checks.append({"company": name, "endpoint": endpoint, "status": status,
                               "rowsReturned": len(rows), "rowsInWindow": len(kept)})
                items += kept
                sleep(0.15)
    items += group_insiders(items)
    items.sort(key=lambda x: x["date"], reverse=True)
    items.sort(key=lambda x: x["routine"])
    failed = [c for c in checks if c["status"] == "failed"]
    return {
        "generatedAt": now.isoformat(timespec="seconds"), "windowStart": start, "windowDays": days,
        "source": "OpenDART 지분공시 종합정보(majorstock·elestock)",
        "status": "partial" if failed or missing_all else "complete",
        "checks": checks, "failedCount": len(failed), "unresolvedCompanies": missing_all,
        "dartSpellings": spellings,
        "count": len(items), "items": items,
        "rules": ["공개 공시이며 지분 변동 자체는 단독이 아니다.",
                  "조회 실패·미해결 회사는 0건이 아니라 미확인이다.",
                  "routine은 기관 약식·단순 보고 등 뒤로 미룬 것이지 삭제가 아니다.",
                  "임원 집단 보고는 같은 날 보고서의 합계일 뿐, 취득 경위(장내매수·주식보상 등)는 원문 확인 전 미확인이다.",
                  "보고자 관계(오너 일가·계열)는 원문에 적힌 것만 쓴다."],
        "confirmedScoops": 0,
    }


def main():
    ap = argparse.ArgumentParser(description="지분·지배구조 변동 감시")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        sys.exit("DART_API_KEY 없음 — 이전 결과 유지")
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    table = None
    try:
        import dart_watch
        table = dart_watch.load_corp_codes(key)
    except SystemExit:
        table = None  # registry-only; unresolved names are reported, not zero
    report = build(key, days=a.days, registry=registry, table=table)
    attempted = len(report["checks"])
    if attempted and report["failedCount"] * 2 > attempted:
        sys.exit(f"지분공시 조회 실패 {report['failedCount']}/{attempted} — 이전 결과 유지(0건 아님)")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(out)
    flagged = [x for x in report["items"] if not x["routine"]]
    print(f"지분 변동 {report['count']}건(주목 {len(flagged)}) · 조회 실패 {report['failedCount']} · 미해결 {len(report['unresolvedCompanies'])}")


if __name__ == "__main__":
    main()
