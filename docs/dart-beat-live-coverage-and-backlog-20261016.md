# 산업부 OpenDART 실제 운영 1차 결과·고유번호 보완

기준 2026년 10월 15일 18:09 KST, 첫 전체 출입처 감시에서 48개 화이트리스트 기업 중 **43개사 DART 조회 성공, 5개사 고유번호 미확인, API 조회 오류 0개사, 최근 30일 대상 공시 30건, 원문 상세 조회 12건, 남은 계약·생산 공시 상세 4건**이 확인됐다. 모든 회사의 전 자료·산업 전체 뉴스가 확인됐다는 뜻은 아니다. 저장 파일: `digests/dart_beat_monitor_latest.json`, `digests/dart_beat_changes_latest.json`, `digests/dart_corp_code_coverage_latest.json`.

공식 OpenDART 기업 고유번호 ZIP에서 이름 일치로 13개사 코드를 신규 등록했다. 그러나 KG스틸은 동일/유사 한글 정식 법인명 복수 매치, 포스코홀딩스는 영문 'POSCO홀딩스' 회사명 등으로 기존 정식 이름 일치 수집에서 빠졌다.

## 공식 회사소개 화면으로 **개별 검증** 후 고정한 두 회사

- KG스틸 **법인 고유번호 `00115676`**, 주식코드 `016380`; 원자료: https://englishdart.fss.or.kr/dsbc001/selectPopup.ax?selectKey=00115676
- 포스코홀딩스 **법인 고유번호 `00155319`**, 주식코드 `005490`; 원자료: https://englishdart.fss.or.kr/dsbc001/selectPopup.ax?selectKey=00155319

이는 각각 실제 OpenDART 회사정보에 표시된 법인 고유번호/주식코드의 짝이다. 다른 회사가 유사한 이름이나 일반 검색어를 사용해도 이 고유번호를 임의로 교체하지 않는다. 특히 KG스틸 코드를 과거 KG동부제철 상호와 문자열 유사성만으로 추정하는 것을 금지한다.

OpenDART 회사코드 ZIP 자동 갱신에서도 **기존 등록 고유번호가 같은 법인명 검색 후보 복수 건 중 하나에 속하면** 정상 확인으로 기록하되, 기존 코드가 어떤 정확 이름 후보에도 속하지 않는다면 수동 검증 경고를 유지한다. 잘못된 고유번호를 자동 덮어쓰지 않는다.

## 기존 공시의 원문 추출 보강 ≠ 새 계약/기업 변화

첫 수집에서 30건의 관련 공개 문서를 확인했고, 세부 원문 검토 대상 16건 중 최대 12건을 확인하여 4건이 남았다. 두 번째 공식 수집에서 같은 접수번호·회사/법인코드/공식 URL이 일치하는 **검증 성공 캐시**는 재사용하고, 나머지 4건을 순서대로 다시 확인한다. 기존에 API 원문 실패가 있었던 정정공시는 실패 캐시를 영구 재활용하지 않고 재조회한다.

전회에는 공시 목록만 관측했고 이번에 같은 공시번호의 금액·계약기간을 처음 복원한 경우, 이제 `same_receipt_first_document_field_recovery`로 별도 구분한다. 이는 기업 신규 계약조건이 아니라 **수집된 증거의 상세화**다. 그 뒤 같은 번호·기존에 확인한 공시원문 추출값이 상충하면 `same_receipt_data_reparse_discrepancy`로 표기하여 수집기·원문 재현 문제를 확인한다.

공식 DART 자료가 없어 0건이었는지, 회사 고유번호가 없어 조회하지 못했는지, 페이지 한도를 초과했는지, 원문을 아직 안 열었는지를 화면에 구분한다. 이 증거만으로 신규 단독, 납품 물량 변동, 연결 실적 변경, 기보도 부재를 확정하지 않는다.

## 실제 운영 검증 방식

PR 테스트 통과는 공식 수집 성공이 아니다. 병합 후 자동 생산 수집에서 `dart_beat_monitor_latest.json`의 `companiesCodeVerified`, `companiesUnresolved`, `uninspectedRelevantDetails`, `sourceChecks`와 `dart_beat_changes_latest.json`의 'same_receipt_first_document_field_recovery'를 확인한다. 최초 공개일이 오래된 공시를 '최근 3일의 신규 사실'로 분류하지 않는다.
