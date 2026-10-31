"""법제처 국가법령정보 공유서비스(공공데이터포털 15000115) — 출입 업종 행정규칙(고시·훈령·예규) 발령, 법령 공포, 법제처 법령해석례.

관보 입법예고(kr_official_watch.gazette)는 '예고'다. 여기서는 확정된 것 — 현행 목록에 새 일련번호로 올라온 행정규칙(제정·개정·폐지제정)과
법령, 새 법령해석례 — 를 잡는다. 훈령·예규·지침은 관보에 실리지 않는 경우가 많다.
- 요청: https://apis.data.go.kr/1170000/law/lawSearchList.do?serviceKey&target=admrul|law|expc&query&numOfRows&pageNo (XML)
- 탐침 10-31: 검색어가 없으면 오류, '*'는 행정규칙 24,248건(1쪽 1.8초)·법령은 시간 초과. 정렬(sort) 값은 먹지 않는다(발령일 순 아님).
  그래서 출입 업종 낱말별로 끝까지 받아 지난번에 없던 일련번호만 본다(개정되면 일련번호가 바뀐다).
- law.go.kr DRF 직접 호출은 등록 IP에서만 된다(탐침: '서버장비의 IP주소 및 도메인주소를 등록') — 이 창구는 공공데이터 키만.
결과는 kr-official 저장소의 lawRules 구역으로만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import datetime as dt
import re
import time
import xml.etree.ElementTree as ET
from urllib.parse import quote

BASE = "https://apis.data.go.kr/1170000/law/lawSearchList.do"
ROWS = 100
MAX_PAGES = 6
RECENT_DAYS = 45      # 새 일련번호라도 발령·공포·회신일이 이보다 오래되면 '새로'로 보지 않는다(검색어 추가·목록 정리)
KEEP_DAYS = 90
SEEN_MAX = 8000
QUERIES = {
    "admrul": ("자동차", "전기", "전력", "에너지", "철강", "금속", "광물", "화학", "배출", "온실가스", "관세", "원산지", "무역",
               "수소", "원자력", "배터리", "이차전지", "가스", "석유", "산업단지", "타이어", "공급망", "탄소"),
    "law": ("자동차", "전기", "전력", "에너지", "철강", "화학", "관세", "무역", "수소", "원자력", "탄소", "공급망", "산업단지"),
    "expc": ("전기", "전력", "자동차", "에너지", "화학", "관세", "가스", "원자력", "산업단지"),
}
FIELDS = {
    "admrul": {"id": "행정규칙일련번호", "title": "행정규칙명", "date": "발령일자", "org": "소관부처명", "change": "제개정구분명",
               "type": "행정규칙종류", "no": "발령번호", "effective": "시행일자"},
    "law": {"id": "법령일련번호", "title": "법령명한글", "date": "공포일자", "org": "소관부처명", "change": "제개정구분명",
            "type": "법령구분명", "no": "공포번호", "effective": "시행일자"},
    "expc": {"id": "법령해석례일련번호", "title": "안건명", "date": "회신일자", "org": "회신기관명", "asker": "질의기관명", "no": "안건번호"},
}
KIND = {"admrul": "행정규칙", "law": "법령", "expc": "법령해석례"}
# 출입 업종을 직접 맡는 부처(행정규칙·법령 B). 공정위·고용부는 하도급·산업안전처럼 '공통' 낱말일 때만 의미가 있어 여기 둔다.
CORE = re.compile(r"산업통상|산업부|기후에너지환경부|환경부|국토교통부|관세청|재정경제부|기획재정부|원자력안전위원회|공정거래위원회|고용노동부")
# '공통'(관세·무역·공장 등)만 걸린 규칙은 관세청 통관 사무 훈령처럼 일상이 많다(탐침 41: 45일 관련 62건 중 공통 34, 관세청 17) — 이 낱말일 때만 B
STRONG_COMMON = re.compile(r"원산지|덤핑|할당관세|공급망|첨단전략|핵심광물|탄소국경|무역구제|수출통제|전략물자|산업단지|중대재해|산업안전|"
                           r"온실가스|배출권|탄소중립")
# 관보 입법예고용 업종 낱말(kr_official_watch.TEAMS)에 없는 규칙 이름 낱말 — '전기설비기술기준'·'전기용품 안전기준'처럼 출입 업종 핵심 규칙이
# '전기사업·전력'에 안 걸린다(탐침 41 뒤 시험에서 확인)
EXTRA = {"전력·에너지": r"전기설비|전기안전|전기용품|전력기술|송배전|배전|변압기|전선|케이블|발전소|발전사업|전기저장",
         "자동차": r"배터리|이차전지|충전시설|충전기|자동차관리|차량",
         "공통": r"온실가스|배출권|탄소중립|원산지|덤핑|할당관세|핵심광물|전략물자|수출통제"}
RETRY_ERRORS = ("ConnectionError", "ConnectTimeout", "ReadTimeout", "ChunkedEncodingError")


def norm_date(v):
    d = re.sub(r"\D", "", v or "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else ""


def human_url(kind, rec):
    """사람이 여는 law.go.kr 주소. API가 주는 상세링크는 법제처 DRF(OC·등록 IP 필요)라 쓰지 않는다."""
    if kind == "admrul":
        return f"https://www.law.go.kr/행정규칙/{quote(rec['title'])}"
    if kind == "law":
        return f"https://www.law.go.kr/법령/{quote(rec['title'])}"
    return f"https://www.law.go.kr/LSW/expcInfoP.do?expcSeq={rec['seq']}"


def parse(kind, xml_text):
    root = ET.fromstring(xml_text)
    code = root.findtext(".//resultCode")
    if code not in (None, "00", "0"):
        raise RuntimeError(f"결과코드 {code} {root.findtext('.//resultMsg') or ''}".strip())
    total = root.findtext("totalCnt")
    if total is None:
        raise RuntimeError("totalCnt 없음(오류 응답)")
    f = FIELDS[kind]
    out = []
    for item in root:
        if not len(item):
            continue
        rec = {k: (item.findtext(tag) or "").strip() for k, tag in f.items()}
        if not rec["id"]:
            continue
        rec["seq"] = rec.pop("id")
        out.append(rec)
    return int(total), out


def law_teams(title, teams_of):
    teams = list(teams_of(title))
    for team, rx in EXTRA.items():
        if team not in teams and re.search(rx, title or ""):
            teams.append(team)
    return teams


def tier_of(kind, rec, teams):
    beat = bool(set(teams) - {"공통"}) or bool(STRONG_COMMON.search(rec.get("title") or ""))
    if kind == "expc":
        return "B" if beat else "C"
    if kind == "law":
        # 법령 공포는 관보·보도자료가 먼저다. 제정·전부개정만 B
        return "B" if beat and CORE.search(rec.get("org") or "") and re.search(r"^제정|전부개정", rec.get("change") or "") else "C"
    return "B" if beat and CORE.search(rec.get("org") or "") else "C"


def fetch(get, kind, q, page, key, sleep):
    """한 번 실패(연결·시간 초과)는 2초 뒤 다시(탐침 41: 3,153건 중 2질의 연결 시간 초과)."""
    for attempt in (1, 2):
        try:
            r = get(BASE, params={"serviceKey": key, "target": kind, "query": q, "numOfRows": ROWS, "pageNo": page}, timeout=40)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            return parse(kind, r.content)
        except Exception as e:  # noqa: BLE001
            if attempt == 2 or type(e).__name__ not in RETRY_ERRORS:
                raise
            sleep(2)


def collect(prev, now, key, *, get, teams_of, ministries, sleep=time.sleep, deadline=None):
    """prev: 지난 doc['lawRules'] 구역(dict) 또는 None. 돌려줌: (구역, 점검 한 줄)."""
    stamp = now.isoformat(timespec="seconds")
    baseline = not prev
    prev = prev or {}
    seen = set(prev.get("seen") or [])
    items = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    since = (now.date() - dt.timedelta(days=RECENT_DAYS)).isoformat()
    errors, capped, returned, now_ids, skipped = [], [], 0, set(), []
    for kind, queries in QUERIES.items():
        for q in queries:
            if deadline is not None and time.monotonic() > deadline:
                skipped.append(f"{KIND[kind]} '{q}'")
                continue
            page, total = 1, None
            while page <= MAX_PAGES:
                try:
                    total, recs = fetch(get, kind, q, page, key, sleep)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{KIND[kind]} '{q}' {page}쪽 {str(e)[:60] if isinstance(e, RuntimeError) else type(e).__name__}")
                    break
                returned += len(recs)
                for rec in recs:
                    iid = f"{kind}:{rec['seq']}"
                    now_ids.add(iid)
                    if iid in seen or iid in items:
                        continue
                    date = norm_date(rec.get("date"))
                    text = rec["title"]
                    org = rec.get("org") or ""
                    teams = law_teams(text, teams_of)
                    if not teams or (kind != "expc" and not ministries.search(org)):
                        continue
                    if not date or date < since:
                        continue  # 오래된 규칙이 새 검색어로 처음 보인 것 — 새 변화 아님
                    items[iid] = {"id": iid, "kind": KIND[kind], "title": text, "date": date, "org": org,
                                  "change": rec.get("change"), "type": rec.get("type"), "no": rec.get("no"),
                                  "effective": norm_date(rec.get("effective")), "asker": rec.get("asker"), "teams": teams,
                                  "tier": tier_of(kind, rec, teams), "url": human_url(kind, rec), "query": q,
                                  "firstSeen": stamp, "isNew": not baseline}
                if page * ROWS >= total or not recs:
                    break
                page += 1
                sleep(0.3)
            if total is not None and page > MAX_PAGES:
                capped.append(f"{KIND[kind]} '{q}' {total}건 중 {MAX_PAGES * ROWS}건")
            sleep(0.3)
    seen |= now_ids
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    kept = sorted((x for x in items.values() if str(x.get("firstSeen")) >= keep), key=lambda x: (x["date"], x["id"]), reverse=True)
    for x in kept:
        x["isNew"] = x["firstSeen"] == stamp and not baseline
    notes = errors[:3] + capped[:2] + ([f"시간 상한으로 {len(skipped)}개 질의 건너뜀"] if skipped else [])
    status = "failed" if errors and not returned else "partial" if errors or capped or skipped else "ok"
    check = {"source": "법제처 행정규칙·법령·해석례", "status": status, "returned": returned, "kept": len(kept),
             **({"error": "; ".join(notes)[:300]} if notes else {})}
    section = {"checkedAt": stamp, "baselineSince": prev.get("baselineSince") or stamp, "items": kept[:300],
               "seen": sorted(seen)[-SEEN_MAX:]}
    return section, check
