"""유럽·미국 상표 출원 원천(Signa, 11-09) — 유럽은 EUIPO 운영 검색이 구독 승인 대기(403)로 막힌 동안 대신, 미국(USPTO)은 이것만으로 읽는다
(USPTO 직접 API는 ID.me 인증 실패, 11-01).

- Signa는 EUIPO 등 상표청 자료를 매일 맞추는 2차 원천이다(약관 3.1: 불완전·부정확할 수 있음). 기사 전 EUIPO eSearch 원문 확인.
- 검색: GET /v1/trademarks?owner_name=…&office=EM&filing_date_gte=…&sort=-filing_date&limit=100 — 한 쪽 10크레딧(무료 요금제 월 1,000).
  owner_name은 이름 낱말로 넓게 맞춰(11-09 탐침: 'KG Mobility' ↔ 'Zweirad Union e-mobility … Co. KG') 응답 출원인을 회사 규칙으로 다시 거른다.
- 응답을 EUIPO Trademark Search 모양(applicationNumber·applicationDate·wordMarkSpecification·niceClasses·applicants·status)으로 바꿔
  euipo_trademarks.run이 같은 규칙(기준선·새 출원·등급)으로 다룬다. 키는 저장·출력하지 않는다.
"""
from __future__ import annotations

SEARCH_URL = "https://api.signa.so/v1/trademarks"
SOURCE = "Signa(EUIPO 자료를 매일 맞추는 2차 원천)"
SOURCES = {"EM": SOURCE, "US": "Signa(USPTO 자료를 매일 맞추는 2차 원천)"}
PAGE_CREDITS = 10
MIN_CREDITS = 30      # 남은 크레딧이 이보다 적으면 더 묻지 않는다(다음 달 초기화 전까지 미확인)


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
            "status": (raw or {}).get("code") or (st.get("stage") if isinstance(st, dict) else None),
            "filingRoute": x.get("filing_route")}


def search(owner, since, *, key, get, limit=100, office="EM"):
    """→ (rows, 남은 크레딧 또는 None, 다음 쪽 있음). HTTP 오류는 RuntimeError(상태 코드만)."""
    r = get(SEARCH_URL, params={"owner_name": owner, "office": office, "filing_date_gte": since, "sort": "-filing_date", "limit": limit},
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json",
                     "User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"}, timeout=60)
    left = None
    try:
        left = int((getattr(r, "headers", None) or {}).get("X-Credits-Remaining"))
    except (TypeError, ValueError):
        pass
    if r.status_code == 402 or r.status_code == 429:
        raise RuntimeError(f"Signa HTTP {r.status_code}(크레딧·호출 한도)")
    if r.status_code != 200:
        raise RuntimeError(f"Signa HTTP {r.status_code}")
    body = r.json() or {}
    rows = [y for y in (_row(x) for x in body.get("data") or []) if y]
    return rows, left, bool(body.get("has_more"))
