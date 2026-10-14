# NTIS 국가R&D 과제 — 등록 PC 수집 패키지

## 2026-10-14 정상 접속 확인

사용자의 등록된 Windows PC에서 **REAL_PROJECT_DATA_CONFIRMED** 응답을 확인했습니다.
테스트에 표시된 **115,991건은 넓은 진단 검색어의 전체 검색 결과 수**입니다.
자동차·철강 등 개별 출입처 기업의 과제 건수가 아닙니다.

일반 GitHub-hosted runner에서 두 공식 경로 HTTP 404가 반복됐습니다.
이것은 등록한 PC IP와 runner의 출구 IP 차이와 부합하지만,
**IP 제한이 유일한 원인이라고 단정하지 않습니다**.

## PC에서 실제 과제 검색식 수집

1. 이 저장소의 `scripts/ntis_pc_collect.ps1`와 `scripts/Run_NTIS_Collection.cmd`를 **같은 폴더**에 다운로드합니다.
   또는 제공되는 NTIS 등록 PC 수집용 ZIP 패키지를 압축 해제하세요.
2. **NTIS 신청 당시 공인 IP가 유효한 같은 PC·네트워크**에서 `Run_NTIS_Collection.cmd`를 더블클릭합니다.
3. NTIS 키를 PowerShell 숨김 입력란에 직접 입력합니다. 키는 파일·GitHub·채팅에 저장하지 않습니다.
4. 이 프로그램은 먼저 공식 과제번호·제목이 존재하는 진단 `HIT`를 확인합니다.
   확인되지 않으면 본 수집을 실행하지 않습니다.
5. 공개 저장소 `digests/patent_rnd_dossiers_latest.json`에 실린 최근 공개 특허의 검색식부터 최대 8개를 확인합니다.
   결과는 같은 폴더의 `ntis_project_leads_latest.json`으로 저장됩니다.
6. JSON 파일을 **메모장으로 열어 API 키 등 비공개 정보가 없는지 직접 확인**한 뒤 이 채팅에 첨부하세요.
   AI가 파일 구조·과거 특허·검색 키워드와의 관계를 검토하고 GitHub 수집본 반영을 이어갈 수 있습니다.

## 출력 필드와 공개 한계

- 첫 검색 페이지(검색식당 최대 10개) 과제번호·과제명·수행기관·기준년도·연구기간·250자 내외 연구내용·키워드·NTIS 공식 검색 링크만 저장합니다.
- 원문 URL에 승인키는 포함하지 않고, NTIS 공식 검색 링크만 제공합니다.
- `patentOutcomeConfirmed`, `companyProjectParticipationConfirmed`, `commercializationConfirmed`는 전부 `false`입니다.
- 동일 기술어·기관명은 **동일 국가과제, 실제 특허 성과, 차량 적용, 신규 사업, 단독 사실의 증거가 아닙니다**.
- 자료는 가장 최근 GitHub 특허 조사서의 `generatedAt`를 결합해 저장합니다. 웹페이지는 당시 조사서와 시점 일치시에만 표시합니다.
- 특정 기업 검색 0건은 해당 기업이 국가과제를 수행하지 않는다는 뜻이 아닙니다. 검색어·정식 명칭·API 색인 범위 한계가 있습니다.

## 실행 검증

다음은 API 키나 네트워크 없이 XML 구조 테스트만 진행합니다.

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ntis_pc_collect.ps1" -SelfTest

GitHub Actions에서 `-SelfTest` 및 `scripts/ntis_validate_local_export.py`의 회귀테스트를 수행합니다.
등록 IP가 아닌 GitHub-hosted runner의 **실패가 반복되는 예약 수집은 일시 중단**했습니다.
원격 실행이 꼭 필요하면 NTIS의 승인을 받은 고정 출구 IP 서버가 필요합니다.

이 패키지는 등록 PC에서 실행할 때만 과제자료 수집을 시도하며, 원격 서버를 대신 자동 실행하지 않습니다.
