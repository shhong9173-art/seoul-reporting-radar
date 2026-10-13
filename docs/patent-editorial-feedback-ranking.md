# 특허 발제 후보의 기자 판정·취재 근거 기반 재정렬

## 현재 지원 범위

- 기초 자료: KIPRIS 공식 공개특허 → 기존 특허 분석/발제 대기열 `digests/patent_desk_latest.json` → DART 교차검증 `digests/patent_cross_evidence_latest.json`.
- 담당 기자 수동 판정: `data/patent_editorial_reviews.json` (GitHub Actions **Record Patent Editorial Review**).
- 공개 근거 URL이 있는 체크 상태: `data/patent_reporting_checks.json` (GitHub Actions **Record Patent Public Fact Check**).
- 결과: `digests/patent_reporting_triage_latest.json`, `patent-pitches.html`의 현재 추천 순서, 보류 이유, 확인이 필요한 다섯 항목.
- 체크 다섯 항목: 선행보도/회사 발표, 기업 공개 답변, 기술 실제 적용, 산업 영향, 기사 핵심 주장과 반론.
- 편집자 판정은 최신 append-only 사건 1개만 인정. 공개 검증은 개별 항목 최신 체크를 인정하며 **긍정·반증 판정에는 실제 공개 HTTPS URL 필수**. 단순 `needs_check`나 URL 없는 입력은 점수를 높이지 않음.
- 이미 보도·출입처 밖·근거 미흡·가치 부족·기사 발행된 후보는 신규 발제 추천에서 제외. 이력은 별도로 보존.
- 기보도 미검색 후보는 신규 상위 추천보다 기사 검색 확인을 우선. DART에서 동일 기업·특정 기술어휘가 함께 나와도 같은 연구·사업, 기술 적용 또는 기술 성과라고 확정하지 않음.
- 기자가 `worth_reporting`으로 표시하고 공개 체크 5개가 채워져도 **편집자 검토 필요 단계**일 뿐, 부장 보고 확정·기사 출고 승인 또는 단독임을 뜻하지 않음.

## 적중률과 순위 해석

- 실제 기사 가치에 대한 **최종 수동 판정**이 없는 경우 관측 적중률·오분류율은 숫자 0%가 아니라 `null`(측정 불가).
- 충분한 최종 판정이 생겨도 **담당자가 선택하여 검토한 편의표본**의 긍정·부정 비중이다. 133건 전체의 정확도나 단독기사 발견율로 일반화 불가. 알려진 CJ 사후 특허 재현 사례 역시 새 단독을 찾은 실적이 아니다.
- 점수는 기존 문서근거 기반 점수에 일부 기자의 **공개 기록 진행 상황과 수동 판정**을 더한 **취재 순서 점수**다. 기사 적중 확률, 신규성 가능성 또는 ML 모델의 추정값이 아니다.
- 브라우저의 민감한 취재 결과 체크는 해당 브라우저에만 있고 서버에 전송되지 않는다. 따라서 GitHub의 공용 점수에는 반영되지 않는다.
- 같은 브라우저라도 GitHub 공개 판정은 자동 기록되지 않는다. Actions에서 인증된 저장소 사용자가 별도로 제출해야 한다.
- `reviewQueue`는 모든 후보를 보존하며, 보류나 기보도 검사 미실시 건은 상위 5건에 자동 승격하지 않는다.
- 기존 발제용 3개 항목 `*제목 (홍성효, HH:MM)`의 원문과 편집/복사는 그대로 유지. 최신 발제·교차검증 스냅샷 시각 일치 시에만 새 순위 표시. 불일치하면 이전 공식 순서로 복귀.

## 실행·검증

- 독립 정기 작업 `.github/workflows/patent-cross-evidence.yml`: 기존 검증 자료로 cross evidence를 생성한 다음 새 triage 생성. KIPRIS API 실패에도 별도 검사 가능.
- KIPRIS 정규 작업 `.github/workflows/kipris-patent-hunt.yml`: 정상 특허 데이터 이후 교차검증, 기자 판정 순위 산출, 독립 건강 상태 표시.
- 두 가지 GitHub 입력 workflow는 리뷰 입력 뒤 triage를 즉시 재계산.
- 별도 테스트 `tests/test_patent_reporting_triage.py`: 기보도/부정 판정 보류, 기자 긍정 우선, 과거 결정 덮어쓰기, 공개 URL 없는 허위 확인 배제, 출처 시점 불일치 중지, 표본 0건 null, 다섯 항목 완료여도 자동 출고 없음.
- 별도 모델 학습, 뉴스 기사 내용 자동 판정, NTIS/IR 자동 동일 사업 추론 기능은 아직 포함되지 않음.
