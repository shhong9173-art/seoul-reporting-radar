# 주말 자료 검증·국내 리콜 API 연동 준비 (2026-10-16)

## 주말 발제 대기열

- weekend-desk.html: GitHub Pages에서 최신 원천 JSON을 직접 읽고 실제 DART 접수일 기준 최근 3일 항목과 그보다 오래된 공식 문서의 기재 변화 조사서를 분리한다. 스냅샷 생성일을 사건 발생일로 치환하지 않는다.
- weekend_rules.js: 정확한 DART 접수번호·URL·날짜 확인, 중복 제거, 기보도/기업 영향/단독 자동 확정 금지, 실패한 원천의 0건 오판 금지.
- 공시 문안 복사 기능은 원문 확인용 취재 체크 문안이고 데스크 승인·기사 출고를 의미하지 않는다.
- 원천: latest.json, investigation_hunt_latest.json, official_event_triage_latest.json, patent_run_health_latest.json, dart_corp_code_coverage_latest.json, domestic_recall_screen_latest.json, crossborder_source_gap_latest.json.

## DART 법인식별·기보도

- 국내 외제차 브랜드명과 공시 의무 법인은 별개일 수 있다. 정확 공식 이름 일치 실패(BMW코리아, 아우디코리아, 폭스바겐코리아)와 동명 2건(KG스틸)을 별도로 보여 주되, 다른 법인명으로 자동 연결하지 않는다.
- 공시 고유번호 미확인 또는 뉴스 제목 검색 무결과는 공시/기사 0건의 증거가 아니다. 동일 수주·투자 사업명·실제 기사 전문 및 기업 직접 답변을 비교한 뒤에만 보도 차별성을 판단한다.

## 국내 리콜 API 승인 이후 계약

이용 신청 메일을 보냈더라도 실제 승인·상세 명세를 받기 전에는 koreanRecallAPI=not_connected_permission_required를 유지한다. 공개 HTML 첫 화면의 차종 제목이 국내 동일 부품/리콜 부재를 증명하지 않는다.

공식 명세 수신 뒤 (1) 승인된 HTTPS 호스트·인증 방식, (2) 기간별 목록/상세 리콜번호, (3) 제작사·차명·연식·제작 시작/종료·결함 부품·설명, (4) 시정 개시일·정정/무상수리 구분, (5) 페이징·총건수·조회 제한, (6) 재배포/개인정보 제한을 검증한다. 실제 스키마에 없는 필드나 부품 일치·리콜 부재 판정은 만들지 않는다. 승인 전 임의 엔드포인트 호출이나 VIN 기반 개인정보 조회는 금지.

## 검증
node tests/test_weekend_desk.cjs: 미래·가짜 날짜, 오랜 공시, 비공식 링크, 중복 원문, 법인 미해결, 리콜 API 미연결, 미검증 문안의 기사 승인 금지.
