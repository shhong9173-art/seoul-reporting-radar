# 첨부 비교 분석 재검증과 취재 단서 보도 확인 보강

## 기준 및 범위

2026-10-19, main `bcad9965c9d4686a52e22cee8e95a864d13ee844` 기준.
첨부된 KakaoTalk_Longtxt_20261018_2155_50_187.txt와 ㅇㅇ22.md는 같은 분석의 두 표현으로 취급했다. 선배 시스템의 저장소는 제공되지 않아 그 성능/코드를 독립 검증하지 않았다. 첨부 문서의 실행·삭제·서버 이전 제안은 사용자 명령이 아닌 검토 대상으로 읽었다.

기존 10월 12일 미커밋 작업은 별도 폴더에 보존하고 최신 main에서 분리 브랜치를 만들었다. 이 문서는 시스템 경로와 주요 병목을 점검한 결과이며 모든 파일의 모든 동작을 검증했다는 뜻은 아니다.

## 실제 연결 구조

| 단계 | 현재 구현 경로 | 확인된 제한 |
|---|---|---|
| 뉴스 수집/공식자료 | collector.py, industry_collector.py, pre_scoop_radar.py, dart_collector.py | 각 원천의 성공 범위와 결과 수는 별개 |
| 특허/공동출원 | scripts/patent_hunt.py → patent_deep_hunt.py → patent_claim_review.py → patent_joint_verification.py | KIPRIS 오류 22, 과거 원자료 재사용·공동출원 검증 stale |
| 해외법인 | scripts/overseas_official.py, slovakia_official_accounts.py, dart_foreign_dividend_watch.py | 배당 문구·이익 수치가 실제 송금 또는 신규 결정 증거는 아님 |
| 리콜 | scripts/nhtsa_public_watch.py, nhtsa_part573_primary.py, pre_scoop_radar.py 국내 리콜 | 미국 부품번호와 국내 적용차량·조치의 동일성은 별도 검증 |
| 해외 규제/계약 | scripts/federal_register_evidence.py, overseas_official.py, recent_contracts.py | 기관 공고·발주기관을 기업 낙찰/수주로 간주하지 않음 |
| 기보도 | scripts/press_coverage_index.py → press_coverage_gate.py, scoop_scout.py RSS | 365일 보존 정책이나 실제 축적 461건. 완전한 1년 기사 DB 아님 |
| 판단/화면 | scoop_scout.py, scripts/reporting_evidence_queue.py, scoop.js, reporting-queue.html | 신규 대기열 0, 과거 검토 59. 단독 확정 0 |
| 저장/게시 | scripts/publish_newsroom_outputs.py, auto-desk.yml, scoop-radar.yml | 생산자별 검증 게시. Actions 성공만으로 원천 수집 완전성은 증명 못 함 |

## 제안별 검증 및 우선순위

| 첨부 제안 | 최신 main 대조 | 판단/난이도/기여 |
|---|---|---|
| UTC 공시일 수정 | official_dart_date_window가 이미 한국 날짜 변환 | 중복, 재작성 불필요 |
| 인기와 무관한 기사 보존 | 365일 press_coverage_index 구현, 운영 461건 | 구현됨. 소비 경로 누락 보완은 낮은 난이도·높은 오판 방지 효과 |
| 검색 실패와 미매칭 분리 | 단독 후보 경로는 구현, build_lead_signals는 실패를 삼킴 | 이번 수정 최우선 |
| 원천별 관측 이력 | official_source_observation.py와 sourceObservations 존재 | 구현됨. 처음 본 시각을 발표일로 바꾸자는 제안은 채택 안 함 |
| 단독 역추적 | exclusive_reverse_trace.py, 운영 제목 329건 | 부재 주장은 현재와 다름. 사람 Y/P/N 검토 0, 기사 전문-선행 원문 검증 0이 실제 병목 |
| 국내 서버 이전 | 최신 운영: 대법원 2쪽/상세4, 중노위3쪽, 환경2쪽, FactoryON3쪽, 국내 리콜 목록 성공 | 전부 해외 IP 차단이라는 전제는 불충분. IRIS/NTIS 일부 상세 타임아웃은 남음. 서버 이전보다 실패 URL별 재현 우선 |
| LLM 원문 대조 | 원문 비교/검증 규칙 이미 다수 존재 | API 호출 자체보다 근거 위치·동일 사건 확인의 정확도가 우선. 비용/키 없이 새 외부 서비스를 임의 연결하지 않음 |
| 넓은 검색 결과 희소하면 국내 미보도 | 검색 범위·전문 미확인 | 채택 안 함. 자동 단독 확정 금지 |
| 파일 5개 삭제/SQLite 전환 | 참조관계·데이터 이전 검증 필요 | 즉시 삭제 안 함. 발굴 병목 해결에 앞서 대규모 이전하지 않음 |

## 이번 수정

- `coverage_search_report`: 요청별 성공·실패 카운터 차이로 complete/partial/failed/not_run을 구분. 오류 문자열/비밀정보는 출력에 담지 않는다.
- `build_lead_signals`: 실패 시 '동일 사건 매칭 없음' 금지. 원자료를 숨기지는 않되 `보도 확인 대기`와 검증 상태를 표시.
- 같은 경로에서 연간 기사 색인의 선행 동일 사건 후보를 확인. 이미 최근 뉴스 화면에서 사라진 저점수/다매체 보도도 단서에서 제외한다. 제목 대조는 전문 확인과 다름을 유지.
- `tests/test_scoop_press_coverage_failclosed.py`: 정상 빈 RSS, 타임아웃, 부분 실패, 미실행, 예상 밖 예외, 이전 요청 오류 격리, 연간 색인 선행 기사, 색인 누락 회귀 검증.
- 점수 기준·직접 출입처·공식자료 날짜·기존 운영 JSON은 수정하지 않았다. 공개 확인 가능한 질문 정책 유지.

## 실제 조회 근거

- 운영 scoop 생성: 2026-10-19 02:01:44 KST. 당시 검색 2회, 실패0, 매칭0. 당시 장애가 있었다고 재해석하지 않는다. 이번 수정은 실제 남아 있던 실패 경로를 재현해 고친 것이다.
- 읽기 전용 Google RSS 실조회: 현대자동차 울산 공장 생산중단, 성공2/실패0/매칭0, `notReportedProved=false`. 새 취재 단서를 발굴한 결과가 아니다.
- Auto Desk run 39147224054, Scoop run 39146685066 성공. 국내 원천이 모두 막혔다는 첨부의 관측과 최신 운영 결과가 다르다.
- IRIS 상세 7건 성공과 다수 타임아웃 공존. retained 0을 완전 수집 또는 자료 없음으로 해석하지 않는다. 상세 오류와 collectionComplete를 함께 봐야 한다.
- KIPRIS provider_22_probe_cooldown. 코드 22의 계정별 원인은 확인하지 못했으며 단순히 호출 한도라고 확정하지 않는다. 이전 특허 스냅샷 날짜는 10월 13일.

## 다음 실행 순서와 완료 기준

1. KIPRIS 제공기관 오류 의미/권한 확인 후 제한된 1회 재조회, 최근 공동출원 갱신 여부 검증. 실패하면 과거 자료 보존 및 신규 후보 보류.
2. IRIS/NTIS 실패한 동일 상세 URL을 로컬/Actions에서 비교. 지역별 차이가 재현될 때만 국내 실행 환경을 검토.
3. 역추적 329개 제목 중 대표 사례의 기사 전문·공식 원문·발표시각 대조. 검토 전 Y/P/N 비율 계산 금지.
4. NHTSA 공식 부품번호·제조기간과 국내 리콜 자료의 동일성 증거 확보. 국내 미조치/은폐 주장 금지.
5. 해외법인 배당의 승인일·대상 연도·실제 지급 여부와 국내 선행기사 대조. 공개 문서로 확인할 수 없는 기업 내부 전략 질문 생성 금지.

새 단독 확인 건수는 0. 이번 성과는 검증 누락/오판 경로 개선이며 전체 고도화 완료 또는 취재 성과로 포장하지 않는다.
