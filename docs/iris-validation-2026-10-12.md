# IRIS 직접 수집기 정상화 검증

## 점검 기준과 기존 구현

- 기준 main: `47ccf54c2c1999b0f3fc32f6f5b4546e103d4ab0` (2026-10-12 09:19 KST). 독립 브랜치: `fix/iris-official-announcements`.
- 인수인계의 주요 Python/JS/HTML/CSS/JSON 및 두 workflow 파일 모두 존재한다. 기존 AGENTS.md는 없어 신설했다.
- `auto-desk.yml`: 뉴스 수집 → 국내외 산업 데이터 → DART/수치 → 변화/전략/조사 → 아카이브 → 발제 → GitHub Pages. 실제 cron은 15분 간격이다. README의 30분 설명은 오래됐다.
- `scoop-radar.yml`: 회귀 테스트 → `pre_scoop_radar.py` → DART 수치 → `scoop_scout.py` → JSON 검증/갱신 → Pages. 독립 갱신은 매시 7·37분이다.
- `index.html`은 data.js, app.js, dashboard.js, pitch.js, scoop.js 등 기존 화면을 로드한다. dashboard_v2.js는 존재하지만 현재 index에서 직접 로드하지 않는다.
- `pre_scoop.json.directSourceDiagnostics`가 `scoop.json.sourceHealth.preScoop.directSourceDiagnostics`로 전달된다. 기존 진단 연결 구조를 유지했다.
- 기준 데이터는 인수인계와 일치: 공식 원자료 174, 단독 후보 0, 미확정 단서 0, 공개 추적 1, 단서 심사 입력 172, 출입처 제외 114, 노이즈 제외 52. 이 수치는 기존 저장 데이터이며 전체 파이프라인을 새로 실행한 결과가 아니다.
- 직접 출입처 화이트리스트·공개자료/단서 분리·DART 원문·IRIS/NTIS/NLRC 직접 수집 코드가 존재한다. 존재 여부를 전체 기능의 정확성 검증으로 간주하지 않는다.

## 정확한 실패 원인

기존 목록 `https://www.iris.go.kr/contents/retrieveBsnsAncmListView.do`의 실제 HTML은 `onclick="f_bsnsAncmListForm_view('024199','2026','S051100',...)"`로 상세 식별자를 전달한다. 기존 정규식은 상세 href의 `ancmId=`, JS의 `ancmId=/:`, `data-ancm-id`만 찾으므로 ID가 존재해도 0개로 판정했다. `listUsesJsOrAjax=True`는 당시 실제 Ajax 조회 결과가 아니라 ID가 없다는 이유로 설정되던 값이다.

또 실제 상세 페이지는 `공고일자`가 `공고명`보다 먼저 나오며 공고명 다음에는 세부내역명·사업공고명 등이 배치된다. 기존 제목 정규식의 종료 표지(공고일자/재공고 여부/공고번호)는 실제 순서와 맞지 않는다. 전체 페이지 앞부분을 요약하면 메뉴가 본문에 섞이는 문제도 있었다.

공식 `bsnsAncmList.js`의 구형 목록 갱신 코드는 `...BtinSituListView.do`에 JSON을 기대하지만 실제 응답은 HTML이었다. 현재 메뉴의 `bsnsAncmBtinSituList.js`를 확인해 실제 JSON 경로 `POST /contents/retrieveBsnsAncmBtinSituList.do`를 검증했다. 구조는 `listBsnsAncmBtinSitu`와 `paginationInfo`이며 각 항목의 `ancmId`·`ancmDe`·`ancmTl`을 제공한다.

## 수정 내용

- `pre_scoop_radar.py`: `fetch_direct_iris_announcements`를 공식 JSON 조회로 변경. `ancmIng`/`ancmEnd` 각 최대 2페이지, 상세 최대 30건, 보존 최대 10건. 목록의 실제 공고일로 조회 우선순위를 정한다. 접수 마감일은 사용하지 않는다.
- `_iris_request`/`_iris_fetch`: 공식 폼 POST와 상세 GET, 요청당 12초 제한. 전송 오류·429·5xx에 한해 1회 재시도. 403·파싱 오류 등을 재시도로 숨기지 않는다.
- `parse_iris_detail`/`_IrisBodyParser`: 라벨 기반 메타데이터 및 `tb_contents` 본문 추출. 공고명·공고일·접수기간·사업명·명시된 지원대상을 구조화한다. 없는 필드는 빈 값으로 남긴다. 지원대상 표의 원문을 그대로 보존하며 금액을 별도로 만들어내지 않는다.
- `_iris_company_mentions`: IRIS에 한정해 정확한 이름 경계를 검사하고 글로벌 BMW를 BMW코리아로 치환하지 않는다. 본문의 단순 언급은 `mentionedCompanies`로 분리하며 참여·선정으로 해석하지 않는다. 기존 직접 출입처 목록과 하위 필터는 변경하지 않았다.
- 날짜 누락/오류/범위 밖, 목록-상세 제목·날짜 불일치, 본문 없음, 산업 무관, 중복 ID, 잘못된 ID, 전송/구조 오류를 분리해 진단한다. 조회 제한과 `collectionComplete=False`를 명시한다.
- URL은 공식 공유 경로 `/contents/retrieveBsnsAncmView.do?ancmId=...&ancmPrg=...`를 사용한다. ID는 공식 JSON에서 확인한 숫자 문자열만 허용한다. 0으로 시작하는 ID를 보존한다.
- `tests/test_official_collectors.py`, `tests/fixtures/iris/*`: 실제 JSON/HTML 발췌로 날짜·마감일·본문·순서·중복·범위·오류·비출입처 필터 회귀 검증. 기존 가상 IRIS 응답 테스트를 실제 응답 기반으로 교체했다.
- `tests/diagnose_iris.py`: 운영 파일을 쓰지 않고 IRIS만 조회해 진단과 기존 출입처 함수의 판정을 JSON 표준출력으로 제공한다.
- `AGENTS.md`: 인수인계의 지속적 개발 원칙을 간결하게 기록했다.

## 실제 검증 결과

실행: Python 3.12, Windows. 수정 전 8개 테스트 통과. 수정 후 23개 테스트 통과, 실패 0개(기존 8개 + 신규 15개). 처음 추가한 테스트 중 ‘로그인’이라는 단어를 무조건 메뉴로 간주한 검증은 실제 신청 안내 본문에도 해당 단어가 있어 실패했다. 본문 외부에 넣은 고유 문구가 유입되지 않는 방식으로 테스트를 바로잡았다.

```text
python -m unittest discover -s tests -p 'test_official_collectors.py' -v
python tests/diagnose_iris.py
```

2026-10-12 09:46 KST 수정 후 공식 사이트 직접 조회 결과:

| 항목 | 수정 전 직접 재현 | 수정 후 |
|---|---:|---:|
| 목록 HTTP 조회/구조 파싱 | HTML 1회 / ID 0 | JSON 4페이지 / 4페이지 |
| 검증된 상세 ID | 0 | 39 |
| 상세 요청/HTTP 성공 | 0 / 0 | 30 / 30 |
| 정상 공고일 추출 | 0 | 30 |
| 최근 21일 공고 | 판정 불가 | 7 |
| 산업 관련 공개자료 보존 | 0 | 2 |
| 직접 출입처 확인 자료 | 판정 불가 | 0 |
| 오래된 자료 제외 | 판정 불가 | 23 |
| 최근 자료 중 산업/기업 조건 미충족 | 판정 불가 | 5 |
| 전송 오류 / 재시도 | 0 / 0 | 0 / 0 |

접수 중 공고는 19건/2페이지 모두 목록 조회했다. 마감 공고는 19,098건/1,910페이지 중 앞 2페이지만 조회했다. 합계 39개 ID 중 상세는 30개를 확인했고 9개는 한도 때문에 미조회했다. 그러므로 **조회 경로 정상화는 확인했지만 전체 최근 공고의 완전 수집은 보증하지 않는다.** 세부 결과는 `iris-validation-2026-10-12.json`에 기록했다.

보존된 공개자료:

1. [2026년 3차 전력정보화 및 정책지원사업(재생에너지분야) 신규지원 대상과제 공고](https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId=024277&ancmPrg=ancmIng): 공고일 2026-09-29.
2. [2026년도 소재부품기술개발사업(4차) 신규지원 대상과제 공고](https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId=024237&ancmPrg=ancmIng): 공고일 2026-09-22. 원문은 2026년 선정 으뜸기업 6기 전용 공모라고 명시하지만 여기서 담당 기업의 선정 사실을 추정하지 않았다.

두 자료의 직접 출입처 기업은 기존 `direct_beat_company_hits`에서도 빈 목록이다. 일반 공모를 단독 후보로 만들지 않았다. 회사 없는 공모 및 삼성전기·포스코퓨처엠·포스코인터내셔널 공모에 대한 기존 `build_lead_signals` 제외 결과도 오프라인 검증했다. 전체 언론 검색·단독 생성 파이프라인을 실행해 검증한 것은 아니다.

실제 실행 전후 저장소 루트 JSON과 data.js의 SHA-256이 모두 일치했다. 운영 데이터·아카이브 수정, 전체 파이프라인 실행, main 병합, 배포는 하지 않았다.

## 운영 주소와 GitHub 상태

- 운영 기준: https://shhong9173-art.github.io/seoul-reporting-radar/ . HTTP 200, 자동차 대시보드 HTML 확인.
- 공개 `scoop.json`: HTTP 200, 생성 시각 2026-10-12 09:17:43 KST. 기준 main 파일과 바이트 단위 일치.
- 두 workflow는 저장소 루트를 Pages artifact로 올리고 `actions/deploy-pages@v4`로 배포한다. 현재 저장소 코드에서 workers.dev 참조는 찾지 못했다. 과거 배포본의 주소·폐기 여부는 확인되지 않았다.
- 브라우저 렌더링·상호작용까지 확인한 것은 아니며 이번 수정의 배포 화면 반영은 미검증이다.
- 작업 브랜치 `fix/iris-official-announcements`에서 PR로 검토한다. main에 직접 반영하지 않는다. 기존 workflow에 pull_request 트리거가 없어 PR 생성 자체로 이 테스트가 Actions에서 자동 실행되지는 않는다.

## 남은 문제와 후속 우선순위

1. **출입처 기준 불일치:** 태광·동성케미칼·DL케미칼이 직접 화이트리스트에서 빠져 있다. 세아제강·동국제강은 기존 포함 상태이며, 세아씨엠·동국씨엠·효성중공업·일진전기도 추가돼 있다. 화이트리스트 도입 커밋 `57b71e2` 및 확대 이력은 존재하지만 해당 기업의 실제 출입처 인정 근거는 코드/커밋 설명만으로 확인하지 못했다. 기존 BMW 글로벌/국내법인 정규화도 별도 검증이 필요하다. 이번 IRIS 수정에서 임의로 목록을 바꾸지 않았다.
2. **IRIS 누락 가능성:** 한도 밖 목록/상세, 공고 예정 탭, 첨부 HWP/PDF, 이미지 공고문은 미수집. 본문 기업명도 엄격한 경계 검사로 조사 결합·다양한 별칭을 놓칠 수 있다. 제목이 일반 연구사업이고 본문에만 산업 연관성이 있는 경우 현재 제목 필터에서 제외될 수 있다. 목록/상세 불일치는 조용히 수용하지 않고 제외한다. 필요시 검증된 날짜 필터·증분 수집과 첨부문서 분석을 후속 PR로 진행한다.
3. **NTIS:** 기준 저장 데이터에서 상세 8회 시도 중 4회 성공, 4회 타임아웃. 실패 유형별 재시도·타임아웃·공식 조회 경로를 다음 작은 작업으로 개선한다. 이번에는 재실행하지 않았다.
4. **DART:** 기준 저장 데이터에서 수치 추출 12건 중 7건 성공/5건 실패. 단위 패턴 불일치와 원문 파일 없음 등 원인을 분리한다. 기존 테스트에서 발생하는 정규식 FutureWarning도 후속 과제다. 이번에는 코드를 변경하지 않았다.
5. **KIPRIS:** 검색엔진 의존에서 공식 상세/구조화 데이터로 강화하되 기술 차이·적용/양산 근거를 함께 검토한다.
6. **비교 엔진:** 기존 계약·공장·기간·금액·물량과 신규 원문을 사건 단위로 비교하고 기존 기사와 같은 사건인지 검증한다. 정정 공시나 단순 공개 공고를 신규 단독으로 올리지 않는다.
7. **후속 배포 검증:** PR 병합 이후 Actions → pre_scoop/scoop JSON → 실제 Pages 화면까지 별도로 확인한다. 이번 단계는 수집기 코드·회귀 테스트·읽기 전용 실조회 검증의 완료이며 운영 반영 완료가 아니다.
