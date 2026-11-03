"""지방의회 회의록 — 공장 지역 지방의회 본회의·상임위 회의록에 출입처 이름이 나온 대목(기자 전용 저장소 council-minutes).

- 왜: 경쟁지 [단독] 30일 역추적에서 못 잡은 「기아 '신차 2000대' 불법 야적 논란」(10-20, 공장시설로 허가받고 야적장으로)처럼 인허가·민원·
  환경·세금 문제는 시·군·도의회 질의에 먼저 나온다.
- 원천: 국회도서관 지방의정포털(CLIK) 회의록 Open API — `https://clik.nanet.go.kr/openapi/minutes.do`(목록: searchKeyword·sort=MTG_DE/DESC,
  상세: docid → MTR_SJ 안건·MINTS_HTML 본문). 17개 광역·175개 기초의회. 하루 1,000번·한 번 100건 한도. robots.txt `Allow: /`(11-03 탐침 144~145).
- 인증키는 포털 회원 로그인 뒤 발급(clik.nanet.go.kr/potal/guide/openApi.do) — 기자가 발급해 GitHub 비밀값 CLIK_API_KEY로 넣는다.
  키가 없으면 '미설정'(0건 아님)으로 저장한다. 응답 칸 이름은 포털 안내 문서 기준이고 키를 넣은 첫 실행에서 실제 응답으로 확인한다.
- 출입처 이름으로 최신 회의록 20건씩 찾고(회의일 내림차순), 새 회의록만 상세를 열어 이름 앞뒤 150자를 2곳까지 남긴다(한 실행 30건).
  인허가·불법·위반·오염·민원·특혜·감면·보조금·증설·이전·폐쇄·매각·사고 낱말이 그 대목에 있으면 A, 없으면 C(화면에서 접음).
- 첫 실행은 기준선. 회의록은 회의 뒤 몇 주 늦게 올라온다 — 회의일과 공개일이 다르다. 의원 질의는 주장이다(집행부 답변·회사 확인).
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "council_minutes/v1"
API = "https://clik.nanet.go.kr/openapi/minutes.do"
UA = {"User-Agent": "seoul-reporting-radar (newsroom research; local council minutes)"}
PAUSE = 1.0
LIST_COUNT = 20
DETAIL_BUDGET = 30
KEEP_DAYS = 180
# (검색어, 출입처, 대목에서 그 회사를 가리키는지 볼 정규식)
TERMS = [
    ("현대자동차", "현대차", r"현대자동차|현대차(?!증권)"), ("기아자동차", "기아", r"기아(?:자동차|차|\s?오토랜드|\s?화성|\s?광명|\s?광주)"),
    ("기아 오토랜드", "기아", r"기아\s?오토랜드"), ("현대모비스", "현대모비스", r"현대모비스"), ("현대위아", "현대위아", r"현대위아"),
    ("HL만도", "HL만도", r"(?:HL|에이치엘)\s?만도|만도"), ("한국지엠", "한국GM", r"한국\s?(?:지엠|GM)"), ("KG모빌리티", "KG모빌리티", r"(?:KG|케이지)\s?모빌리티"),
    ("르노코리아", "르노코리아", r"르노코리아"), ("한국타이어", "한국타이어", r"한국타이어"), ("넥센타이어", "넥센타이어", r"넥센타이어"),
    ("금호타이어", "금호타이어", r"금호타이어"), ("포스코", "포스코", r"포스코(?!퓨처엠|인터내셔널|이앤씨|DX|케미칼)"), ("현대제철", "현대제철", r"현대제철"),
    ("KG스틸", "KG스틸", r"(?:KG|케이지)\s?스틸"), ("세아제강", "세아제강", r"세아제강"), ("동국제강", "동국제강", r"동국제강"),
    ("동국씨엠", "동국씨엠", r"동국씨엠"), ("고려아연", "고려아연", r"고려아연"), ("석포제련소", "영풍", r"석포제련소|영풍"),
    ("현대일렉트릭", "HD현대일렉트릭", r"현대일렉트릭"), ("LS일렉트릭", "LS일렉트릭", r"(?:LS|엘에스)\s?일렉트릭"), ("대한전선", "대한전선", r"대한전선"),
    ("LS전선", "LS전선", r"(?:LS|엘에스)\s?전선"), ("두산에너빌리티", "두산에너빌리티", r"두산에너빌리티"), ("GS칼텍스", "GS칼텍스", r"(?:GS|지에스)\s?칼텍스"),
    ("한화솔루션", "한화솔루션", r"한화솔루션|한화큐셀"), ("OCI", "OCI", r"(?<![A-Za-z])OCI(?!\s?홀딩스)|오씨아이"), ("태광산업", "태광", r"태광산업"),
    ("LG화학", "LG화학", r"(?:LG|엘지)\s?화학"), ("롯데케미칼", "롯데케미칼", r"롯데케미칼"), ("금호석유화학", "금호석유화학", r"금호석유화학|금호석화"),
    ("에쓰오일", "S-OIL", r"에쓰\s?-?\s?오일|S-?OIL"), ("SK이노베이션", "SK이노베이션", r"(?:SK|에스케이)\s?이노베이션"), ("현대오일뱅크", "HD현대오일뱅크", r"현대오일뱅크"),
]
A_WORDS = re.compile(r"인허가|허가|불법|위반|행정처분|오염|유출|악취|민원|특혜|감면|보조금|증설|신설|이전|폐쇄|철수|매각|사고|사망|야적|지방세|체납")


def tidy(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def rows_of(body):
    """목록 응답 → [{DOCID, RASMBLY_NM, MTGNM, MTG_DE, …}] (LIST 안 ROW로 감싼 모양과 바로 든 모양 둘 다)."""
    lst = body.get("LIST") or []
    if isinstance(lst, dict):
        lst = [lst]
    out = []
    for x in lst:
        r = x.get("ROW") if isinstance(x, dict) and "ROW" in x else x
        if isinstance(r, list):
            out += [y for y in r if isinstance(y, dict)]
        elif isinstance(r, dict):
            out.append(r)
    return out


def snippets(text, rx, n=2, width=150):
    out = []
    for m in rx.finditer(text or ""):
        s = text[max(0, m.start() - width): m.end() + width].strip()
        if not any(s[:40] in o for o in out):
            out.append(s)
        if len(out) >= n:
            break
    return out


def run(now, previous=None, *, key=None, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    key = key if key is not None else os.environ.get("CLIK_API_KEY", "").strip()
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    if not key:
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "not_configured",
                "checks": [{"source": "국회도서관 지방의회 회의록(CLIK)", "status": "unset",
                            "error": "CLIK_API_KEY 미설정 — clik.nanet.go.kr 로그인 뒤 인증키 신청, GitHub 비밀값으로"}],
                "items": prev.get("items") or [], "events": prev.get("events") or []}
    seen = dict(prev.get("seen") or {})
    known = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)]
    first = not prev.get("baselineAt")
    errors, fresh, fatal = [], [], False
    for i, (term, comp, pat) in enumerate(TERMS):
        if i:
            sleep(PAUSE)
        try:
            r = get(API, params={"key": key, "type": "json", "displayType": "list", "startCount": 0, "listCount": LIST_COUNT,
                                 "searchType": "ALL", "searchKeyword": term, "sort": "MTG_DE/DESC"}, headers=UA, timeout=30)
            body = r.json()
        except Exception as e:  # noqa: BLE001
            errors.append(f"{term}:{type(e).__name__}")
            continue
        code = str(body.get("RESULT_CODE") or "")
        if code and code != "SUCCESS":
            errors.append(f"{term}:{code} {str(body.get('RESULT_MESSAGE') or '')[:30]}")
            if code in ("ERROR01", "ERROR09", "ERROR10"):   # 키 오류·하루 한도 — 더 묻지 않는다
                fatal = True
                break
            continue
        for row in rows_of(body):
            did = str(row.get("DOCID") or "")
            if not did or did in seen or any(f[0] == did for f in fresh):
                continue
            fresh.append((did, term, comp, pat, row))
    if first:   # 기준선: 지금 목록의 회의록 번호만 기억
        for did, _t, _c, _p, row in fresh:
            seen[did] = str(row.get("MTG_DE") or "")
    opened = 0
    pending = 0 if first else max(0, len(fresh) - DETAIL_BUDGET)   # 한 실행 상한을 넘은 것은 다음 실행에(본 것으로 치지 않음)
    for did, term, comp, pat, row in ([] if first else fresh[:DETAIL_BUDGET]):
        sleep(PAUSE)
        opened += 1
        try:
            d = get(API, params={"key": key, "type": "json", "displayType": "detail", "docid": did}, headers=UA, timeout=40).json()
            rr = rows_of(d)
            det = rr[0] if rr else d
            text = tidy(det.get("MINTS_HTML"))
        except Exception as e:  # noqa: BLE001
            errors.append(f"상세 {did}:{type(e).__name__}")
            continue   # 다음 실행에 다시
        seen[did] = str(row.get("MTG_DE") or "")
        rx = re.compile(pat)
        snips = snippets(text, rx)
        if not snips:
            continue
        tier = "A" if any(A_WORDS.search(s) for s in snips) else "C"
        rid = f"clik:{did}"
        rec = {"id": rid, "company": comp, "term": term, "council": row.get("RASMBLY_NM"), "meeting": row.get("MTGNM"), "date": row.get("MTG_DE"),
               "session": row.get("RASMBLY_SESN"), "agenda": tidy(det.get("MTR_SJ"))[:200], "snippets": [s[:320] for s in snips], "tier": tier,
               "docid": did, "url": tidy(det.get("ORGINL_FILE_URL")) or "", "firstSeen": stamp}
        known[rid] = rec
        if tier == "A":
            events.append({"id": rid, "tier": "A", "kind": "지방의회 회의록", "company": comp, "council": rec["council"], "detectedAt": stamp,
                           "url": rec["url"] or None,
                           "text": (f"{rec['council']} {rec['meeting'] or ''}({rec['date']}) 회의록 · {comp} 대목 「{snips[0][:240]}」"
                                    + (f" · 안건 {rec['agenda'][:80]}" if rec["agenda"] else "") + f" · 회의록 번호 {did}(국회도서관 지방의정포털)"
                                    + " · 의원 질의는 주장 — 집행부 답변·회사 확인")})
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    status = "failed" if fatal or (errors and len(errors) >= len(TERMS)) else "partial" if errors else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "baselineAt": prev.get("baselineAt") or stamp,
            "checks": [{"source": "국회도서관 지방의회 회의록(CLIK)", "status": "failed" if status == "failed" else "partial" if errors else "ok",
                        "returned": len(fresh), "opened": opened, **({"pending": pending} if pending else {}),
                        **({"error": "; ".join(errors[:4])} if errors else {}),
                        **({"note": "첫 실행 기준선(새 회의록 번호만 기억)"} if first else {})}],
            "seen": dict(sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:3000]),
            "items": sorted((x for x in known.values() if str(x.get("firstSeen")) >= keep), key=lambda x: str(x.get("date")), reverse=True)[:300],
            "events": sorted((e for e in events if str(e.get("detectedAt")) >= keep), key=lambda e: e["detectedAt"], reverse=True)[:200],
            "rules": ["국회도서관 지방의정포털 회의록에서 출입처 이름으로 찾은 새 회의록의 대목(이름 앞뒤 150자). 의원 질의·발언은 주장이다 — 집행부 답변·회사 확인.",
                      "그 대목에 인허가·불법·위반·오염·민원·특혜·감면·보조금·증설·이전·폐쇄·매각·사고·야적·체납 낱말이 있으면 A, 없으면 참고(C).",
                      "회의록은 회의 뒤 몇 주 늦게 올라온다 — 회의일과 공개일이 다르다. 첫 실행은 기준선, 조회 실패·한도 초과는 미확인."]}


def main():
    import private_store
    now = dt.datetime.now(KST).replace(microsecond=0)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("council-minutes", token)
        except private_store.StoreError as e:
            print(f"::warning title=council-minutes-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
        if private_store.late_scheduled_duplicate(previous, now):
            return
    doc = run(now, previous)
    c = doc["checks"][0]
    new = [e for e in doc.get("events") or [] if e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=council-minutes::상태 {doc['status']} · 새 회의록 {c.get('returned', 0)} · 상세 {c.get('opened', 0)} · 이번 새 이벤트 {len(new)}"
          + (f" · {c['error'][:80]}" if c.get("error") and doc["status"] == "not_configured" else ""))
    if not token:
        print("::warning title=council-minutes-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("지방의회 회의록 조회 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("council-minutes", doc, token)
    print(f"::notice title=council-minutes-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
