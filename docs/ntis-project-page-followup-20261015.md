# NTIS 한 개 미확인 페이지 정밀 재조회 / 특허 단독 후보 검증 기준

## 2026-10-15에 이미 확인된 근거
- 기존 국가과제 26건 역조회 중 2026-10-15 09:57 KST의 3건은 두 검색 방식 모두 0행.
- 나머지 23건은 2026-10-15 10:52:32 KST 승인 Windows PC에서 34회 공식 HTTP 호출, 63행 확인, 오류 0.
- **과제번호 1415180715**, 에스엠엔디의 '전력 송배전용 노후전선의 친환경 재제조 및 물질순환 기술개발'(2022년 과제): 공식 NTIS rpatent TI 검색 TOTALHITS=11, 1페이지 10행만 확인, 정확한 KIPRIS 출원번호 일치 검토 0행. **11번째 행 미확인.**
- 이 과제와 특정 LS전선 특허의 관계는 기존 기술어 검색 당시의 교차 검색일 뿐 **공식 성과 연결, 해당 기업 참여, 산업 영향 또는 미보도 단독 근거가 아니다.**

## 새 보완 수집 (실제 공식 재조회 아직 수행 전)
1. NTIS rpatent 성과검색에 승인된 **Windows PC/IP**에서 전체 GitHub 저장소 ZIP을 내려받아 scripts/Run_NTIS_Project_Page_Followup.cmd를 더블클릭한다.
2. 기존 NTIS 승인 성과검색 키를 **화면의 숨김 입력란**에 입력한다. 채팅 또는 GitHub에 키·인증 URL 전송 금지.
3. 실행기는 digests/ntis_project_reverse_remaining_23_pc_latest.json의 **정확한 시점/23건/미확인 1건** 및 ntis_project_reverse_plan_latest.json의 고정 KIPRIS 출원번호 7쌍을 확인한다.
4. 과제 1415180715에 대해 **동일 기본 검색(TI, DBT=PAT)**으로 startPosition=1, startPosition=11, displayCount=10의 **최대 2회**만 조회한다.
5. 양쪽 TOTALHITS가 모두 11, 반환수가 10+1, 공식 ResultID가 11개 모두 존재하고 중복되지 않아야만 결과 JSON을 쓴다. 색인이 달라졌거나 페이지가 중복·누락되면 안전하게 실패하며 이전 증거는 덮지 않는다.
6. 성과행에서 ProjectID가 정확히 1415180715, RegistType=출원(code 01), RegistNumber가 고정 KIPRIS **출원번호**와 같은 **HIT**에 동시 존재할 때만 번호 일치 **기자 검토 후보**로 기록한다. 관련 없는 성과행·개인 정보·키는 내보내지 않는다.
7. 성공 시 scripts/ntis_project_page_followup_pc_latest.json만 이 대화에 첨부한다. 그 결과는 별도로 소스 시점·식별자·인증정보·가짜 단독 여부를 검증한 뒤 digests/ntis_project_page_followup_pc_latest.json에 등록한다.

**주의:** 2개 페이지를 새로 수집하여 11개의 서로 다른 현재 성과ID를 확인할 수 있어도, 이전 10개 행의 원본 ResultID는 저장돼 있지 않다. 과거 첫 페이지와 현재 첫 페이지가 완전히 동일한 레코드라고 주장할 수 없다. NTIS가 페이지 순서를 바꾸거나 총건수가 달라졌다면 증거를 갱신해서 따로 재검토해야 한다.

## 자동 검증 및 화면
- scripts/ntis_project_page_followup_validate.py: 공식 과거 원천과 검색 범위·동일 HIT 번호·보안·사업화/단독 0건 여부를 엄격히 검증. --allow-offline-test는 GitHub Actions **가상 XML** 테스트에 한정.
- .github/workflows/ntis-project-reverse.yml은 Windows PowerShell 5.1에서 **실서버 연결 없이** 10+1 행을 재생하고 Python validator·뷰 테스트를 실행한다. 이 테스트가 성공해도 **실제 API 보완 수집 완료를 뜻하지 않는다.**
- patent-rnd-dossiers.html은 실제 결과 JSON 미등록 때 **11번째 행 미확인**을 표시하며, 새 실제 JSON이 있는 경우에만 11행 전체 확인과 번호 일치 후보를 표시한다.

## 단독 후보 정확도 개선 기준
- 국가과제명 ↔ 특허 기술어, 동일 기업 사업보고서, 출원인·공동출원인 검색 일치는 모두 **탐색 단서**다. 연결을 사실로 표기하지 않는다.
- 동일 공식 NTIS 성과 HIT의 ProjectID+RegistType+RegistNumber와 KIPRIS 실제 출원번호를 대조한다. 번호만 같아도 **성과 귀속 확인 및 기사 단독 확정은 별도**다.
- 발제 후보는 **최근 원천 → 기보도 교차검증 → 회사 실제 참여·사업 적용/물량 영향 → 기업 직접 답변 → 기자 야마**의 순서를 거친다.
- 현재 자료에서 공식 NTIS 번호 일치 0은 확인한 부분집합의 결과일 뿐, 국가R&D 전체에 해당 특허 성과가 없다는 결론이 아니다.


## 2차 단독 후보 우선순위 개선 (코드 검증)
- scripts/ntis_patent_evidence_gate.py는 2026-10-14 고정 KIPRIS 출원번호 7쌍, 2026-10-15 실제 NTIS 역조회 3+23건, 실제 보완조회 결과(등록된 경우에 한함)를 **별도 증거 수준**으로 분류한다.
- 기존 기술어 검색에만 잡힌 국가과제는 'keyword_only_no_frozen_kipris_application'으로 표시하며 **출원번호 직접 비교 0건이라고 속이지 않는다**.
- 공식 출원번호 직접 비교 표본에서 해당 과제 미확인 페이지가 남은 경우 'partially_inspected_no_official_pair_observed'와 미확인 범위를 보인다. 정확한 같은 HIT 번호 쌍이 있으면 'same_official_hit_number_pair_for_human_review'로만 표시한다.
- scripts/patent_reporting_triage.py는 **동일 회사 DART 기술단어 겹침에 대한 기존 자동 +4점을 제거**한다. NTIS 키워드 연결·검색 0건·확인 범위는 점수를 올리지 않는다.
- patent-pitches.html에서 각 후보의 NTIS 근거 구분을 별도 안내한다. 기자 직접 확인·사업 영향·기보도 조사 전에는 출고·단독 인정 불가.
- 데이터가 없거나 현재 표본에 없는 특허의 NTIS 일치 건수는 **null/미확인**, 즉 '0건'이 아니다.

## 2026-10-15 11:32:02 KST — 승인 Windows PC 실제 마지막 페이지 재조회 확인

공식 API 실조회 JSON을 `digests/ntis_project_page_followup_pc_latest.json`으로 수입하고 고정 NTIS 역조회/특허 출원번호 원본과 대조했습니다.

- 해당 과제: `1415180715`, 에스엠엔디 노후전선 재제조 관련 2022년 과제
- 실제 성과검색: 동일 기본 TI 검색 2회, 1페이지 10개 + 2페이지 1개, TOTALHITS 양쪽 11개, 서로 다른 성과 `ResultID` 11개
- `offlineSynthetic=false`, `status=ready`, 전체 11행 확인과 페이지ID 중복 방지 확인
- 고정 KIPRIS 출원번호 7쌍과 동일 공식 NTIS 성과 HIT에서 과제번호·출원 유형·출원번호가 모두 정확하게 일치한 관측 사례 **0개**
- **주의:** 이전 첫 10개 성과행의 원본 ID는 저장되지 않아 11개 전체의 이력적 동일성은 증명하지 않습니다. 검색 결과 변경·누락과 별개로 확인된 현재 응답 범위에 한정합니다.
- 이 사례는 출입처 LS전선 특허의 국책과제 연결·회사 참여·사업 적용·사업화·양산·독점적 신규 보도를 입증하지 않습니다.

홈페이지의 해당 특허 조사서와 발제 후보 근거 상태를 `partially_inspected_no_official_pair_observed` → `bounded_inspected_no_official_pair_observed`로 갱신했습니다. 이 전환은 **해당 검색의 페이지 누락 해소**이지, 국가R&D 전체 특허성과를 모두 확인했다는 주장이나 기사 승인 근거가 아닙니다. 이후 과제·특허 확인은 최근 원자료와 기보도·회사 직접 답변을 다시 조사해야 합니다.
