# 출입처 추가 연결 이후의 ‘첫 관측 공시’는 신규 사건이 아님

2026-10-16 03:19 KST 전체 DART 정상 수집 결과에서 KG스틸의 공시 `20261015000414`(2026-10-15 주요사항보고서 자기주식처분결정)가 처음 관측됐다. 그러나 이는 신규 법인 고유번호 `00115676`을 공식 확인한 후 처음 **수집할 수 있게 된 이미 공개된 공시**다. 뉴스나 단독 발견 시점이 아니다.

이전 스냅샷에서 해당 기업의 `sourceChecks.status`가 `corp_code_unavailable`, `source_error`, `pagination_uninspected` 중 하나였고 이번 스냅샷에서는 `checked`인 경우, 현재 결과에 처음 나타난 접수번호를 단순 `newly_observed_public_filing`로 분류하지 않고 `existing_public_filing_from_newly_resolved_issuer`로 분리한다.

**보도 판단에 미치는 영향**: 첫 공식 수집은 신규 발표나 기보도 부재가 아니라 *감시 범위 확대*다. 보도전문·공식 공개일과 기사 야마의 독립 검증 없이는 신규 기사/단독 후보로 확정하지 않는다. 계약조건 등의 실제 변경 여부는 원공시 접수번호와 두 공식 문서를 정확히 연결한 별도 증거만 인정한다.

정정공시가 새로 감시된 법인의 과거 문서라면 정정 자체의 실측 근거 등은 따로 분류하되 `firstObservedBecauseIssuerBecameCollectable=true` 플래그와 취재 질문을 붙여 **감시 범위 확장이라는 사실을 숨기지 않는다.**

`tests/test_dart_beat_monitor.py`는 KG스틸 재현 사례, 이미 조회 중이던 기업의 새로운 공식 접수와의 구분을 검증한다.
