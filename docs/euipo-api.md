# EUIPO 상표 검색 API(유럽 출원) — 연결 메모

미국 USPTO(ID.me 인증 실패, 11-01)를 대신할 해외 상표 원천으로 EUIPO Trademark Search API를 붙이는 중이다.

## 키
- 운영 포털 dev.euipo.europa.eu에 앱 `radar-trademark`(기자 계정, 11-02)를 만들고 'Trademark search' 상품을 구독했다.
- GitHub Secrets: `EUIPO_CLIENT_ID`, `EUIPO_CLIENT_SECRET`(값은 저장소·대화에 남기지 않음). 탐침 워크플로(`probe/new-sources`)에만 넣어 둠.

## 주소(11-02 탐침으로 확인)
| 용도 | 운영 | sandbox |
|---|---|---|
| 토큰(OAuth client_credentials, scope `uid`) | `https://euipo.europa.eu/cas-server-webapp/oidc/accessToken` | `https://auth-sandbox.euipo.europa.eu/oidc/accessToken` |
| 상표 검색 | `https://api.euipo.europa.eu/trademark-search/trademarks` | `https://api-sandbox.euipo.europa.eu/trademark-search/trademarks` |

- `auth.euipo.europa.eu/oidc/accessToken`(공개 꾸러미 euipo-tm-client 기본값)은 운영에서 502다 — 11-02 오전 GitHub 러너·기자 컴퓨터 모두 502. 다른 공개 클라이언트들도 '죽은 주소'로 적어 둠.
- 검색 요청에는 `Authorization: Bearer <토큰>`과 `X-IBM-Client-Id: <client_id>`를 함께 보낸다. 질의는 RSQL(예: `applicants.name=="*HYUNDAI MOTOR*"`), `size` 10~100, `sort=applicationDate:desc`.

## 상태
- 11-02 12:0x probe 106·107: CAS 주소로 토큰 200(유효 7,200초). 상표 검색은 `403 Forbidden — Unauthorized request`(problems-registry `access-forbidden`).
- 추정(미확인): 운영 환경 상품 구독이 아직 승인되지 않았다. 기자가 포털에서 구독 상태(Active/Pending)를 확인하기로 함. 운영 승인에 신원 서류가 필요하다는 외부 메모가 있으나 EUIPO 공식 문서로는 확인 못 함.
- 연결(11-02, `scripts/euipo_trademarks.py`): `trademark_watch`가 같은 실행에서 유럽 구역(`eu` 칸)을 채운다. 회사 23곳(`data/trademark_watch.json`의 `euipo`), 출원일 120일, 회사당 검색 1회(30건, 출원일 내림차순). 403이면 '승인 대기'로 남기고 나머지 회사는 묻지 않는다(실행당 토큰 1·검색 1).
- 월요일 전체, 화~금은 직전이 완료가 아닐 때만(승인 대기·실패) — 승인되면 다음 평일 07:10에 첫 기준선이 잡힌다.
- 화면: `trademarks`에 '[유럽 상표 출원(EUIPO)]' 구역, 새 출원은 radar_today에 '유럽 상표 출원'(처음 보는 이름+업종 핵심 상품류 B, 그 밖 C).

## 대체 원천: Signa(11-09)
- EUIPO 구독이 일주일째 'Pending approval'이라 기자가 Signa(signa.so, 무료 요금제)에 가입해 키를 GitHub Secrets `SIGNA_API_KEY`로 넣었다(값은 저장소·대화에 없음).
- 탐침 202~206(11-09, `probe/new-sources`): `GET https://api.signa.so/v1/trademarks?owner_name=…&office=EM&filing_date_gte=…&sort=-filing_date&limit=100`. `limit` 최대 100, 검색 한 쪽 10크레딧(쪽 크기와 무관). 무료 요금제는 가입 10,000 + 월 1,000(응답 헤더 `X-Credits-Remaining`·`X-Credits-Reset`, 11-09 기준 초기화 12-09).
- `owner_name`은 이름 낱말로 넓게 맞춘다 — 'KG Mobility' ↔ 'Zweirad Union e-mobility … Co. KG', 'Lotte Chemical' ↔ 'LOTTE Fine Chemical', 'SK Innovation' ↔ 'SK Innovation Ventures GmbH'. 그래서 응답 출원인을 기존 `accept`·`exclude` 규칙으로 다시 거른다(SK이노베이션 `exclude: Ventures`, 포스코 `accept`에 'POSCO Co.' 추가).
- 2년(2024-11~) 유럽 출원이 탐침에서 잡힌 곳: 현대자동차·기아(현대차와 공동)·현대모비스·HL만도·넥센타이어·금호타이어·포스코·LS일렉트릭·LS전선·효성중공업·두산에너빌리티·LG화학. 0건: 한국타이어·현대제철·고려아연·HD현대일렉트릭·대한전선·한화솔루션·금호석유화학·S-OIL(정식 영문 이름으로도 0건 — 유럽 출원이 없거나 다른 이름).
- 마드리드 지정(W로 시작하는 번호)의 `filing_date`는 유럽 지정일이다(포스코 PosZET: 국제등록 2019, 유럽 지정 2026-07-22).
- 연결(`scripts/signa_trademarks.py`, `euipo_trademarks.run(signa_key=…)`): EUIPO 토큰 실패·403이면 그 회사부터 Signa로 읽고, 응답을 EUIPO 모양으로 바꿔 같은 기준선·새 출원·등급 규칙을 쓴다. 남은 크레딧 30 아래면 더 묻지 않는다(미확인). EUIPO는 실행마다 토큰 1·검색 1로 계속 확인해 승인되면 저절로 EUIPO로 돌아간다.
- 화면: `trademarks` 유럽 구역에 '원천: EUIPO 직접 조회는 구독 승인 대기 — Signa로 대신 읽음 n곳 · 남은 크레딧', 줄마다 '· Signa', radar_today 항목에 'Signa 2차 자료 — EUIPO eSearch 원문 확인'.
- 한계: Signa 약관 3.1 — 결과가 불완전·부정확할 수 있다. 5.1 — 무료 요금제는 예고 없이 바뀔 수 있다. 한 달 23곳 × 주 1회 ≈ 1,000크레딧이라 월요일이 다섯 번인 달은 모자랄 수 있다(가입 크레딧이 남는 동안은 괜찮음).

## 미국(USPTO)·조회 주기(11-09, 탐침 207)
- 미국 상표는 USPTO 직접 API가 ID.me 인증 실패(11-01)라 Signa(`office=US`)로만 읽는다 — 같은 23곳·같은 이름 규칙(`euipo.applicants`), 문서 'us' 칸, id `uspto:<일련번호>`, 원문 링크 USPTO TSDR.
- 2년(2024-11~) 미국 출원 수(탐침): 현대자동차 100+(공동 포함)·기아 56·고려아연 45·한화솔루션 36·포스코 10(그룹사 섞임 — 규칙으로 거름)·LS일렉트릭 6·금호타이어 5·HL만도 4·현대제철 3·효성중공업 2, 나머지 0~1.
- 유럽 0건 8곳 다른 이름: 'HYUNDAI STEEL'(2024년 6건)·'Hankook Tire Co'(2022년 1건)은 이름이 맞고 최근 출원이 없을 뿐. 고려아연·HD현대일렉트릭(옛 Hyundai Electric & Energy Systems)·대한전선(옛 Taihan Electric Wire)·금호석유화학·S-OIL은 5년 0건.
- 조회 주기(`euEvery`·`usEvery`, 주): 직전 남은 Signa 크레딧이 3,000 아래일 때만 쓴다(가입 크레딧이 남은 동안은 매주 다). 유럽 매주 7곳·2주 5곳·4주 11곳, 미국 매주 5곳(현대차·기아·고려아연·한화솔루션·포스코)·2주 4곳·4주 14곳 ≈ 월 99쪽(990크레딧, 무료 월 1,000). 안 물은 주는 직전 결과를 두고(`carried`) 화면에 '크레딧 아끼려 이번 주 안 물음 n곳'.
