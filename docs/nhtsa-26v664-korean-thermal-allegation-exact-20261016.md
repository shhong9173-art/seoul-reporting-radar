# 2026-10-16 NHTSA 제네시스 26V664 Part 573, 한국시장 열 관련 사건 주장 원문 정밀 분류

실운영 2026-10-16 08:46 KST 공식 NHTSA `RCLRPT-26V664-0680.pdf` PDF SHA 추출 결과의 **3쪽**에는 제조사가 `July 2, 2026 – Hyundai received additional information related to power seat switch performance and associated thermal event allegations from the Korean market`라고 기재했다.

핵심은 **한국시장에서 열 관련 사건 주장(thermal event allegations)이 접수됐다는 회사 제출 보고서의 진술**이다. 이 문장이 실제 차량 화재, 인명피해, 국내 리콜 미실시, 국내 부품 동일성, 사고 위치/수량을 독립 검증하는 자료는 아니다. 기사에서 확인 전 ‘한국서 화재 발생’으로 표현하면 안 된다.

이전 수집기 `INCIDENT_TERMS`에는 `thermal incident`만 있고 보고서 실제 원문 표현 `thermal event allegations`가 빠져 `incidentTermNearby=false`로 분류됐다. 이번 개선에서 **thermal event allegation**을 별도 분류값 `thermal_event_allegation_unverified`로 구분하고, 원문 안에 날짜 및 `Hyundai received`가 명시된 경우에만 `manufacturerInformationReceivedDateFromExactText=2026-07-02`를 기록한다.

화재가 실제 확인됐음을 뜻하는 플래그 `explicitFireConfirmedByManufacturer=false`, `domesticIncidentVerified=false`를 유지한다. 조사서에서 원문 페이지·핵심 문맥·제조사의 정보 수령일과, 국내 동종 부품 적용·당국 시정조치·국내 신고 사건·기보도 여부 각각 별도 확인이 필요하다는 경고를 표시한다.

관련 자료: https://static.nhtsa.gov/odi/rcl/2026/RCLRPT-26V664-0680.pdf (3쪽, manufacturer chronology). 독립 사실 확인은 국내 국토부/자동차리콜센터 기록, 국내 차종/연식/부품 공급범위 및 회사 공개 답변이 필요하며, 해당 근거 없이는 단독 확정 불가.
