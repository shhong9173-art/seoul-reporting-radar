"""유럽·미국 상표 출원 원천(Signa, 11-09) — 유럽은 EUIPO 운영 검색이 구독 승인 대기(403)로 막힌 동안 대신, 미국(USPTO)은 이것만으로 읽는다
(USPTO 직접 API는 ID.me 인증 실패, 11-01).

- Signa는 EUIPO 등 상표청 자료를 매일 맞추는 2차 원천이다(약관 3.1: 불완전·부정확할 수 있음). 기사 전 EUIPO eSearch 원문 확인.
- 검색: GET /v1/trademarks?owner_name=…&office=EM&filing_date_gte=…&sort=-filing_date&limit=100 — 한 쪽 10크레딧(무료 요금제 월 1,000).
  owner_name은 이름 낱말로 넓게 맞춰(11-09 탐침: 'KG Mobility' ↔ 'Zweirad Union e-mobility … Co. KG') 응답 출원인을 회사 규칙으로 다시 거른다.
- 11-14(Signa 답장 + 탐침 229로 확인): ① owner_name_match=phrase — 낱말이 붙어서 순서대로 나올 때만('KG Mobility' phrase 조회 0줄, 'Co. KG' 없음)
  ② owner_id=own_a,own_b,… 목록 한 번 조회가 10크레딧(회사 수와 무관, 탐침: 5개 id 목록 = 이름 조회와 같은 53줄) — 줄마다 owners[].id가 온다
  ③ filing_bases[].basis_type(미국만): intent_to_use(1B, 사용 의사)·use_in_commerce(1A)·foreign_application(44D)·foreign_registration(44E)·
  madrid_extension(66A). **출원 때 적은 근거**라 1(b)가 나중에 사용 진술서를 내도 intent_to_use로 남는다. EUIPO는 근거를 공개하지 않아 비어 있다
  ④ updated_at_gte로 최근 며칠에 Signa가 새로 넣거나 고친 줄만(탐침: 4일 → 11-11 출원 26줄) ⑤ GET /v1/offices의 last_synced_at(크레딧 0).
  머리글 X-Credits-Remaining·X-Credits-Charged. GET 주소는 2KB까지라 id는 한 번에 45개.
- 응답을 EUIPO Trademark Search 모양(applicationNumber·applicationDate·wordMarkSpecification·niceClasses·applicants·status)으로 바꿔
  euipo_trademarks.run이 같은 규칙(기준선·새 출원·등급)으로 다룬다. 키는 저장·출력하지 않는다.
"""
from __future__ import annotations

SEARCH_URL = "https://api.signa.so/v1/trademarks"
SOURCE = "Signa(EUIPO 자료를 매일 맞추는 2차 원천)"
SOURCES = {"EM": SOURCE, "US": "Signa(USPTO 자료를 매일 맞추는 2차 원천)"}
OFFICES_URL = "https://api.signa.so/v1/offices"
PAGE_CREDITS = 10
MIN_CREDITS = 30      # 남은 크레딧이 이보다 적으면 더 묻지 않는다(다음 달 초기화 전까지 미확인)
ID_CHUNK = 45         # GET 주소 2KB 한도(Signa 답장 11-14)
MAX_PAGES = 6         # 목록 조회 한 번에 읽는 쪽 수(쪽마다 100줄·10크레딧). 넘으면 '일부만'으로 남긴다
BASIS_KO = {"intent_to_use": "사용 의사(1B)", "use_in_commerce": "사용 중(1A)", "foreign_application": "외국 출원 우선권(44D)",
            "foreign_registration": "외국 등록 기초(44E)", "madrid_extension": "마드리드 지정(66A)"}
UA = "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"


def _status(st, raw):
    """EUIPO는 원래 상태 글(APPLICATION_PUBLISHED), USPTO는 숫자 코드(630)라 단계 글을 앞에 붙인다(11-10: 화면에 '상태 630'만 보였다)."""
    code = str((raw or {}).get("code") or "").strip()
    stage = str((st or {}).get("stage") or (st or {}).get("primary") or "").strip() if isinstance(st, dict) else ""
    if code and not code.isdigit():
        return code
    if stage:
        return f"{stage}(USPTO 코드 {code})" if code else stage
    return code or None


def _row(x):
    if not isinstance(x, dict):
        return None
    mark = str(x.get("mark_text") or "").strip()
    st = x.get("status") or {}
    raw = st.get("raw") if isinstance(st, dict) else None
    return {"applicationNumber": x.get("application_number"), "applicationDate": x.get("filing_date"),
            **({"wordMarkSpecification": {"verbalElement": mark}} if mark and not mark.startswith("[") else {}),
            "markFeature": (x.get("mark_feature_type") or "").upper() or None,
            "niceClasses": x.get("nice_classes") or [],
            "applicants": [{"name": o.get("name")} for o in x.get("owners") or [] if isinstance(o, dict) and o.get("name")],
            "owners": [{"id": o.get("id"), "name": o.get("name")} for o in x.get("owners") or [] if isinstance(o, dict) and o.get("id")],
            "bases": sorted({str(b.get("basis_type")) for b in x.get("filing_bases") or [] if isinstance(b, dict) and b.get("basis_type")}),
            "status": _status(st, raw),
            "filingRoute": x.get("filing_route")}


def _left(r):
    try:
        return int((getattr(r, "headers", None) or {}).get("X-Credits-Remaining"))
    except (TypeError, ValueError):
        return None


def _headers(key):
    return {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": UA}


def search(owner, since, *, key, get, limit=100, office="EM", phrase=False):
    """회사 이름으로 한 번(10크레딧) → (rows, 남은 크레딧 또는 None, 다음 쪽 있음). HTTP 오류는 RuntimeError(상태 코드만).
    phrase=True면 이름 낱말이 붙어서 순서대로 나온 출원인만(기본은 낱말이 다 있으면 순서 무관 — 응답을 회사 규칙으로 다시 거른다)."""
    params = {"owner_name": owner, "office": office, "filing_date_gte": since, "sort": "-filing_date", "limit": limit}
    if phrase:
        params["owner_name_match"] = "phrase"
    r = get(SEARCH_URL, params=params, headers=_headers(key), timeout=60)
    left = _left(r)
    if r.status_code == 402 or r.status_code == 429:
        raise RuntimeError(f"Signa HTTP {r.status_code}(크레딧·호출 한도)")
    if r.status_code != 200:
        raise RuntimeError(f"Signa HTTP {r.status_code}")
    body = r.json() or {}
    rows = [y for y in (_row(x) for x in body.get("data") or []) if y]
    return rows, left, bool(body.get("has_more"))


def search_ids(ids, since, *, key, get, office="EM", updated_since=None, limit=100, max_pages=MAX_PAGES):
    """출원인 id 목록으로 한꺼번에(쪽마다 10크레딧, 회사 수와 무관) → (rows, 남은 크레딧, 읽은 쪽 수, 덜 읽음).
    updated_since(YYYY-MM-DD)를 주면 그날 이후 Signa가 새로 넣거나 고친 줄만. id는 45개씩 나눠 묻는다."""
    ids = sorted({i for i in ids if i})
    rows, left, pages, truncated = [], None, 0, False
    for n in range(0, len(ids), ID_CHUNK):
        cursor = None
        while True:
            if pages >= max_pages:
                truncated = True
                break
            params = {"owner_id": ",".join(ids[n:n + ID_CHUNK]), "office": office, "filing_date_gte": since, "sort": "-filing_date", "limit": limit}
            if updated_since:
                params["updated_at_gte"] = updated_since
            if cursor:
                params["cursor"] = cursor
            r = get(SEARCH_URL, params=params, headers=_headers(key), timeout=60)
            pages += 1
            left = _left(r) if _left(r) is not None else left
            if r.status_code in (402, 429):
                raise RuntimeError(f"Signa HTTP {r.status_code}(크레딧·호출 한도)")
            if r.status_code != 200:
                raise RuntimeError(f"Signa HTTP {r.status_code}")
            body = r.json() or {}
            rows += [y for y in (_row(x) for x in body.get("data") or []) if y]
            cursor = (body.get("pagination") or {}).get("cursor")
            if not body.get("has_more") or not cursor:
                break
        if truncated:
            break
    return rows, left, pages, truncated


def synced_at(office, *, key, get):
    """Signa가 그 관청 자료를 마지막으로 맞춘 시각(GET /v1/offices, 크레딧 0). 못 읽으면 None."""
    try:
        r = get(OFFICES_URL, headers=_headers(key), timeout=40)
        if r.status_code != 200:
            return None
        body = r.json() or {}
        for x in (body.get("data") if isinstance(body, dict) else body) or []:
            if isinstance(x, dict) and (x.get("code") or x.get("st3_code")) == office:
                return x.get("last_synced_at")
    except Exception:  # noqa: BLE001 — 신선도 표시는 덤이다(조회를 막지 않는다)
        return None
    return None
