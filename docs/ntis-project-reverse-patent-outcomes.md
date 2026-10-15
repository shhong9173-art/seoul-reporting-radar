# NTIS 과제번호 → 특허 성과 역조회 (26개)

## 공식 API 근거와 확정된 범위

사용자가 업로드한 **2024-01-03 국가R&D 성과검색(전체용) 공식 매뉴얼**의 국가R&D 특허 검색 명세(p.15–18)를 기준으로 구현합니다.

- 공식 성과검색 endpoint: `https://www.ntis.go.kr/rndopen/openApi/public_result`, `collection=rpatent`
- 검색 필드 `TI`: **출원등록명, 과제고유번호**. 상세검색 필드 `TI03`: **과제고유번호**. `DBT=PAT`은 특허 컬렉션 조건
- 같은 `HIT`의 `ProjectID`: **과제고유번호**, `RegistNumber`: **출원 또는 등록번호**, `RegistType`: **출원/등록 구분**, `ResultID`: **성과ID**
- 문서의 요청명세 표에는 `SRWR`, `searchFd`, `displayCnt`가, 실제 REST URI 예시에는 `query`, `searchField`, `displayCount`가 사용됩니다. 기존 승인 PC의 실제 NTIS API 응답은 REST URI 예시 형식으로 수집됐습니다.

**주의:** `TI`와 `TI03`의 검색 필드 명세는 공식 문서에서 확인됐지만, **특정 2026년 과제번호에 대한 실제 검색 색인 방식이나 성과 반환은 아직 등록 PC에서 검증하지 않았습니다.** 0건은 미보유 또는 미연계를 의미하지 않습니다.

## 고정된 소스와 설계

과거 승인 PC의 NTIS 과제검색 8개 검색식/27개 레코드에서 **과제고유번호 기준 26개**를 중복 제거했습니다. 한 과제가 여러 기술어 검색에 노출됐더라도 HTTP 요청은 번호당 한 번입니다.

- `digests/ntis_project_reverse_plan_latest.json`: 26개 고유 과제번호와 2026→2025→과거 연도 순 조회계획. **순서는 검색 운영 우선순위이지 기사 가치 순위가 아닙니다.**
- `digests/ntis_project_reverse_kipris_source.json`: 계획을 작성할 때 검증한 공식 KIPRIS 공개번호/출원번호 7쌍의 **고정 참조본**입니다. 이후 자동 생성되는 `patent_rnd_dossiers_latest.json` 시각이 바뀌더라도 임의로 새 특허와 연결되지 않습니다.
- `digests/ntis_project_leads_latest.json`: 당시 실제 승인 PC의 국가과제 검색 결과. 26개는 전체 국가R&D 과제가 아니라 **출입처 관련 기술어 검색의 부분 표본**입니다.

검색 2단계: ① `query=<과제번호>&searchField=TI&addQuery=DBT=PAT`, ② ①의 `TOTALHITS=0`일 때만 `addQuery=TI03=<과제번호>&DBT=PAT` 상세 검색을 추가. **2단계 검색 동작은 공식 필드 명세를 활용한 후보 방식이며 실제 API의 논리 연산 결과는 아직 미검증**입니다. 응답에 어떤 다른 과제번호가 섞여 있더라도 `ProjectID`가 요청번호와 **정확히 일치**하는 행만 검토합니다.

### Windows 등록 PC 실행

`scripts/ntis_project_reverse_pc.ps1`과 `scripts/Run_NTIS_Project_Reverse.cmd`를 같은 폴더에 놓고 CMD를 더블클릭합니다. NTIS에 등록된 Windows PC/IP에서 **기존 성과검색 승인 API 키**를 PowerShell 숨김 입력란에 넣습니다.

기본 실행은 **과제 26개 × 최대 2개 검색 방식 = 최대 52회**, 검색별 첫 페이지 10건만 확인합니다. 우선 3건만 시험할 경우 Windows PowerShell에서 다음과 같이 실행할 수 있습니다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ntis_project_reverse_pc.ps1" -MaxProjects 3
```

수집 완료 후 **`ntis_project_reverse_pc_latest.json`**을 이 대화에 첨부합니다. API 키, 전체 인증 URL, 관계없는 NTIS 특허 성과 원문은 저장하지 않도록 구성했습니다. 실행 도중 `RESULT:` / `DIAGNOSTIC:`이 뜨면 **그 줄만** 보내주고 인증키는 공유하지 않습니다.

### 결과와 기사 검증 기준

1. 공식 성과검색의 각 `HIT`에서 `ProjectID`와 요청번호가 같은가?
2. 같은 `HIT`의 `RegistType`이 **출원(code 01)**이고, `RegistNumber`가 KIPRIS의 **출원번호**와 정확히 일치하는가? 등록번호·공개번호와 혼용 금지
3. `ResultID`를 통해 원문을 재확인할 수 있는가?
4. 과제의 **주관·공동연구기관**, 특허의 공동출원인과 기술적 역할, 성과 귀속, 기보도, 실제 제품/양산 적용을 별도 취재했는가?

1–3을 충족한 경우에도 **자동 확정이 아닌 번호 일치 취재 검토 후보**입니다. 과제번호·특허번호가 함께 조회됐더라도 기업 사업화·수주·양산 및 **미보도 단독**은 확정하지 않습니다. 결과가 없거나 검색 0건·페이지 미확인·API 오류인 경우에도 특허 성과 부재는 확정할 수 없습니다.

### 보안·재현성 테스트

- `python scripts/ntis_project_reverse_plan.py` — 26개 과제번호의 고정 출처 검증
- `python -m unittest discover -s tests -p 'test_ntis_project_reverse*.py' -v` — 식별번호와 사업화 과대 해석 차단
- `python scripts/ntis_project_reverse_validate.py ntis_project_reverse_pc_latest.json` — 실제 PC 결과 수입 전 엄격한 구조·키·출처 검증
- GitHub Actions `NTIS Project-ID Reverse Patent Outcome Regression`: Windows PowerShell 5.1에서 고정 실수집 소스 26건으로 검색계획을 구성한 뒤 **가상 공식 XML**을 사용하여 전체 루프·타입 검사·JSON 생성을 검증. 테스트의 번호 일치는 실제 NTIS 발견 사례가 아닙니다.

## 2026-10-15 09:57 KST — 등록 PC의 실제 3개 과제 시범조회

업로드된 `ntis_project_reverse_pc_latest.json`을 과거 공식 국가과제 데이터·고정 KIPRIS 출원번호 자료와 대조했습니다.

- 정확히 **3/3개 과제번호 조회**, API 6회 완료, 오류 0회.
- `2410017694` (글로벌엔지니어링 xEV 위치센서), `2410017896` ((주)오텍 PBV), `2410019058` (한빛이디에스 전력설비 센서): 모두 **TI 0, TI03 0, 실제 확인 성과행 0**.
- 이 자료는 **NTIS 성과검색 서비스에 해당 특허 성과가 없다는 판정이 아님**. 공식 매뉴얼의 TI/TI03 명세는 확인됐으나 검색 필드가 실서버에서 과제번호를 정확히 색인하는지는 양성 대조군 검사로 증명되지 않았습니다.
- 따라서 **나머지 23개 과제의 일괄조회는 보류**. 먼저 기존 `부분방전` 특허 성과검색의 실제 HIT에서 추출한 공식 `ProjectID`와 `ResultID`를 기준으로 같은 결과가 과제번호 검색에서도 재현되는지 검증합니다.

### 검색 필드 양성 대조군 검증

승인받은 Windows PC에서 **`scripts/ntis_project_field_control_pc.ps1`**과 **`scripts/Run_NTIS_Project_Field_Control.cmd`**를 같은 폴더에 두고 CMD를 실행합니다.

실제 NTIS `rpatent`에서 먼저 `부분방전`을 조회하고, 정규화된 **10자리 과제번호와 성과ID가 동시에 들어 있는 공식 HIT 1건**을 메모리에서 선택합니다. 그 과제번호를 ① `searchField=TI`, ② `BI`, ③ 기본 전체검색, ④ `부분방전`+`TI03` 상세조건, ⑤ 과제번호+`TI03`로 조회합니다. **총 최대 6회**, 각 페이지 첫 10건만 확인합니다.

단순 `TOTALHITS`뿐 아니라 최초 공식 성과의 **같은 `ResultID`와 `ProjectID`가 검색 결과에 다시 나타나는지** 기록합니다. `searchField`별로 0이 나오면 해당 경로의 검색 재현이 확인되지 않았다는 의미일 뿐 전체 성과 데이터 부재가 아닙니다.

생성되는 `ntis_project_field_probe_pc_latest.json`에는 **검색별 총건수·응답행·같은 성과 재발견 여부만** 저장됩니다. 대조군의 과제번호, 성과ID, 관계없는 성과행, 개인명, URL 전체, API 키는 출력하지 않습니다. 파일을 메모장으로 확인한 뒤 해당 JSON만 채팅에 올리면 됩니다.

Python 검사기 `scripts/ntis_project_field_control_validate.py`는 키 노출·과장된 기사 주장·예상 밖의 데이터 필드·10자리 무관 과제번호 저장까지 차단합니다. GitHub Actions의 Windows PowerShell 5.1 오프라인 가상 응답 테스트는 실제 서버에서 인덱싱이 된다는 증거가 아닙니다.
