"""미국 소송·ITC 337조 감시: 출입처가 당사자인 미국 연방법원 사건(CourtListener)과 출입처 이름이 나오는 ITC 337조 고시.

- CourtListener v4 검색(RECAP 사건 목록): 회사 영문명으로 최근 사건을 찾고, 당사자(party) 목록에 출입처가 있을 때만 남긴다.
  본문에 이름만 나오는 다른 회사 사건은 버린다.
- 분류: 국제무역법원(CIT)·연방순회항소법원(CAFC) 사건, 특허·계약·반독점·증권·노동 등은 먼저 보여 주고,
  소비자 제조물책임·개인 고용 소송·위조품 단속(Schedule A)은 '일상'으로 접는다.
- ITC 337조: 미국 관보에서 ITC 고시 중 'Certain …' 337조 사건(제소 접수·조사 개시·판정)을 찾아 본문을 한 번 읽고
  출입처 영문명이 나오면 남긴다(문서번호로 캐시).
- 결과는 기자 전용 저장소(us-litigation)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import trade_remedy_watch as trw  # noqa: E402  (BEAT_NAMES, named_companies, text_lines, get_text)

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "us_litigation/v1"
CL_API = "https://www.courtlistener.com/api/rest/v4/search/"
CL_SITE = "https://www.courtlistener.com"
WINDOW_DAYS = 45
KEEP_DAYS = 120
MAX_PAGES = 3
ITC_BODY_BUDGET = 40

# (출입처, 검색 문구, 당사자 판정 정규식). 계열사·약어 오인을 막기 위해 당사자 이름으로 다시 확인한다.
COMPANIES = [
    ("현대차", '"Hyundai Motor"', r"Hyundai Motor|Genesis Motor"),
    ("기아", '"Kia America"', r"\bKia\b"),
    ("기아", '"Kia Corporation"', r"\bKia\b"),
    ("기아", '"Kia Georgia"', r"\bKia\b"),
    ("현대모비스", '"Hyundai Mobis"', r"Hyundai Mobis|\bMobis\b"),
    ("현대모비스", '"Mobis Alabama"', r"\bMobis\b"),
    ("현대위아", '"Hyundai WIA"', r"Hyundai WIA"),
    ("HL만도", '"HL Mando"', r"\bMando\b"),
    ("한국타이어", '"Hankook Tire"', r"Hankook"),
    ("넥센타이어", '"Nexen Tire"', r"Nexen Tire"),
    ("금호타이어", '"Kumho Tire"', r"Kumho"),
    ("포스코", '"POSCO"', r"\bPOSCO\b(?!\s*(?:International|Future|E&C|DX))"),
    ("현대제철", '"Hyundai Steel"', r"Hyundai Steel"),
    ("세아제강", '"SeAH Steel"', r"SeAH"),
    ("동국제강·동국씨엠", '"Dongkuk"', r"Dongkuk"),
    ("고려아연", '"Korea Zinc"', r"Korea Zinc"),
    ("HD현대일렉트릭", '"Hyundai Power Transformers"', r"Hyundai Power Transformers|HD Hyundai Electric|Hyundai Electric"),
    ("HD현대일렉트릭", '"HD Hyundai Electric"', r"Hyundai Power Transformers|HD Hyundai Electric|Hyundai Electric"),
    ("LS일렉트릭", '"LS Electric"', r"\bLS Electric"),
    ("LS전선", '"LS Cable"', r"\bLS Cable|LS GreenLink"),
    ("LS전선", '"LS GreenLink"', r"\bLS Cable|LS GreenLink"),
    ("대한전선", '"Taihan"', r"Taihan"),
    ("두산에너빌리티", '"Doosan Enerbility"', r"Doosan"),
    ("한화솔루션", '"Hanwha Q Cells"', r"Hanwha|Q ?Cells"),
    ("한화솔루션", '"Qcells"', r"Hanwha|Q ?Cells"),
    ("OCI", '"Mission Solar"', r"Mission Solar|\bOCI\b"),
    ("GS칼텍스", '"GS Caltex"', r"GS Caltex"),
    ("KG모빌리티", '"KG Mobility"', r"KG Mobility|SsangYong"),
    ("효성중공업(관련)", '"Hyosung HICO"', r"Hyosung"),
    ("일진전기(관련)", '"Iljin Electric"', r"Iljin"),
]

# Nature-of-suit code → (분류, 우선순위). Lower is shown first; 3 = 일상(접힘).
NOS = [
    (r"^83[05]", "특허", 1), (r"^840", "상표", 2), (r"^410", "반독점", 1), (r"^85[0-9]", "증권", 1),
    (r"^89[03]", "환경·기타 법령", 1), (r"^470", "부패·RICO", 1), (r"^19[0-6]|^11[0-9]", "계약", 1),
    (r"^7[0-9]{2}", "노동", 2), (r"^89[0-9]", "기타 법령", 2), (r"^3[0-9]{2}", "제조물책임·상해", 3),
    (r"^44[0-9]", "고용 차별(개인)", 3), (r"^4[0-9]{2}", "기타 민사", 2),
]
CONSUMER_CAUSE = re.compile(r"Magnuson|Warranty|Product Liabil|Personal Inj|Motor Vehicle|Lemon", re.I)


def classify(x):
    court = (x.get("court_id") or "").lower()
    case = x.get("caseName") or ""
    nos = (x.get("suitNature") or "").strip()
    cause = x.get("cause") or ""
    if court == "cit":
        return "국제무역법원(무역구제 소송)", 0
    if court == "cafc":
        return "연방순회항소법원", 0
    if re.search(r"^In re\b|Multidistrict|MDL", case, re.I):
        return "병합·집단 소송", 1
    if re.search(r"Schedule A|Unincorporated Associations", case, re.I):
        return "위조품 단속(상표)", 3
    for rx, name, pri in NOS:
        if re.match(rx, nos):
            return name, pri
    if CONSUMER_CAUSE.search(cause):
        return "소비자·제조물책임", 3
    return "분류 없음", 2


def cl_search(query, since, token, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    headers = {"User-Agent": "seoul-reporting-radar (github.com/shhong9173-art)", "Accept": "application/json",
               "Authorization": f"Token {token}"}
    rows, url, params = [], CL_API, {"q": query, "type": "r", "order_by": "dateFiled desc", "filed_after": since}
    for _ in range(MAX_PAGES):
        try:
            r = get(url, params=params, headers=headers, timeout=40)
        except Exception as e:
            return rows, type(e).__name__
        finally:
            sleep(1.0)
        if r.status_code == 401:
            return rows, "HTTP 401 토큰 거부"
        if r.status_code == 429:
            return rows, "HTTP 429 호출 한도"
        if r.status_code != 200:
            return rows, f"HTTP {r.status_code}"
        try:
            body = r.json()
        except ValueError:
            return rows, "JSON 아님"
        rows += body.get("results") or []
        url, params = body.get("next"), None
        if not url:
            break
    return rows, None


def litigation(token, now, previous, *, get=None, sleep=time.sleep):
    since = (now - dt.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    prev = {x["id"]: x for x in (previous or {}).get("cases", []) if isinstance(x, dict) and x.get("id")}
    found, checks = {}, []
    for company, query, party_rx in COMPANIES:
        rows, err = cl_search(query, since, token, get=get, sleep=sleep)
        if err:
            checks.append({"source": f"CourtListener {query}", "company": company, "status": "failed", "error": err, "returned": len(rows)})
            if "401" in err:
                break  # a refused token fails every query the same way
            continue
        own = 0
        for x in rows:
            parties = [p for p in (x.get("party") or []) if isinstance(p, str)]
            matched = [p for p in parties if re.search(party_rx, p, re.I)]
            if not matched:
                continue  # the company is only mentioned in a filing of someone else's case
            did = f"cl:{x.get('docket_id')}"
            own += 1
            item = found.get(did)
            if item:
                item["beat"] = sorted(set(item["beat"]) | {company})
                item["matchedParties"] = sorted(set(item["matchedParties"]) | set(matched))[:6]
                continue
            category, pri = classify(x)
            case = x.get("caseName") or ""
            plaintiff = bool(re.match(rf"^\s*(?:{party_rx})", case, re.I))
            found[did] = {
                "id": did, "beat": [company], "caseName": case, "court": x.get("court"), "courtId": x.get("court_id"),
                "docketNumber": x.get("docketNumber"), "dateFiled": x.get("dateFiled"), "dateTerminated": x.get("dateTerminated"),
                "suitNature": x.get("suitNature") or "", "cause": x.get("cause") or "", "category": category, "priority": pri,
                "role": "원고" if plaintiff else "피고·기타 당사자", "matchedParties": matched[:6], "partyCount": len(parties),
                "url": CL_SITE + (x.get("docket_absolute_url") or ""),
                "firstSeen": prev.get(did, {}).get("firstSeen") or now.isoformat(timespec="seconds"),
            }
        checks.append({"source": f"CourtListener {query}", "company": company, "status": "ok", "returned": len(rows), "own": own})
    return found, checks


def is_337(title):
    """Section 337 notices ('Certain X; Notice of …'), not AD/CVD notices that also start with 'Certain … From <country>'."""
    if re.search(r"Section 337|Receipt of Complaint", title, re.I):
        return True
    return bool(re.match(r"Certain .*;", title)) and not re.search(r"\bFrom\b", title)


def itc_337(now, previous, *, get=None, sleep=time.sleep):
    """ITC notices of the last WINDOW_DAYS that are Section 337 matters, kept when the body names a beat company."""
    since = (now - dt.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    params = [("conditions[agencies][]", "international-trade-commission"), ("conditions[publication_date][gte]", since),
              ("order", "newest"), ("per_page", "200")]
    for f in ("title", "publication_date", "html_url", "document_number", "raw_text_url", "type"):
        params.append(("fields[]", f))
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(trw.FR_API, params=params, headers={"User-Agent": trw.UA, "Accept": "application/json"}, timeout=40)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}", 0
        data = r.json()
    except Exception as e:
        return [], type(e).__name__, 0
    prev = {x["id"]: x for x in (previous or {}).get("itc", []) if isinstance(x, dict) and x.get("id")}
    seen = set((previous or {}).get("itcChecked") or [])
    rows, budget, checked = [], ITC_BODY_BUDGET, []
    for x in data.get("results") or []:
        title = x.get("title") or ""
        if not is_337(title):
            continue
        did = f"fr:{x.get('document_number')}"
        checked.append(did)
        if did in prev:
            rows.append(prev[did])
            continue
        if did in seen or budget <= 0 or not x.get("raw_text_url"):
            continue
        budget -= 1
        body, err = trw.get_text(x["raw_text_url"], get=get, headers={"User-Agent": trw.UA, "Accept": "text/plain,text/html"})
        sleep(0.5)
        if body is None:
            checked.pop()  # retry next time
            continue
        named = trw.named_companies(trw.text_lines(body))
        if named:
            rows.append({"id": did, "date": x.get("publication_date"), "title": title, "url": x.get("html_url"),
                         "stage": "제소 접수" if re.search(r"Receipt of Complaint", title, re.I) else
                                  ("조사 개시" if re.search(r"Institution", title, re.I) else
                                   ("최종 판정" if re.search(r"Final", title, re.I) else
                                    ("예비 판정" if re.search(r"Initial Determination", title, re.I) else "절차 고시"))),
                         "named": named, "firstSeen": now.isoformat(timespec="seconds")})
    return rows, None, sorted(set(checked) | seen)[-600:]


def run(token, *, now, previous=None, get=None, sleep=time.sleep):
    stamp = now.isoformat(timespec="seconds")
    had_state = bool(previous)
    found, checks = litigation(token, now, previous, get=get, sleep=sleep)
    itc, ierr, checked = itc_337(now, previous, get=get, sleep=sleep)
    checks.append({"source": "미국 관보 ITC 337조", "status": "failed" if ierr else "ok", "returned": len(itc), **({"error": ierr} if ierr else {})})
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    prev_cases = {x["id"]: x for x in (previous or {}).get("cases", []) if isinstance(x, dict) and x.get("id")}
    # cases outside this run's window (or from failed queries) stay until KEEP_DAYS
    for did, x in prev_cases.items():
        if did not in found and str(x.get("dateFiled") or "") >= keep_from:
            found[did] = x
    cases = sorted(found.values(), key=lambda x: (x["priority"], -int(re.sub(r"\D", "", x.get("dateFiled") or "0") or 0)))
    for x in cases:
        x["isNew"] = had_state and x["id"] not in prev_cases
    prev_itc = {x["id"] for x in (previous or {}).get("itc", []) if isinstance(x, dict)}
    if ierr:
        itc = list((previous or {}).get("itc") or [])
    for x in itc:
        x["isNew"] = had_state and x["id"] not in prev_itc
    failed = [c for c in checks if c["status"] != "ok"]
    return {"schema": SCHEMA, "generatedAt": stamp, "windowDays": WINDOW_DAYS, "status": "partial" if failed else "complete",
            "checks": checks, "cases": cases, "itc": itc, "itcChecked": checked,
            "rules": ["당사자 목록에 출입처(미국 법인 포함)가 있는 사건만. 서류에 이름만 나온 남의 사건은 제외.",
                      "소장 접수는 주장일 뿐 사실 확정이 아니다. 청구 내용·금액은 소장 원문(PACER)으로 확인하고 회사 입장을 듣는다.",
                      "CourtListener에 아직 안 올라온 사건이 있을 수 있다. 0건은 소송 없음이 아니다.",
                      "ITC 337조 고시의 회사명은 제소인·피제소인·제3자일 수 있다. 원문에서 역할을 확인한다.",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="미국 소송·ITC 337조 감시(기자 전용 저장소로)").parse_args()
    now = dt.datetime.now(KST)
    cl_token = os.environ.get("COURTLISTENER_TOKEN", "").strip()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not cl_token:
        sys.exit("COURTLISTENER_TOKEN 미설정 — 실행하지 않음(0건 아님)")
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("us-litigation", token)
        except private_store.StoreError as e:
            print(f"::warning title=us-litigation-state::이전 상태 조회 실패({e}) — 신규 표시는 이번 실행 기준")
    doc = run(cl_token, now=now, previous=previous)
    ok = sum(1 for c in doc["checks"] if c["status"] == "ok")
    shown = sum(1 for x in doc["cases"] if x["priority"] < 3)
    errors = sorted({c.get("error") for c in doc["checks"] if c.get("error")})
    print(f"::notice title=us-litigation::질의 정상 {ok}/{len(doc['checks'])} · 출입처 당사자 사건 {len(doc['cases'])}건(우선 {shown}, "
          f"신규 {sum(1 for x in doc['cases'] if x['isNew'])}) · ITC 337조 출입처 이름 {len(doc['itc'])}건"
          f"{' · 오류 ' + ', '.join(errors) if errors else ''}")
    if not token:
        print("::warning title=us-litigation-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if ok == 0:
        sys.exit("모든 질의 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("us-litigation", doc, token)
    print(f"::notice title=us-litigation-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=us-litigation-token::토큰 거부 또는 배포 전 — {private_store.token_shape(private_store.normalize_token(token))}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
