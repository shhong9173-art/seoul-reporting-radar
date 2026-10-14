# NTIS 국가R&D 과제검색 API 연결 및 한계

## 설정

1. NTIS OpenAPI에서 **국가R&D 과제검색 서비스(전체용)** 이용 승인을 받아야 합니다. 성과검색·기관현황·보고서 API 이용권한과 혼동하면 안 됩니다.
2. GitHub 저장소 **Settings → Secrets and variables → Actions → New repository secret**에서 `NTIS_API_KEY`를 만들고 승인된 키를 값으로 넣습니다. 공개 Issue/PR/Actions 로그, 웹페이지, 채팅에 키를 넣지 않습니다.
3. `Actions → NTIS Public R&D Project Collection → Run workflow`에서 실행 결과를 확인합니다. 정상 실행 시 `digests/ntis_project_leads_latest.json`에 `checked` 검색식과 과제번호·제목·수행기관 등의 일부 공개 메타정보가 기록됩니다.
4. 실패 시 `status`와 `errorClass`만 확인합니다. `missing_key`, `ntis_status_or_schema_unrecognized`, `HTTP_403`, `network_or_ip_allowlist` 등을 *과제 0건*으로 해석하지 않습니다.

### 서버 공인 IP 등록 유의사항

NTIS 활용신청에서 특정 공인 IP를 등록했다면, 해당 IP에서 호출하는 경우에만 접근할 수 있습니다. GitHub 제공 기본 Actions runner는 변동 IP를 사용합니다. 신청 시 자신의 PC IP를 넣었다면 GitHub Actions 요청이 거부될 수 있습니다. 키를 다시 공개하지 말고 NTIS API 관리 화면/담당자에게 실제 호출 IP 허용 기준을 확인한 뒤, 필요하다면 고정 출구 IP 서버 또는 허용된 수집 경로를 사용합니다.

## 데이터 및 판단 규칙

- URL: `https://www.ntis.go.kr/rndopen/openApi/public_project` (승인된 전체용 API). 비밀키는 요청 시 `apprvKey`로만 전달합니다.
- 검색식: 기존 **KIPRIS 특허 교차 취재 조사서**에서 제공하는 기업·기술 조합. 1회 실행 최대 12개 검색식, 검색식당 첫 페이지 최대 10건. 하루 3회 평일 실행.
- `ProjectNumber`, `ProjectTitle/Korean`, `ResearchAgency/Name`, `ProjectYear` 등 공식 응답 필드만 일부 기록하고 공식 NTIS 검색 링크를 제공합니다.
- 같은 기관 이름·기술 키워드가 등장해도 **특허-국가과제 동일 프로젝트 여부, 특허 성과, 사업화, 단독**을 절대 자동 확정하지 않습니다.
- NTIS 성과검색(전체용) 승인이 별도로 확인되면, **과제번호와 실제 특허 성과 공개번호**의 직접 일치 여부를 검증하는 별도 연결이 필요합니다. 성과검색 권한이 없는데 검색 결과가 없다고 추정하지 않습니다.
- 외부 API가 HTML 권한 오류, 이해할 수 없는 XML, 타임아웃 또는 차단을 반환하면 공식 결과 0개로 채우지 않고 명시적 오류 상태를 남깁니다.
- 새 취재 조사서가 생성되면 `dossierGeneratedAt` 일치 여부를 확인한 뒤 웹 화면에 표시합니다. 서로 다른 시점의 근거는 새 사실로 결합하지 않습니다.

원문: [NTIS OpenAPI](https://www.ntis.go.kr/rndopen/api/mng/apiMain.do) · [공공데이터포털 과제검색 서비스](https://www.data.go.kr/data/15077315/openapi.do)

## 2026-10-14 첫 운영 진단

- 저장소에서 `NTIS_API_KEY`를 전달한 실행이 실제로 이루어졌지만, 기존 공개 예제의 `/rndopen/openApi/public_project` 경로가 **HTTP 404**를 반환했습니다(10개 검색식).
- 404는 실제 국가과제 0건이 아닙니다. 서버 IP 제약·API 서비스 주소 변경·승인된 서비스와 다른 URL 등 원인을 구분해야 합니다.
- 즉시 중단 가드가 추가돼 동일 API 경로에 대한 404/403 등 반복 요청을 하지 않습니다.
- **NTIS에 표시된 `01.통합OpenAPI_국가R&D 과제검색(전체용)_매뉴얼_2025.pdf`를 확인해 공식 요청 URL과 쿼리 파라미터를 정확히 맞출 것.** GitHub에 키/등록 IP를 공개해서는 안 됩니다.
