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

## 2025-12-16 공식 매뉴얼 대조 결과 (사용자 제공 PDF, 18쪽)

- p.4 서비스 안내 URL은 `https://www.ntis.go.kr/rndopen/openApi/pjtSearch/`이며, **p.6의 실제 요청 END POINT는** `https://www.ntis.go.kr/rndopen/openApi/public_project`입니다. 이는 지난 코드의 경로와 정확히 같습니다. 따라서 기존의 HTTP 404는 *경로 오기 때문이라는 증거가 아닙니다*.
- p.6~8 파라미터 표에는 `SRWR`, `searchFd`, `displayCnt`, `searchRnkn`이 나오지만, **p.11의 공식 REST URI 예시는** `query`, `searchField`, `displayCount`, `sortby`, `naviCount=30`, `cmbnApiYn=Y`를 실제로 보냅니다. 현재 수집기는 해당 **URI 예시 방식**을 적용했습니다.
- p.8~10의 `RESULT/TOTALHITS/RESULTSET/HIT`, `ProjectNumber`, `ProjectTitle/Korean`, `ResearchAgency/Name`, `ProjectPeriod` 응답 구조를 검증합니다.
- p.3: 공개 웹페이지에서 직접 제공 가능한 범위는 과제명·과제번호·연도·수행기관·연구기간·연구내용 250자 내외 등으로 제한돼 있습니다. 그 밖의 정보는 NTIS 상세페이지 링크를 사용해야 합니다. 상세페이지 로그인 필요: `https://www.ntis.go.kr/project/pjtInfo.do?pjtId={과제고유번호}`.
- 새 URI 예시 방식도 **404**라면 담당자에게 ① 실제 운영 API URL ② key 사용 승인의 서비스 종류 ③ 등록 IP 제한 ④ API 운영상태를 함께 문의합니다. 임의 대체 URL을 정식 API라고 단정하지 않습니다.

매뉴얼의 파라미터 표와 URI 예시는 표기가 서로 다르므로 현재 방식이 실제 배포 서버의 유일한 정답이라고 보증할 수 없습니다. 첫 승인·호출 성공으로 확정해야 합니다.

## 2026-10-14 두 공식 경로의 제한적 검증

사용자 제공 2025 매뉴얼 p.6의 실제 과제검색 END POINT
(`/rndopen/openApi/public_project`)가 HTTP 404를 보이면, 매뉴얼 p.4의
별도 **서비스 URL**(`/rndopen/openApi/pjtSearch/`)을 정확히 **한 번만** 추가
확인합니다. 대체 URL이 실제 과제검색 엔드포인트라고 가정하지 않습니다.
유효한 `RESULT/TOTALHITS/RESULTSET` 및 과제 필드가 반환되는 경우에만
조회가 성공했다고 기록하며, 둘 다 404이거나 두 번째 URL이 HTML 등
비정상 구조를 반환하면 오류 상태를 유지합니다. 요청에 사용한
인증키/전체 URL은 출력하지 않고, 성공 시 경로명만 기록합니다.


## 2026-10-14: NTIS registered PC IP versus GitHub Actions runner

The NTIS application registered a reporter's **PC public IP**. Standard GitHub
Actions Ubuntu runners use separate, changing egress IP ranges. HTTP 404 from
Actions is consistent with an IP allowlist issue, but is not proof that NTIS
uses HTTP 404 for IP denial. The uploaded NTIS manual does not specify an
IP-restriction error code.

### First test from the registered Windows PC

1. On the same Windows PC and internet connection used for NTIS registration,
   open https://api.ipify.org and privately verify the current public IP still
   matches the NTIS registered address. A VPN, mobile hotspot or network
   change may change the IP. Do not post it publicly.
2. Download and inspect [scripts/ntis_local_diagnostic.ps1](../scripts/ntis_local_diagnostic.ps1).
   The script uses only PowerShell built-ins, sends at most two NTIS requests
   to two URLs printed in the 2025 manual, and queries the manual's
   example keyword (나노).
3. Open PowerShell in the folder where you saved the file. For Downloads:

       cd "$env:USERPROFILE\Downloads"
       powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ntis_local_diagnostic.ps1"

   Inspect the file first; the process-scoped execution-policy switch does
   not permanently alter system-wide Windows policies.
4. At the hidden prompt, enter the approved NTIS API key. Do not type it into
   shell command history, GitHub Issues, or a ChatGPT message. The script
   transmits it over HTTPS to NTIS only, and does not save, echo or publish it.
5. Share only result labels such as DOCUMENTED_PATH_1: HTTP_404,
   DOCUMENTED_PATH_2: HTTP_404, or VERIFIED_RESULT_TOTALHITS_123.

### How to interpret the codes

- Registered PC returns valid official RESULT XML but Actions gets HTTP 404:
  narrow the investigation to cloud runner/IP/network restrictions; this
  supports, but does not prove, the egress-IP hypothesis.
- Both PC and Actions HTTP 404: ask NTIS about API approval, service URL,
  IP restrictions and current service state; do not infer that data is absent.
- PC HTTP 403: examine API approval, registered IP and authorization.
- HTTP 200 but unexpected HTML/XML: do not count it as zero projects.
- A valid RESULT with TOTALHITS=0 means only the current test keyword yielded
  no indexed results in that particular request.

For unattended collection, use an NTIS-approved fixed-egress-IP machine or
ask NTIS whether their service supports a different allowed access policy.
Never register one arbitrary GitHub-hosted runner IP as permanent. A
self-hosted runner on a public repository can expose secrets through unsafe
workflows and pull requests; seek security review before considering it.
