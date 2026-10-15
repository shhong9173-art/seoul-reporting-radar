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
