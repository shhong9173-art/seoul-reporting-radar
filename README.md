# 자동차 산업부 취재 레이더

자동차·부품·배터리 담당 기자용 뉴스 모니터링 대시보드입니다.

## 테스트
수집 파이프라인 즉시 실행 테스트용 커밋입니다.

## 기능
- 오늘 꼭 볼 것 / 단독·속보 후보 / 후속 취재 후보 / 전체 모니터링
- 완성차 / 부품 / 배터리 / 정책·관세 / 중국차 / 노조·생산
- 주요 자동차·배터리 기업 필터
- Google News RSS 기반 최근 72시간 자동 수집
- 기사 중복 제거 및 이슈 클러스터링
- 최초 관측 매체·보도량·커버리지 공백 표시
- 취재가치·후속취재 가치 점수
- 원문 링크 중심 모니터링

## 자동 갱신
`.github/workflows/auto-desk.yml`이 30분마다 `collector.py`를 실행하고 `data.js`를 갱신합니다. `data.js` 변경은 workflow 재실행 대상에서 제외합니다.

## 주의
‘단독 후보’는 기사형 단독 표기를 탐지한 후보이며 실제 단독 여부를 보증하지 않습니다. 기사 작성 전 원문과 취재원 확인이 필요합니다.

## 선배 취재 키트 기반 확장
- 출입처별 아침 공시 브리핑: [`morning.html`](morning.html) 및 `digests/latest.md` (첫 자동 실행 이후 생성).
- 독립 일정: `.github/workflows/reporter-morning.yml`, 평일 06:50 KST, 기존 `DART_API_KEY` Secrets 사용.
- 원자료 → 이미 보도 확인 → 본 기자 발제 → 팩트체크: [`reporter_kit/README.md`](reporter_kit/README.md)
- 관세청·네이버 API 도구: `scripts/customs.py`, `scripts/news_check.py` (별도 키 필요).

## 신규: 공식 데이터 발굴·회사 간 비교
- [데이터 발굴 화면](data-lab.html)에서 자동차, 자동차 부품, 전력기기, 철강, 비철 기업의 3개년 연결 매출·영업이익과 최근 반기 누적을 비교한다.
- OpenDART 전체 재무제표(`fnlttSinglAcntAll`)를 같은 보고서 코드·기업코드·계정 ID·원화 연결 기준으로 검산. 실제 데이터를 확보하지 못하면 빈 값으로 남긴다.
- [공식 지표 비교 엔진](scripts/peer_financial.py)은 3곳 이상 회사가 비교될 때 매출 증감률의 경쟁기업 중앙값 격차가 큰 자료를 **취재 단서**로만 제시한다. 단독 자동 확정 금지.
- [매주 자동 실행](.github/workflows/peer-data-research.yml): 월요일 07:20 KST 예정, API 장애 시 기존 JSON 보존. 자세한 기준은 [설계 문서](docs/peer-research-design-20261013.md).


## 사업보고서 ‘사업의 내용’ 본문 발굴 시범
- `scripts/business_content.py`: 2024·2025 사업보고서의 'II. 사업의 내용' 공식 원문에 등장하는 수주·생산능력·가동률·부문매출 표 증거를 탐색.
- `data-lab.html`에 새 원문/표 대조 패널 추가. 숫자 비교 검증과 단독 판정은 아직 아님.
- `.github/workflows/business-content-scout.yml`: 주간 자동 갱신, 공식 XML 조회와 데이터 보존 안전장치.
- 범위·한계: `docs/business-content-scout.md`.


## 공식 사업보고서 수주·생산능력 수치 검산
- `scripts/business_metric_compare.py`가 전·당기 이월 수치와 동일 행·표시 단위·회계기간을 교차 검증한 뒤 `digests/business_metrics_latest.json`을 생성한다.
- 현대차·기아·현대제철·세아제강을 추가해 공식 사업내용 발췌 대상으로 총 7개사를 확인한다.
- `data-lab.html`은 검증된 두 원문 수치 변화와 각 원문 링크를 별도 영역에 표시한다. 공개된 사업보고서 재분석 결과이며 단독 인증은 아니다.
- 상세 검증 및 사례: `docs/business-metric-validation-20261013.md`.


## 관세청 HS 무역통계 지표 · 인증키 설정 시 활성화
- `scripts/customs.py`의 월별 숫자 검증식, 필수 응답 필드·정확한 소수 수치 유지 기능을 보완했다.
- `scripts/customs_watch.py`는 HS 8504(변압기·정지형변환기 포함), 8544(절연전선·케이블), 8703(승용차), 7208(열연 평판압연제품 관련)을 관세청 공식 API에서 조회한다. 품목군은 모두 광범위한 HS4로 개별 출입처 기업 실적이 아니다.
- 최근 완결 월까지 조회하되 동일 월의 전년 동기만 비교하고 수출금액(USD), 중량(kg), 환산 수출단가(USD/kg)를 검산한다.
- `CUSTOMS_API_KEY` GitHub Actions Secret이 설정된 경우에만 매주 월요일 07:55(KST) 실행해 `digests/hs_trends_latest.json`을 게시한다. **Secret 미설정 시 파일을 만들거나 0으로 채우지 않는다.**
- `data-lab.html`에 공식 HS 추세 별도 섹션 추가. DART 계약 수주·생산능력 수치와 직접 연결된다고 추론하지 않는다.

## 최신 분기·반기 사업본문 취재 레이더
- `scripts/recent_business_scout.py`는 2026년 현시점 최신 정기보고서(1분기·반기·3분기)를 찾아 2025년 **동일 보고기간** 사업내용 원문과 대조한다.
- 현대차·기아·전력기기 3사·현대제철·세아제강 직접 출입처 7사, 공식 투자 사업명·관련 표 일부·원문 접수번호·언론 검색 후보를 `digests/recent_business_latest.json`에 저장한다.
- 매 평일 오전 07:45(KST) 최신 접수번호를 확인하고, 변경이 없으면 이전 검증 원문 발췌를 재사용한다. 새로운 정정공시라면 즉시 원문 재조회.
- `data-lab.html`에 출입처별 최신 투자 근거·선행 기사 검색·취재 질문을 제공.
- 이전 표 일부에서 사업명이 보이지 않아도 신규 투자·최초·단독임을 뜻하지 않는다. [설계와 검증](docs/latest-interim-source-scout.md).

## 해외 공식 문서·최근 DART 계약 취재 레이더
- `official-watch.html`에서 US Federal Register의 연방고시, EU TED의 조달공고, DART 공급/시설투자/생산 공시를 **공식 원문 링크와 함께** 조회한다.
- `scripts/overseas_official.py`: 미 연방 공식 고시와 EU 공개 조달 제목/구매기관의 직접 회사명 언급만 추적. 해당 회사의 공장 허가·낙찰 사실로 확정하지 않음.
- `scripts/recent_contracts.py`: 직접 출입처 DART 최근 21일 공시 중 신규 공급계약·시설투자·생산재개·중단과 정정 원공시를 **명시적 접수번호 근거가 있을 때만** 연결.
- `.github/workflows/official-overseas-contracts.yml`: 평일 08:10 KST 새 원천 검색, 회사 코멘트·기보도 검증 전까지 단독 미확정.
- 실제 원천의 범위와 빠진 현지 미국 주/카운티 공장 인허가: `docs/official-overseas-contracts.md`.

## 공식 투자계획의 원문 변화 발굴
- hunt.html은 2025 연간 사업보고서와 2026 최신 정기보고서, 가능하면 2024 연간 보고서의 같은 투자 항목을 직접 비교한다.
- scripts/investigation_hunt.py는 공식 투자 종료 예정월·금액의 변경을 찾고 기보도 검색/데스킹 질문을 제시한다. 실제 준공 지연이나 단독을 자동 확정하지 않는다.
- 평일 08:45 KST digests/investigation_hunt_latest.json 갱신. 설계: docs/source-delta-hunt.md.

## 관세청 승인 API 8종 연동 상태 (2026-10-13)
- 기존 월별 HS 통계: `scripts/customs_watch.py`, `.github/workflows/hs-trends.yml` (HS4 8504·8544·8703·7208). 개별 회사 수출실적 아님.
- 10일 누적 잠정치 수출·수입: `scripts/customs_tenday.py`, `.github/workflows/customs-tenday.yml`. 1일·11일·21일 11:30 KST 수집.
- **추가 관세청 5종**: `scripts/customs_five.py`, `.github/workflows/customs-five.yml`. 매월 16·18일 11:30 KST, 수동 실행 가능. `CUSTOMS_API_KEY` GitHub Secret 1개를 공통 사용.
- 추가 5종: 시도별 품목별(HS2·울산/충남/경북), 신성질별 국가별(미국/중국), 신성질별(전체 국가), 성질별 국가별(미국/중국), 종류별(전국 거래 형태). **표본 범위**는 출입 산업의 취재용 부분집합이며 대한민국 무역 전체를 대표하지 않는다.
- 결과: `digests/customs_five_latest.json`을 검증 후 원자적으로 교체하고 `data-lab.html`에 집계 단위별 개별 표로 표시. 각 표는 같은 달의 전년도 값과 비교한다. 중복 합산/기업 귀속/단독 표시 금지.
- 공공데이터포털 월별 공식 통계의 다음 달 중순 공표 주기를 고려하여 **16일 이전에는 전전월**, 이후에는 전월을 조회한다. 신규 월 값이 미수신되거나 API 오류가 나면 기존 JSON은 보존하며 해당 수집 실행은 실패 처리한다.
- 실데이터 검증과 범위: [관세청 5종 API 통합 설계](docs/customs-five-statistics.md).

## KIPRIS 공식특허 발굴
- [특허 취재 레이더](patents.html)는 24개 국내 직접 출입처 법인의 공식 출원인명·최근 35일 공개특허 번호·공개일·초록·IPC를 대조한다. 출원일과 공개일은 별도 표시.
- KIPRISPlus **해당 특허·실용신안 공보 API 이용 승인과 별도 ServiceKey**가 있어야 실제 수집 가능. GitHub Actions Secret `KIPRIS_SERVICE_KEY`로 설정. 관세청 키와 다름.
- `scripts/patent_hunt.py`, `digests/patent_hunt_latest.json`, `.github/workflows/kipris-patent-hunt.yml`: 평일 09:15(KST) 갱신. 특허 공개는 사업화·단독 확정이 아니며 미인증은 0건으로 취급하지 않는다. `docs/kipris-patent-hunt.md`.

## 특허 기술 변경 단독 연구 2단계
- `scripts/patent_deep_hunt.py`와 `digests/patent_deep_latest.json`: 24개사 최근 특허 공개번호별 중복/공동출원 합산, 정밀 기술주제 교정, 제목 유사 특허와 2023년 이후 공식 동일 발명명칭 선행공보 조회(최대 10건).
- `patents.html` 특허 심층 취재 조사 카드: 기술적 청구항/외국 특허패밀리/양산·수주 관련성은 아직 독립 확인 전 미확정, 기술 관련성과 회사 답변 검증을 독려. [설계/검증](docs/kipris-patent-deep-hunt.md).

## KIPRIS 공식 제1항(청구항) 원문 대조
- `scripts/patent_claim_review.py`가 특허 공개/심층 결과에 연결된 공식 출원번호를 KIPRISPlus 서지상세 `getBibliographyDetailInfoSearch`에 조회한다. 이전 문헌(동일 발명명칭·일부 동일 출원인)과 **청구항 제1항의 문구를 확보한 경우에만** 비교해 `digests/patent_claim_review_latest.json`에 발췌·해시·유사도와 취재 질문을 저장한다.
- 원문 부재·청구항 파싱 오류는 결과 없음으로 취급하며 의미 있는 신기술·단독이라고 판정하지 않는다. 특허 `patents.html` 페이지의 `/claim-check` 영역과 [원칙](docs/patent-claim-source-review.md) 참고.
