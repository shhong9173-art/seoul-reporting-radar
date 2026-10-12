# 공장 인허가·조달·공급계약: 공식 원천별 취재 레이더

## 실제 확인된 공식 원천
- [미국 Federal Register](https://www.federalregister.gov/developers/documentation/api/v1) `documents.json`: 미국 연방정부 고시의 제목·요약·공개일·공식 원문 링크 검색. **미국 주·카운티 건축/환경공장 인허가 대부분은 여기서 확인되지 않는다.** 공개 고시 안의 특정 회사 언급만 확인.
- [EU TED Search API v3](https://docs.ted.europa.eu/api/latest/search.html) `POST https://api.ted.europa.eu/v3/notices/search`: 공개 EU 조달 공고의 제목·구매기관·게시일·공식 원문 링크. 검색 API는 공개 자료 접근에 API 키가 필요하지 않으나 간헐적인 호출 제한·응답 실패가 가능.
- [DART OpenDART](https://opendart.fss.or.kr/) `list.json` + `document.xml`: 직접 출입처 13개사의 최근 21일 내 공급계약·신규 시설 투자·생산중단/재개와 그 정정.
- **TED 공고에 회사 이름이 나왔다고 해당 기업이 낙찰됐다는 뜻이 아니며**, Federal Register 고시는 특정 현지공장 허가 승인과 동일하지 않음. 해외 공장 인허가 중 미국 주·카운티 자료는 아직 자동 수집 **미구현**.

## 정밀도 우선 안전장치
- Federal Register는 공식 문서의 **제목 또는 abstract**, TED는 **notice title 또는 buyer-name**에서 지정된 영문 기업명 완전 단어가 나왔을 때만 표시. 매칭이 본문 안에만 있거나 짧은 'LS', 'Kia' 같은 토큰이면 직접 회사로 연결하지 않음.
- 각 원천의 `sourceId`, 실제 `published`, `sourceUrl`, 요청 문자열, 검색 장애 유무를 보존. 수집 시간은 고시일이 아니다. TED 공고에는 **낙찰·계약 체결 확정 불가** 표시.
- DART `last_reprt_at=N`으로 정정 포함 최근 목록에서 **발행회사 고유번호·접수번호·공시 유형·접수일** 검증. 공시명만 보고 공급계약 조건을 주장하지 않음.
- DART 정정은 기존 `dart_lineage.review_lineage()`로 **원문에 명시된 원공시 접수번호를 해당 회사·공시 종류의 공식 목록에서 다시 확인하고 원/정정 원문을 각각 조회**한 경우에만 전후 수치 표시. 원계약 번호가 없는 정정은 목록·같은 날짜 후보까지만 표시.
- DART 원문 검증 상한 기본 9건, 그 밖의 목록 신호는 `uninspectedListCount`로 집계. 사업 프로젝트·관세청 수출 통계와 자동 인과 연결 금지.
- 오탐 개선: 최신 분기/반기 사업본문의 '2025년 7월~2028년 6월', '해외법인外', '미국공장' 같은 포괄적 행은 시설투자 **프로젝트명으로 분류하지 않음**.

## 작업
- `scripts/overseas_official.py` → `digests/overseas_official_latest.json`
- `scripts/recent_contracts.py` → `digests/recent_contracts_latest.json`
- `official-watch.html` → 사용자 화면에서 공식 문서·계약 근거·미확인 상태를 구분
- `.github/workflows/official-overseas-contracts.yml` 평일 08:10 KST 예정 및 수동 실행.
- `tests/test_official_foreign_contracts.py` 공식 API 모델·회사 오인식·선행 공시 확인·장애 상태 회귀 테스트.

## 남은 개발
1. 미국 주·카운티 건축/환경 인허가 사이트를 실제 해외 공장이 있는 지자체로 선별해 공식 Permit ID, Applicant, Address, 시설범위, 신청/허가 날짜 구조화.
2. TED 원문 XML의 공급사/낙찰자 법인 ID와 수주 여부·공고 종류를 계약 절차 유형별로 해독해 확인. 현재 buyer-name은 구매기관이지 낙찰사가 아님.
3. DART 원문에서 계약기간·상대방·금액을 문서 형식별로 정확히 재검증하고 원계약 접수번호가 없는 정정은 사건 동일성 수동 검증 후 별도 표시.
4. 더벨·딜사이트·해외 현지 언론 선행보도 확인 및 회사 직접 답변·데스킹 기록 구조화.
