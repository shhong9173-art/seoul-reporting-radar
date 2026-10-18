# KIPRIS 오류 22 재진단

## 확인한 사실

- 기준 main: `a0bd2ad7`. 10월 16일 실행 38867973860은 source 단계에서 실패했고 deep·claims 단계는 건너뛰었다. 오류 후 계속 호출한다는 가설은 이 실행에 해당하지 않는다.
- 당시 진단 JSON(91433865)은 오류 코드 22만 보존했다. 10월 17일 실행은 72시간 재시도 대기로 실제 조회하지 않았다. 진단 파일 생성 시각을 새로운 오류 응답 시각으로 볼 수 없다.
- 기존 source ledger의 3회는 도입 후 원자료 호출만 센 값이다. 심층/청구항 조회나 계정 전체의 누적 사용량·잔여 한도를 뜻하지 않는다.
- [KIPRIS 공식 FAQ](https://plus.kipris.or.kr/portal/bbs/Faq_info.do?buttonIndex=&pageIndex=2)는 Open API 월 1,000회 무료 호출을 안내한다. [공식 과거 답변](https://plus.kipris.or.kr/portal/bbs/view_Hdesk.do?bbsId=B0000019&hd_rcptno=20190618132932&menuNo=210131)은 `Limited Number Of Service Request Exceeds Error`를 호출 한도와 연결한다. 이 안내만으로 현재 계정의 요금제·소진량·초기화일은 확정하지 않는다.

## 이번 변경

- `ProviderResponseError`: 허용된 오류 메시지의 대소문자·공백·단복수 표기를 분류한다. 임의 오류 본문과 URL, 키는 저장하지 않는다. 코드 22만으로 호출 한도 초과를 확정하지 않는다.
- source ledger: 안전한 오류 분류와 실제 응답 시각을 보존한다. 대기 중 진단 갱신이 실제 재조회처럼 보이지 않도록 한다. 기존 원장의 이전 항목에 시각을 만들어 넣지 않는다.
- `SourceRequestMeter.get`: 실제 전송에 0.2초 간격 적용. 기존 fetch 래퍼 때문에 `search_applicant`의 함수 동일성 검사에 의존한 지연이 적용되지 않던 경로를 수정한다. 이는 속도 완화이며 월간 한도 복구를 보장하지 않는다.
- 격리 진단: 최근 7일 현대자동차 공개공보를 최대 1행, 1회 요청한다. 재시도·상세 조회·운영 JSON 변경은 없다. 성공 응답도 전체 수집 복구로 판정하지 않는다.
- 진단 Actions: 같은 저장소의 진단 코드 PR 또는 수동 실행만 허용. fork에는 비밀정보를 전달하지 않는다. 결과 artifact는 안전한 분류·건수만 포함한다. 녹색 체크는 진단 수행 완료이며 원자료 수집 성공은 `status`, `collectionRecovered`로 별도 판단한다.
- 특허 화면: 호출 제한 분류, 실제 오류 응답일, 자동 재조회 예정일을 표시한다.

## 검증 범위와 남은 작업

- 전체 Python 회귀 테스트 1,067개 통과(기존 공식 수집기 포함), 특허 화면 Node 검사 2개 스크립트 통과.
- [실조회 진단 실행 39151769596](https://github.com/shhong9173-art/seoul-reporting-radar/actions/runs/39151769596): 2026-10-19 02:55:21 KST, 요청 1회, `provider_rejected`, 코드 `22`, `request_limit_reported`. 실제 제공기관이 호출 제한을 응답한 것이 확인됐다. 인증 실패나 파싱 오류로 분류하지 않는다.
- 진단 원문/키는 출력하지 않았다. 안전한 결과 artifact ID 12145099062. `collectionRecovered=false`, `accountUsageVerified=false`. 신규 공보 및 단독 발굴 성과 없음.
- [공식 수수료 페이지](https://plus.kipris.or.kr/portal/use/paymentMmg.do?menuNo=200026)는 무료 호출을 매월 1일 초기화한다고 명시한다. 현재 계정이 무료인지 및 누적 호출량은 별도 확인해야 한다. 유료 이용 신청·결제는 수행하지 않았다.
- 진단 PR의 후속 코드/문서 커밋마다 반복 호출하지 않도록 `pull_request: types: [opened]`로 제한했다.

운영 특허 공보 및 아카이브는 변경하지 않는다. 실제 진단 결과·전체 테스트·PR·배포 결과는 확인 후 이 문서에 보충한다. 제공기관이 계속 요청을 거부한다면 계정 이용 상태 확인이 선행돼야 한다. 코드를 바꿨다는 이유로 복구 완료를 선언하지 않는다.

다음 우선순위는 원자료·심층·청구항 호출을 통합한 사용량 관리, 검증된 과거 비교의 재사용, 신규 공동출원 우선 검증이다. 최신 원자료 수집이 막힌 동안 과거 공보를 새로운 취재 성과로 올리지 않는다.
