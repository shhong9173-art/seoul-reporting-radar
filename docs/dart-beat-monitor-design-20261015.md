# 산업부 출입처 확대 DART 감시 및 공식 변화 검증

## 범위와 공식 API

- 기존 `recent_contracts.py`는 13개 직접 출입처/21일/계약·투자·생산 4개 공시 유형을 조회하고 최대 9건 상세를 분석합니다. 이는 전체 출입처 감시로 해석할 수 없습니다.
- 새 `scripts/dart_beat_monitor.py`는 **자동차·부품·타이어 / 철강 / 비철 / 전력기기·전선 / 에너지·화학** 5개 그룹의 명시적 출입처 화이트리스트를 운영합니다.
- DART 공식 `list.json`으로 각 회사의 최근 30일 문서 접수일, 번호, 정확한 법인 고유번호, 공시 제목을 조회합니다. 정기·수시 공시 중 대표 비교 대상과 계약·투자·생산 사건을 분류합니다. 100건씩 최대 3페이지까지만 조회하며 범위를 초과하면 `pagination_uninspected`로 경고하고 해당 기업의 발견수를 0으로 처리하지 않습니다.
- `dart_corp_codes.json`에 이미 고유번호가 있는 회사와 미확인 회사를 구분합니다. 미확인 기업은 `corp_code_unavailable`로 표시하고 공시 0건이라고 하지 않습니다. 외국 기업 한국판매법인, 비공시법인, 일부 협회 자료의 비포함은 DART와 별도 출입처 관리 대상입니다.
- `scripts/dart_corp_registry.py`는 [OpenDART 고유번호 공식 API](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018)의 ZIP에서 법인명 정규화 후 **유일하게 정확히 일치**한 코드만 추가합니다. 법인명 유사성만으로 단일회사를 추정하지 않습니다. 기존 고유번호와 공식 목록의 일치 결과가 어긋나면 기존 값을 그대로 유지하되 수동 점검 상태로 표기합니다.

## 변동 사실의 분류

1. `newly_observed_public_filing`: 같은 번호의 공개문서가 이전 스냅샷에 없었던 것. 관측된 공개공시일 뿐 뉴스에 이미 보도됐는지는 알 수 없습니다.
2. `issuer_stated_correction_only`: 정정공시 자체의 '정정 전·후' 표에서 공식 회사 기재값 변화가 확인되지만 원공시 번호 독립 확인이 안 된 경우. 공시 기재 사실 이외 수주효과·공급 실적은 불명입니다.
3. `two_official_documents_changed_terms`: DART에 명시된 정확한 원공시 접수번호와 두 독립 문서의 같은 항목이 확인된 경우. 사업적 귀결과 기보도 여부는 별도 취재합니다.
4. `same_receipt_data_reparse_discrepancy`: 동일 공개번호의 추출 결과가 데이터 버전마다 달라진 경우. **기업 변화가 아닌 데이터 추출/수집 오류 점검 항목**입니다.
5. `previously_seen_public_filing`: 같은 공개번호가 이미 있었고 검증된 변화가 없으면 재노출하지 않습니다.

처음 생성하는 JSON은 첫 관측 기준선이며, 미보도 단독의 출발점으로 해석할 수 없습니다. 새 공시가 30일 창에 없는 회사라도 코드 조회 실패/페이지 미검사/비공시 여부에 따라 0건으로 단정할 수 없습니다.

## 실행/검증

- `.github/workflows/dart-beat-monitor.yml`: 평일 07:45 KST GitHub Actions 예정. 기존 공시 자동수집 워크플로와 같은 concurrency 그룹을 사용해 덮어쓰기 충돌을 줄입니다. 먼저 공식 고유번호 ZIP 갱신을 시도하고, 실패하더라도 기존 검증 코드로 감시를 계속합니다.
- 회사 목록 1회/회사, 최대 3페이지(각 100개) 안전 상한. 계약·투자·생산 핵심 문서의 원문은 최대 12건/회만 열어 기존 `recent_contracts.document_evidence`의 독립 원문/정정문 엄격 비교를 재사용합니다.
- `digests/dart_corp_code_coverage_latest.json`: 법인명 해소 내역(개별 기업 미연결). `digests/dart_beat_monitor_latest.json`: 범위/회사별 건강상태/공시 접수번호/첫 관측. `digests/dart_beat_changes_latest.json`: 공식 기재값·새 공개번호 변화 및 검증 한계.
- `dart-beat-monitor.html`: 분야별 필터, 최신 3일/이전 공개자료, DART 원문 연결, 동시 비교 항목/원공시, 미연결·부분 실패 상태.
- `tests/test_dart_beat_monitor.py`: 5개 그룹, 공식 페이지누락/오류/정상 0건, 원공시 독립 대조, 정정문 자체 기재, 기존 공개번호 재파싱 차이, 공식 법인 이름 유일성/충돌 검증. `tests/test_dart_beat_monitor_view.cjs`: 페이지가 기보도·실제 영향·단독 승격을 주장하지 않는지 검증.

## 운영상 한계와 다음 개선

- ‘전체 출입처’는 화이트리스트에 명시된 회사이고 **DART를 통해 공시가 가능한 법인** 기준입니다. 외국 자동차 기업의 국내 판매법인, 비공시 사업장, 협회 등은 별도 원천이 필요합니다.
- 공시 명칭이나 접수번호만 같지 않은 두 문서를 **같은 계약**으로 추정 연결하지 않습니다. 실제 사업보고서의 매출/가동률/수주잔고 비교는 동일 모수·기간·단위가 확인돼야 하며 현재 이 기능에 임의 통합하지 않습니다.
- 공식 데이터 확보와 자료 검증 후에도 전문지·다른 언론의 기사 전문과 출입처의 공개 가능한 실제 영향 확인 전에는 부장 보고용 단독 확정이 불가능합니다.

공식 출처: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018 (기업고유번호 ZIP), https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001 (공시 검색).