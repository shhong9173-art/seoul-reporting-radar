# 선배 전수 AI 취재 키트: 본 기자 업무 통합판

기존 `seoul-reporting-radar`의 원자료 수집·단독 분류 체계를 유지하면서 선배가 제공한 **아침 공시 수집, 무역통계, 선행 보도 확인, 6종 취재 프롬프트**를 보조 모듈로 설치한다.

## 취재 순서
1. 평일 오전 06:50(KST) `.github/workflows/reporter-morning.yml`의 OpenDART 조회. `digests/YYYY-MM-DD.md`와 `digests/latest.json` 생성(첫 실행 후).
2. 홈페이지의 **아침 공시 브리핑**에서 신규 공시 접수번호와 우선 확인 유형을 보고 원문을 연다.
3. 동일 사건의 이전 공시, 기존 IR, 선행 기사(네이버·구글·더벨·딜사이트·전문지)를 검증한다.
4. `prompts/hunt.md`와 `prompts/balje.md`를 사용해 기사 야마, 수치, 회사에 확인할 질문 2~3개를 준비한다.
5. `prompts/check.md`로 문장별 팩트 검증, `prompts/gisa.md`로 기사, `prompts/desk.md`로 데스킹 점검, `prompts/graphic.md`로 그래픽 문구 작성.

## 본 기자 규칙이 우선
- 선배 원본 `ㅇ제목+5~9개 불릿`은 `prompts/senior_balje_reference.md`에 보존하고 실제 보고는 `*제목 (홍성효, HH:MM)`와 약 3개 항목이다.
- ★는 **보고서 유형의 우선 확인 표식**이지 미보도·단독이 아니다.
- 기존 수집기보다 독립되어 있으며 `scoop_scout.py`·`DIRECT_BEAT_COMPANIES`를 수정하지 않았다.
- 풍산·가온전선·제룡전기 등 비출입처 기업은 업로드된 선배 목록에서 그대로 복사하지 않았다.
- 공시 고유번호 확인 실패 업체는 '못 찾은 이름'으로 남기며 공시 0건으로 단정하지 않는다.
- AI 관계자 멘트 생성 금지. 실제 정책 파급·회사 영향은 원자료와 직접 기업 답변으로 검증한다.

## 선택 도구
- `scripts/customs.py`: HS 품목별 수출입 금액·중량. 실행 예: `python scripts/customs.py --hs 8504 --start 202501 --end 202609`. `CUSTOMS_API_KEY` 별도 필요. 관세청 원표·HS 범위 검증 필수.
- `scripts/news_check.py`: 네이버 뉴스 검색. 실행 예: `python scripts/news_check.py "현대차 공급계약"`. `NAVER_CLIENT_ID` 및 `NAVER_CLIENT_SECRET` 별도 필요. 검색 결과 0건이 미보도 확정은 아니다.
- `/hunt /balje /gisa /desk /check /graphic`은 파일 내용을 참고해 사용자가 입력하는 **취재 작업 지시**이지 웹사이트에서 실행되는 실제 슬래시 명령 시스템은 아니다.

## 비밀키·실행
기존 Actions Secrets의 `DART_API_KEY`를 재사용한다. `NTFY_TOPIC`은 선택사항이며 제3자 알림 서비스로 공시 제목이 전달될 수 있으므로 비공개·긴 토픽을 사용한다. API 키를 코드나 digest로 출력하지 말 것.

새 파이프라인은 GitHub Actions의 **Reporter Morning DART Digest**를 한 번 수동 실행해 실제 OpenDART 조회·digests 생성·Pages 표시를 확인한 뒤 일일 운영 결과를 평가한다. 저장된 코드와 오프라인 테스트 통과는 실제 API 수집 성공과 다르다.

## 신규: 공시 근거 비교·기존 기사 후보·통계 검증

- `scripts/review_engine.py`가 `digests/latest.json`을 읽어 `digests/review_latest.json`을 생성한다.
- **동일 공시 접수번호와 회사가 모두 일치하는** `dart_numeric.json`의 원문 수치와 발행인 정정표만 합친다. 단순히 회사와 보고서 유형이 같다는 이유로 별도 계약을 연결하지 않는다.
- 정정표의 before/after는 발행인이 정정 문서에 기재한 차이이며, 원공시를 별도 조회해 독립 검증한 값이 아님을 표시한다.
- 분류는 `정정표 변경 검토`, `원문·변경 사실 확인`, `공개자료 추적`, `정례 공개·후순위` 네 단계. 자동 단독 확정, '이미 보도됨' 확정, 발제 확정은 금지한다.
- 선행 기사 검색은 NAVER API 키가 있으면 네이버, 없으면 최근 30일 Google News RSS로 시도한다. 결과가 없거나 사이트가 막혀도 미보도 확정이 아니고, 검색 결과가 있어도 동일 사건이라고 확정하지 않는다. 1회 실행당 기업·이슈 10개 조합으로 제한한다.
- `python scripts/review_engine.py --no-news`로 외부 요청 없이 공시 수치·정정표 근거만 갱신할 수 있다.
- 관세청 원표 CSV에 한해 `python scripts/trade_trends.py data/customs_8504_ALL_202501_202609.csv --year 2026`으로 **동일 HS 코드·동일 월** 수출액, 물량, 수출단가(USD/kg)를 비교한다. 연결되는 기업 계약·생산수치 등은 추정하지 않는다.
- 본 단계는 '기자의 발제 가능 여부 자동 확정'까지 구현한 것이 아니다. 원공시의 독립 비교와 동일 사건 확인, 회사 직접 답변은 후속 취재 및 별도 개발 과제다.
