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
- 검색이 열리면: `trademark_watch`에 유럽 출원 구역(출입처 영문 출원인 이름, 최근 90일, 주 1회)을 붙인다. 호출 한도(외부 메모: 앱당 하루 25,000회)는 공식 확인 뒤 정한다.
