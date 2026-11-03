"""타사 공시 속 출입처 — 출입처가 아닌 회사의 DART 공시에 출입처가 거래상대·계약상대로 적힌 것(기자 전용 저장소 dart-counterparty).

- 왜: 「LG화학 대산 BPA 국도화학에 매각」(10-08·10-22 경쟁지 [단독])은 출입처 공시가 아니라 상대 회사(국도화학)의 '영업양수 결정
  (종속회사의 주요경영사항)'에 나왔다(10-26 접수, 「1. 양수영업 ㈜LG화학 대산 BPA 생산 및 판매 사업일체 … 3. 양수가액(원) 78,437,000,000」).
  출입처 공시 감시(dart_beat_monitor)는 이런 타사 공시를 보지 않는다.
- 원천: OpenDART 공시검색(list.json, 시장 전체 — 주요사항보고 B·거래소공시 I, 최근 2일)에서 종류 낱말(양수·양도·취득·처분·합병·분할·
  영업·공급계약·생산중단·투자판단)로 거른 뒤 원문(document.xml) 앞부분을 읽는다. 11-03 탐침 144~146: 10월 한 달 거른 공시 중
  에스트래픽 [기재정정] 영업양수결정의 「거래상대방 회사명(성명) 엘에스일렉트릭 주식회사 … 총 양수대금 74,536,000,000원」,
  국도화학 위 공시를 잡았다(2일치 60건은 0건 — 드물다).
- 판정: 양수·양도·취득·처분·합병·분할·영업 공시는 원문 앞 4,000자(서식 본문)에 출입처 이름이 나오면, 공급계약은 '계약상대' 칸
  (dart_contract_tables) 또는 그 낱말 뒤 200자에 나오면, 생산중단은 앞 4,000자 어디든. 출입처 자신의 공시는 뺀다(출입처 공시 감시 몫).
  같은 그룹 계열사의 공시(현대글로비스↔현대차 등)는 그룹 내 거래라 참고(C).
- 등급: 자산·영업·지분 거래 상대 A, 공급계약 해지 A, 공급계약 500억원 이상 A·그 미만 B, 생산중단(출입처 언급)·투자판단 B.
- 첫 실행은 기준선. 결과는 기자 전용 저장소로만. 공개 로그는 건수만. 조회 실패는 0건이 아니라 미확인.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import os
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "dart_counterparty/v1"
LIST_API = "https://opendart.fss.or.kr/api/list.json"
DOC_API = "https://opendart.fss.or.kr/api/document.xml"
UA = {"User-Agent": "seoul-reporting-radar (newsroom research; counterparty filings)"}
DAYS = 2
MAX_PAGES = 20         # 유형별 최대 쪽(100건씩)
DOC_BUDGET = 80        # 한 실행에 여는 원문 수
PAUSE = 0.6
KEEP_DAYS = 120
SEEN_DAYS = 7
HEAD = 4000            # 서식 본문(앞부분)
BIG_CONTRACT = 50_000_000_000

# 출입처 한국어 법인 이름(어디서든 볼 때) — 계열사가 붙는 이름은 뒤를 막는다
BEAT_KO = [
    ("현대차", r"현대자동차(?!써비스|정비|판매|부품|증권|해상|그룹)"), ("기아", r"기아\s*(?:주식회사|㈜|\(주\))|기아자동차|(?:주식회사|㈜|\(주\))\s*기아(?![가-힣])"),
    ("현대모비스", r"현대모비스"), ("현대위아", r"현대위아"), ("HL만도", r"(?:에이치엘|HL)\s?만도"), ("한국GM", r"한국지엠(?!디)"),
    ("KG모빌리티", r"(?:케이지|KG)\s?모빌리티"), ("르노코리아", r"르노코리아"), ("한국타이어", r"한국타이어앤테크놀로지"), ("넥센타이어", r"넥센타이어"),
    ("금호타이어", r"금호타이어"), ("포스코홀딩스", r"포스코홀딩스|POSCO\s?(?:홀딩스|Holdings)"), ("포스코", r"포스코(?![가-힣A-Za-z])|\bPOSCO\b(?!\s?(?:홀딩스|Holdings|퓨처엠|Future|인터내셔널|International|이앤씨|E&C|DX))"), ("현대제철", r"현대제철"),
    ("KG스틸", r"(?:케이지|KG)\s?스틸"), ("세아제강", r"세아제강(?!지주)"), ("세아홀딩스", r"세아홀딩스"), ("동국제강", r"동국제강"), ("동국씨엠", r"동국씨엠"),
    ("고려아연", r"고려아연"), ("영풍", r"(?:주식회사\s*|㈜\s*|\(주\)\s*)영풍(?![가-힣])|영풍\s*(?:주식회사|㈜|\(주\))"),
    ("HD현대일렉트릭", r"(?:HD|에이치디)\s?현대일렉트릭"), ("LS일렉트릭", r"(?:LS|엘에스)\s?(?:일렉트릭|ELECTRIC)"), ("대한전선", r"대한전선"),
    ("LS전선", r"(?:LS|엘에스)\s?전선"), ("LS MnM", r"(?:LS|엘에스)\s?(?:MnM|엠앤엠)"), ("두산에너빌리티", r"두산에너빌리티"),
    ("GS칼텍스", r"(?:GS|지에스)\s?칼텍스"), ("한화솔루션", r"한화솔루션"), ("OCI", r"오씨아이(?!홀딩스)|\bOCI(?!\s?홀딩스|\s?Holdings)\b"),
    ("태광", r"태광산업"), ("동성케미칼", r"동성케미칼"), ("DL케미칼", r"(?:DL|디엘)\s?케미칼"), ("LG화학", r"(?:LG|엘지)\s?화학"),
    ("롯데케미칼", r"롯데케미칼"), ("금호석유화학", r"금호석유화학"), ("S-OIL", r"에쓰-?오일|S-?OIL"),
    ("SK이노베이션", r"(?:SK|에스케이)\s?이노베이션"), ("HD현대오일뱅크", r"현대오일뱅크"),
]
# DART 회사명은 영문 섞인 이름(S-Oil·POSCO홀딩스·LS ELECTRIC)이라 대소문자를 가리지 않는다(11-03 탐침 147: 출입처 자신의 실적 공시가 걸렸다)
BEAT_RX = [(k, re.compile(v, re.I)) for k, v in BEAT_KO]
# 계약상대 칸에선 '기아'처럼 짧은 이름도 그 회사다
LOOSE = {"기아": re.compile(r"기아(?![가-힣])")}
# 같은 그룹(계열사가 출입처와 거래한 공시는 그룹 내 거래 — 참고)
GROUP = {"현대차": r"^(?:현대|기아|에이치엘|HL)", "기아": r"^(?:현대|기아)", "현대모비스": r"^(?:현대|기아)", "현대위아": r"^(?:현대|기아)",
         "현대제철": r"^(?:현대|기아)", "포스코": r"^포스코", "포스코홀딩스": r"^포스코", "LS일렉트릭": r"^(?:LS|엘에스)", "LS전선": r"^(?:LS|엘에스)",
         "LS MnM": r"^(?:LS|엘에스)", "GS칼텍스": r"^(?:GS|지에스)", "한화솔루션": r"^한화", "LG화학": r"^(?:LG|엘지)", "롯데케미칼": r"^롯데",
         "SK이노베이션": r"^(?:SK|에스케이)", "HD현대일렉트릭": r"^(?:HD|에이치디)", "HD현대오일뱅크": r"^(?:HD|에이치디)", "두산에너빌리티": r"^두산",
         "세아제강": r"^세아", "세아홀딩스": r"^세아", "동국제강": r"^동국", "동국씨엠": r"^동국", "고려아연": r"^(?:고려|영풍)", "영풍": r"^(?:영풍|고려아연)",
         "KG스틸": r"^(?:KG|케이지)", "KG모빌리티": r"^(?:KG|케이지)", "금호석유화학": r"^금호", "OCI": r"^(?:OCI|오씨아이)", "DL케미칼": r"^(?:DL|디엘)",
         "태광": r"^(?:태광|흥국)"}
KIND = re.compile(r"단일판매|공급계약|생산중단|양수|양도|취득|처분|합병|분할|영업정지|투자판단")
DEAL = re.compile(r"양수|양도|취득|처분|합병|분할")
LABEL = re.compile(r"계약\s*상대|거래\s*상대|상대방|양수인|양도인|매수인|매도인|발행회사|고객사|납품처|발주처")
SKIP_KIND = re.compile(r"전환사채|신주인수권|교환사채|자기주식|자기사채|기업설명회|투자유의|조회공시|임원|최대주주등소유주식|실적|배당|주주총회|감사보고서")


def beats_in(text, loose=False):
    out = []
    for k, rx in BEAT_RX:
        if (rx.search(text or "") or (loose and k in LOOSE and LOOSE[k].search(text or ""))) and k not in out:
            out.append(k)
    return out


def plain(markup):
    t = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", markup or "")
    t = re.sub(r"\.xforms[^{]*\{[^}]*\}", " ", t)   # 서식 CSS가 태그 밖에 남는 공시가 있다
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


def decode(b):
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def documents(get, key, rcept):
    r = get(DOC_API, params={"crtfc_key": key, "rcept_no": rcept}, headers=UA, timeout=40)
    data = r.content
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise RuntimeError("원문 ZIP 아님")
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist()[:40]:
            if info.filename.lower().endswith((".xml", ".htm", ".html")) and info.file_size < 20_000_000:
                out.append(decode(z.read(info)))
    return out


def judge(filing, docs):
    """(출입처 목록, 역할, 맥락, 금액) — 해당 없으면 None."""
    from dart_contract_tables import extract_contract_terms
    name = filing["report_nm"]
    text = " ".join(plain(d) for d in docs)
    head = text[:HEAD]
    if "공급계약" in name or "단일판매" in name:
        terms = extract_contract_terms(docs).get("fields", {})
        party = str(terms.get("counterparty") or "")
        found = beats_in(party, loose=True)
        ctx = party
        if not found and not party:   # 계약상대 칸을 읽었는데 출입처가 아니면 거기서 끝(회사 소개의 '주요 고객' 같은 이름은 안 센다)
            for m in LABEL.finditer(head):
                hit = beats_in(head[m.end(): m.end() + 200], loose=True)
                if hit:
                    found, ctx = hit, head[m.start(): m.end() + 160]
                    break
        if not found:
            return None
        digits = re.sub(r"[^\d]", "", str(terms.get("contract_amount") or ""))
        amount = int(digits) if digits else None
        subject = terms.get("contract_subject") or ""
        return found, "공급계약 해지 상대" if "해지" in name else "공급계약 상대", (f"계약상대 {party}" if party else ctx)[:200] + (f" · 계약명 {subject}" if subject else ""), amount
    found = beats_in(head)
    if not found:
        return None
    m = next(rx.search(head) for k, rx in BEAT_RX if k == found[0])
    ctx = head[max(0, m.start() - 120): m.end() + 140]
    role = "생산중단 공시에 이름" if "생산중단" in name else "투자판단 공시에 이름" if "투자판단" in name else "자산·영업·지분 거래 상대"
    amt = re.search(r"(?:양수|양도|취득|처분)\s*(?:가액|금액|대금)[^0-9]{0,30}([\d,]{6,})", head)
    return found, role, ctx, int(amt.group(1).replace(",", "")) if amt else None


def tier_of(role, amount, same_group):
    if same_group:
        return "C"
    if role in ("자산·영업·지분 거래 상대", "공급계약 해지 상대"):
        return "A"
    if role == "공급계약 상대":
        return "A" if (amount or 0) >= BIG_CONTRACT else "B"
    return "B"


def eok(n):
    if not n:
        return ""
    jo, rest = divmod(int(n) // 100_000_000, 10_000)
    return f"약 {jo}조{rest}억원" if jo else f"약 {rest:,}억원"


def list_filings(get, sleep, key, now):
    bgn = (now.date() - dt.timedelta(days=DAYS - 1)).strftime("%Y%m%d")
    end = now.date().strftime("%Y%m%d")
    rows, errors = [], []
    for ty in ("B", "I"):
        page = 1
        while True:
            try:
                r = get(LIST_API, params={"crtfc_key": key, "bgn_de": bgn, "end_de": end, "pblntf_ty": ty, "page_no": page, "page_count": 100},
                        headers=UA, timeout=40).json()
            except Exception as e:  # noqa: BLE001
                errors.append(f"{ty}{page}:{type(e).__name__}")
                break
            if r.get("status") == "013":   # 조회된 데이터 없음 — 정상 0건
                break
            if r.get("status") != "000":
                errors.append(f"{ty}:{r.get('status')}")
                break
            rows += r.get("list") or []
            if page >= int(r.get("total_page") or 1):
                break
            if page >= MAX_PAGES:
                errors.append(f"{ty}: {MAX_PAGES}쪽 상한")
                break
            page += 1
            sleep(PAUSE)
    return rows, errors


def run(now, previous=None, *, key=None, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    key = key if key is not None else os.environ.get("DART_API_KEY", "").strip()
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    if not key:
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "failed",
                "checks": [{"source": "OpenDART 공시검색", "status": "not_configured", "error": "DART_API_KEY 미설정"}]}
    seen_from = (now - dt.timedelta(days=SEEN_DAYS)).strftime("%Y%m%d")
    seen = {k: v for k, v in (prev.get("seen") or {}).items() if str(v) >= seen_from}
    known = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)]
    first = not prev.get("baselineAt")
    rows, errors = list_filings(get, sleep, key, now)
    cand = [x for x in rows if KIND.search(x.get("report_nm") or "") and not SKIP_KIND.search(x.get("report_nm") or "")
            and not beats_in(x.get("corp_name") or "") and x.get("rcept_no") not in seen]
    cand.sort(key=lambda x: (0 if DEAL.search(x["report_nm"]) else 1, x["rcept_no"]), reverse=False)
    opened, doc_errors, pending = 0, 0, max(0, len(cand) - DOC_BUDGET)
    for x in cand[:DOC_BUDGET]:
        sleep(PAUSE)
        opened += 1
        try:
            docs = documents(get, key, x["rcept_no"])
        except Exception:  # noqa: BLE001
            doc_errors += 1
            continue   # 다음 실행에 다시(본 것으로 치지 않음)
        seen[x["rcept_no"]] = x.get("rcept_dt") or now.strftime("%Y%m%d")
        res = judge(x, docs)
        if not res:
            continue
        found, role, ctx, amount = res
        beat = found[0]
        same = bool(GROUP.get(beat) and re.search(GROUP[beat], re.sub(r"^(?:주식회사|㈜|\(주\))\s*", "", x["corp_name"])))
        tier = tier_of(role, amount, same)
        fid = f"dcp:{x['rcept_no']}"
        rec = {"id": fid, "company": beat, "others": found[1:], "filer": x["corp_name"], "report": re.sub(r"\s+", " ", x["report_nm"]).strip(),
               "rceptNo": x["rcept_no"], "date": x.get("rcept_dt"), "role": role, "context": re.sub(r"\s+", " ", ctx)[:260],
               "amount": amount, "tier": tier, "sameGroup": same, "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={x['rcept_no']}",
               "firstSeen": stamp, **({"baseline": True} if first else {})}
        known[fid] = rec
        if not first and tier in ("A", "B"):
            events.append({"id": fid, "tier": tier, "kind": f"타사 공시 · {role}", "company": beat, "filer": x["corp_name"], "report": rec["report"],
                           "detectedAt": stamp, "url": rec["url"],
                           "text": (f"{x['corp_name']} 공시 「{rec['report']}」({x.get('rcept_dt')}) — {beat}이(가) {role}"
                                    + (f" · 금액 {amount:,}원({eok(amount)})" if amount else "") + f" · 원문 「{rec['context'][:200]}」"
                                    + " · 상대 회사 공시(출입처 공시 아님) — 거래 조건·시점은 원문과 출입처 확인")})
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    failed_list = bool(errors) and not rows
    status = "failed" if failed_list else "partial" if (errors or doc_errors or pending) else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "baselineAt": prev.get("baselineAt") or stamp,
            "checks": [{"source": "OpenDART 공시검색(시장 전체 B·I)", "status": "failed" if failed_list else "partial" if errors else "ok",
                        "returned": len(rows), **({"error": "; ".join(errors[:4])} if errors else {})},
                       {"source": "공시 원문", "status": "partial" if (doc_errors or pending) else "ok", "returned": opened,
                        **({"error": f"원문 읽기 실패 {doc_errors}건"} if doc_errors else {}),
                        **({"pending": pending} if pending else {})}],
            "counts": {"listed": len(rows), "candidates": len(cand), "opened": opened, "matched": sum(1 for x in known.values() if x["firstSeen"] == stamp)},
            "seen": seen,
            "items": sorted((x for x in known.values() if str(x.get("firstSeen")) >= keep), key=lambda x: str(x.get("date")), reverse=True)[:300],
            "events": sorted((e for e in events if str(e.get("detectedAt")) >= keep), key=lambda e: e["detectedAt"], reverse=True)[:200],
            "rules": ["출입처가 아닌 회사의 공시(양수·양도·취득·처분·합병·분할·영업·공급계약·생산중단)에 출입처가 거래상대·계약상대로 적힌 것. 출입처 자신의 공시는 출입처 공시 감시 몫이라 뺀다.",
                      "자산·영업·지분 거래 상대와 공급계약 해지는 A, 공급계약은 500억원 이상 A·그 밖 B, 생산중단·투자판단 공시에 이름이 나온 것 B, 같은 그룹 계열사 공시는 참고(C).",
                      "상대 회사 공시는 그 회사의 발표다. 출입처 쪽 조건(매각 가격·시점·사유)은 출입처 공시·회사 확인 전 미확인. 이름만 겹친 다른 회사일 수 있어 원문 확인.",
                      "첫 실행은 기준선. 원문 읽기 실패·한 실행 상한(60건)을 넘은 공시는 다음 실행에 다시 본다(미확인)."]}


def main():
    import private_store
    now = dt.datetime.now(KST).replace(microsecond=0)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("dart-counterparty", token)
        except private_store.StoreError as e:
            print(f"::warning title=dart-counterparty-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
        if private_store.late_scheduled_duplicate(previous, now, hours=2):
            return
    doc = run(now, previous)
    c = doc.get("counts") or {}
    new = [e for e in doc.get("events") or [] if e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=dart-counterparty::상태 {doc['status']} · 목록 {c.get('listed', 0)} · 후보 {c.get('candidates', 0)} · 원문 {c.get('opened', 0)}"
          f" · 출입처 거래상대 {c.get('matched', 0)} · 이번 새 이벤트 {len(new)}")
    if not token:
        print("::warning title=dart-counterparty-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("OpenDART 공시검색 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("dart-counterparty", doc, token)
    print(f"::notice title=dart-counterparty-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
