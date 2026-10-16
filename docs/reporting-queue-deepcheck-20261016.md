# 취재 레이더 2단계: 최근 공식문서 우선 + 정정문 원계약 연결 확인 (2026-10-16)

## 변경 목적
기존 통합 취재 대기열은 2026년 10월 16일 기준 실제 최근 공식 접수 후보 0건임에도 과거 DART 변화 57건을 기본 화면에 모두 노출했다. 신규 기사처럼 오래된 자료가 재등장하는 문제를 방지하기 위해 첫 화면은 **실제 공식 접수일 최근 3일**만 보여준다. '전체 과거 자료'는 사용자가 명시적으로 선택했을 때만 표시한다.

## 새로운 심층 검증 등급
DART 정정공시 후속 자료와 그 공식 과거 이력은 각각 별개의 생성 시점이 있다. 같은 최신 recent_contracts 원천에서 파생됐고, 과거 원문 확인이 완료된 자료만 합친다.

검증에 필요한 저장된 3개 파일:
- digests/recent_contracts_latest.json
- digests/dart_contract_followup_latest.json
- digests/dart_correction_history_latest.json

조건:
1. 공식 최근 목록의 생성시각 == 후속 기사색인 자료의 dartSourceGeneratedAt == 과거 정정 이력의 dartSourceGeneratedAt
2. 후속 기사색인 생성시각 == 과거 정정 이력의 newsIndexSourceGeneratedAt
3. 공식 원문 URL·접수번호·발행회사·정정공시 여부·날짜가 일치하고 과거 후보 문서가 실제 조회됨
4. 과거 공시 후보의 기재값과 현재 정정문의 '정정 전' 값이 실제 문자열상 일치하지만 sameContractVerified=false, currentAmendmentLinkedToThisOrigin=false
5. 원공시 접수번호, 계약 상대방, 사업명, 최초 공개시점과 기사 본문을 대조하기 전에는 동일 계약이나 단독을 확정하지 않음

이 등급은 **과거 자료 조사만을 위한 검토 카드**다. 실제 신규 기사 알림이나 단독 목록에 들어가지 않는다. 데이터가 없거나 이전 스냅샷과 시점이 맞지 않는 경우 새 등급 0건이 아니라 correctionHistorySourceGate에 미확인 상태를 남긴다.

## 운영
reporting-queue.html을 홈페이지에서 열면 최근 공식 접수 필터가 기본값이다. 최신 정정문과 다른 과거 문서에서 기재값이 이어지는 후보는 '계약 동일성 미확인 · 원공시 역추적'을 사용해 별도로 본다. 다음 확인 질문은 비공개 내부 검토·미확정 계약 추궁이 아닌 이미 공개된 접수번호와 확정 서류를 검증하는 범위로 제한한다.

CI는 Python에서 3개 원천의 시점 불일치·위조된 문구 일치·다른 회사·원문 URL을 거르고, Node에서 화면 기본선택과 미확정 문구를 검증한다. 병합 후 GitHub Actions의 실제 저장된 원천 재생 결과로 최종 확인한다.
