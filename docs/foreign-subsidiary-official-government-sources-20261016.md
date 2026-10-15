# 해외 생산법인 현지 정부 공시 교차조회: 슬로바키아·체코

## 공식 원천 및 법인 매핑
- Kia Slovakia s.r.o. **생산법인** IČO **35876832**, 공식 홈페이지 https://www.kia.sk/en/contact/general-contact, 슬로바키아 재무부 법인·개별 회계연도 공시 https://www.registeruz.sk/cruz-public/domain/accountingentity/show/244945
- **판매법인** Kia Sales Slovakia s.r.o. IČO **35942894**는 다른 기업이다. 법인명을 유사 매칭해 합치면 안 된다.
- 현대차 체코 노쇼비체 생산법인 Hyundai Motor Manufacturing Czech s.r.o. IČO **27773035**. 현대차 체코 수입법인 Hyundai Motor Czech s.r.o. IČO **28399757**는 별개. 회사 공식 고지 https://www.hyundai.com/cz/obchodni-podminky/obchodni-udaje.html.
- 체코 재무부 공식 ARES https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/27773035 는 제조법인 IČO·정식 이름 확인만 제공. 회계연도별 감사 재무제표·배당결의·송금액은 법무부 Sbírka listin 공식 서비스 https://www.or.justice.cz/ias/ui/rejstrik 에서 법인·문서별 별도 검증 필요.
- 슬로바키아 재무부 [RÚZ Open API v2.5](https://registeruz.sk/cruz-public/home/api): `uctovne-jednotky` IČO 정식 조회→ `uctovna-jednotka` 법인 이름·IČO 이중 검증→최근 신고 `uctovna-zavierka`의 `idUJ` 동일 법인 및 2024/2025 개별 재무제표 제출일·승인일 대조. 조회 최대 16건, 법인 하나, 외부 API 실패는 실패로 기록. 현지 IFRS 보고서는 PDF 첨부로 공개될 수 있으므로 **숫자·배당원인·현금 송금은 보고서 원문 분석 전 미확인**.

## 기사로 주장하면 안 되는 사실
- DART 기아 반기보고서 2026-09-16 공시의 슬로바키아 법인 관련 `1,610,458백만원`은 **배당금수익 인식액**이다. 현지에서 같은 금액의 원화가 한국으로 실제 송금됐다는 증거가 아니다.
- 2024·2025년 현지 재무제표의 제출·승인 확인은 그 해 현지 당기순이익, 초과 배당, 2026년 현금배당 결의나 배당금 수취를 증명하지 못한다.
- 체코 재무부 ARES 법인번호 확인은 체코 감사 재무제표의 배당 항목을 읽었다는 증거가 아니다.
- 국내 자동차리콜센터 데이터는 베타 API 사용 승인 없이는 미연결. 미국 NHTSA 공개 캠페인이 국내 사양에도 적용된다는 추정, 국내 리콜이 없다는 역추정 모두 금지.
- 동일 사건 국내외 기보도 기사 전문 검증 및 홍보팀에서 확인 가능한 공개 실적·원문 조건 전에는 `confirmedScoops=0`, `approvedArticles=0`.

## 구현 산출
- `scripts/slovakia_official_accounts.py`: 슬로바키아 공식 재무부 API, 정확한 생산법인 및 연도별 감사제표 **메타데이터**만 저장; `digests/slovakia_official_accounts_latest.json`.
- `scripts/czech_factory_official_identity.py`: 체코 ARES 법인 사실만 저장; `digests/czech_factory_official_identity_latest.json`.
- `scripts/crossborder_source_gap_triage.py`: 기존 NHTSA/기아 DART 조사서에 해당 정부 공시 매핑과 부족한 증거를 결합.
- `crossborder-scoops.html`: 현지 법인번호, 2024·2025 제출·승인일, 공식 정보 링크, 본사 송금 미검증을 표시.
- `.github/workflows/crossborder-source-gap.yml`: 평일 09:10 KST 공식 해외 법인 조회→원천 결합→JSON 발행. API 오류를 0건으로 위장하거나 마지막 성공 데이터 삭제 금지.
- `tests/test_slovakia_official_accounts.py`, `tests/test_czech_factory_official_identity.py`: 법인 혼동/고유번호/등록 자료 누락/현금 과잉 추론 및 소스 오류 검증.

## 실제 검증
CI 재현을 통과하더라도 외부 정부 API의 실제 호출·접수 내역은 병합 후 정상 운영 결과 JSON으로 별도 점검한다. 특히 웹 API 오류라면 서류가 없었다고 단정하지 않는다.
