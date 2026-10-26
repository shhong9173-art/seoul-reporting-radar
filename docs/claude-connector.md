# Claude 커넥터(MCP) — 매의눈식 취재 도구

선배 매의눈의 3층 구조(수집 → Claude가 부르는 도구 → 취재 절차 스킬)를 이 레이더에 맞춰 옮긴 것이다.

| 층 | 선배 매의눈 | 이 레이더 |
|---|---|---|
| 수집·대조 | 서버 프로그램 | GitHub Actions 수집기(기존) + `scripts/radar_tool_views.py`가 만드는 `tools/*.json` |
| 도구 | MCP 도구 43개 | Cloudflare 워커 `/mcp` (아래 16개) |
| 절차 | hunt·paper·desk·balje·gisa 스킬 | radar-hunt·radar-balje·radar-desk 스킬(기자 계정에 저장) |

## 주소와 권한

- 공개 연결: `https://seoul-reporting-radar.shhong9173.workers.dev/mcp`
  공개 자료(이미 GitHub Pages에 공개된 레이더 결과)만 읽는다. 구글 뉴스 대조, 원문 열기, 후보 점검 가능.
- 기자 전용 연결: `https://seoul-reporting-radar.shhong9173.workers.dev/mcp/<MCP_ACCESS_TOKEN>`
  DART 실시간·네이버 뉴스·나라장터 실시간과 비공개 저장소(취재 패키지·후보·판정 기록)가 열린다.
  토큰이 틀리거나 등록 전이면 404를 돌려준다.
- 저장소와 Pages는 공개다. 취재 패키지·킬 사유·후보는 저장소에 쓰지 않고 워커의 비공개 저장소(Durable Object, SQLite)에만 둔다.

## 도구

공개: `radar_big_picture`, `radar_clues`, `radar_stats`, `dandok_monitor`, `radar_health`, `news_check`,
`source_document`, `candidate_check`

기자 전용: `dart_filings`, `dart_find_text`, `g2b_bids`, `scoop_packages`, `package_save`, `candidate_submit`,
`candidate_feedback`, `candidate_weekly_review`

선배 도구 중 옮기지 않은 것: `paper_db`(지면 DB — 지면 원천 데이터가 없음), 식품안전나라·CJ 지배구조·
가맹·상표 도구(식품팀 전용), KOSIS·ECOS·SGIS(이 레이더에 수집기가 아직 없음).

## 원칙(코드로 강제)

- 조회 실패·미설정·일부 성공은 0건이 아니라 미확인으로 돌려준다. `news_check`는 채널별 상태를 따로 적는다.
- 뉴스 색인 0건은 `색인 0건 — 미보도 증거 아님`, 유사 제목은 `같은 사건인지 원문 확인 필요`로만 표시한다.
- 출처가 붙인 단계(공개 원자료 추적 / 취재 단서·단독 미확정 / 단독 후보)를 도구가 올리지 않는다.
- `candidate_check`는 원문 URL·게시일·내용 해시, 보도 3채널 조회, 이미 났나 판정, 질문 2~3개, 비교가 없으면
  `조사대기`로 돌린다. 제목 숫자는 원문 수치나 허용 계산 5종(증감률·차이·비중·합계·단위환산)만 통과.
- 점수(가점·감점)와 지면감(새로움·숫자·판·출입처·시점·확장·독점 0~2)은 정리용이다. 단독 판단은 기자가 한다.
- `source_document`는 공식 기관·DART·KIND·KIPRIS·.gov·EU·출입처 홈페이지만 열고 내용 해시를 준다.

## 설정(기자가 할 일)

1. 이 PR과 `tools/*.json` 생성 PR을 병합한다. main 병합 시 Cloudflare가 워커를 배포한다.
2. Cloudflare 대시보드에서 이 워커의 비밀값(Variables and Secrets)에 추가한다.
   - `MCP_ACCESS_TOKEN`: 32자 이상 무작위 문자열(영문·숫자·`-`·`_`). 기자 전용 주소의 열쇠.
   - `DART_API_KEY`: GitHub Secrets에 쓰는 것과 같은 OpenDART 키.
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 네이버 뉴스 검색. 새로 받는 키는 네이버 클라우드 플랫폼 NAVER API HUB(Application 등록에서 '뉴스' 선택 → [인증 정보])에서 발급한다. 개발자센터 신규 신청은 막혔다. 서버는 HUB 방식으로 먼저 호출하고, 거부(401·403)될 때만 예전 개발자센터 방식으로 다시 호출한다.
   - `G2B_API_KEY`(또는 `DATA_GO_KR_KEY`): 공공데이터포털 일반 인증키.
3. Claude 설정의 커넥터에서 사용자 지정 커넥터를 추가하고 기자 전용 주소를 넣는다.

키 값은 응답·로그·저장소 어디에도 출력하지 않는다.
