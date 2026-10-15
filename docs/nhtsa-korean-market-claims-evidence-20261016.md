# NHTSA Part 573에서 한국 시장 사건 ‘언급’ 정확히 구분

## 기사 후보를 구분하는 원칙

2026년 10월 8일 NHTSA에 공개된 미국 리콜 `26V664000` 제조사 보고서에서 **미국 판매용 제네시스 생산·위험 사실**과 **한국 시장 관련 신고를 제조사가 언급했는지**를 구별해야 한다. 전자는 미국 리콜 범위이며, 한국 시장에서 실제 사고가 발생했다는 증명 또는 국내 시정조치가 없었다는 증명은 아니다.

`scripts/nhtsa_part573_primary.py`는 다운로드한 공식 `static.nhtsa.gov` Part 573 PDF의 첫 2쪽에서 정확한 미국 캠페인 번호를 확인한 뒤, 전체 PDF 페이지에서 `Korean market`, `Korea market`, `Korean domestic market` 같은 **시장 범위 표현**과 주변 사고/화재 관련 단어가 함께 있는지 추출한다. 단순히 차량이 South Korea에서 생산돼 미국에 판매됐다는 문장과는 별도다. NHTSA 양식의 `Description of the safety risk, including crash, fire, death, injury`는 공통 서식일 뿐 **실제 한국 화재 사건**으로 분류하지 않는다.

모든 추출 결과는 PDF 쪽수·정확한 한국 시장 언급 표현·원본 PDF 링크·미국 제조사 제출 문맥만 포함한다. `domesticIncidentVerified=false`, `koreanGovernmentIncidentChecked=false`, `domesticRecallAbsenceVerified=false`, `koreanIdenticalPartVerified=false`, `sameAnglePressFulltextChecked=false`를 고정한다. 원문에 한국 시장 언급이 **없거나 OCR 오류로 못 읽은 경우**, 한국 사건이 없었다는 뜻이 아니다.

`scripts/crossborder_source_gap_triage.py`는 공식 PDF 원천과 해당 캠페인 번호/수집 시점이 일치하는 경우에만 문맥을 취재 카드에 연결한다. `crossborder-scoops.html`에는 **미국 제조사의 주장**임을 명시하고, 해당 국내 차종·연식·부품번호·국내 자동차리콜센터 시정조치·사고의 공적 기록·기보도 전문을 확인하기 전에는 발제 승인/단독을 금지한다.

## 홍보팀에서 확인 가능할 질문
- NHTSA 보고서에 적힌 한국 시장 관련 신고·주장에 관해 회사가 공개적으로 인정하는 사실, 공개된 국내 점검/시정조치 자료가 있는지.
- 보고서에 기재된 전동시트 특정 부품이 국내 판매 사양에 실제 적용되는지, 공개된 부품·대상 생산기간 기준으로 확인할 수 있는지.
- 위 사항이 답변 불가/미공개면 원론적 홍보팀 답변만으로 국내 미조치 또는 화재를 추정하지 않음.

이 자료는 **단독 후보의 차이를 확인할 검증 대기열**이며 자동 출고가 아니다.
