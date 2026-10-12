# 관세청 추가 5개 API 통합·실데이터 검증

## 승인 서비스와 출처
| 내부 ID | 공공데이터포털 ID | 수집 범위 | 필드·단위 |
|---|---|---|---|
| `regional` | 15101641 | 울산(31)·충남(44)·경북(47), HS2 27·72·73·74·85·87 | `priodTitle` 연도, `hsSgn`, `expUsdAmt/impUsdAmt`, **천 달러** |
| `newtemper_country` | 15101607 | 미국·중국, 신성질별 8자리 품목 | `year` YYYY.MM, `godsCd`, `statCd`, `dlr`, **달러** |
| `newtemper` | 15101616 | 국가코드가 있는 모든 국가의 신성질별 8자리 품목을 같은 코드에서만 합산 | 같은 필드·달러 |
| `temper_country` | 15100476 | 미국·중국, 현행 성질별 5자리(일부 영문 포함) 품목 | `year`, `godsCd`, `dlr`, **달러** |
| `kind` | 15101634 | 수출·수입 종류별 국가 전체 금액 | `year` YYYYMM, `statCd`(종류코드), `dlr`, **달러** |

- 기존 HS4 통계, 10일 잠정치와 API 목록·결과 파일·UI를 분리한다.
- 신성질별과 현행 성질별 **분류가 서로 다르므로** 숫자를 더하거나 동일 코드로 매칭하지 않는다.
- 시도별 품목별 원자료에서 `priodTitle`은 **연도만 나타나므로**, 요청을 딱 한 달로 제한하고 수집 결과의 `period`는 요청한 연월로 표시한다.
- 기존 8종 API의 정상 응답: [8종 인증 서비스 개별 HTTP 검증](https://github.com/shhong9173-art/seoul-reporting-radar/actions/runs/38287206011).

## 첫 운영 전 격리 실데이터 검증
- [별도 브랜치의 5종 API 실제 수집 테스트](https://github.com/shhong9173-art/seoul-reporting-radar/actions/runs/38288885565)
- 확인 시각: 2026-10-13 KST. **2026년 8월 vs 2025년 8월 동월** 호출(다음 달 15일경 공표 지연 안전 여유).
- 실제 받은 2026년 8월 원본 행 수: 시도별 288 / 신성질별 국가별 2046 / 신성질별 38502 / 성질별 국가별 620 / 종류별 25.
- 5개 API 모두 실제 API 응답/연도·국가·구분 필드 검증 통과 및 9개 오프라인 테스트 성공.
- 이는 요청한 일부 시도와 국가에 대한 통계이며 한국 전체 지역별/국가별·회사별 전수조사 완료를 뜻하지 않는다.

## 데이터 처리와 검증
1. `CUSTOMS_API_KEY`는 GitHub Actions Secret으로만 읽고 공개 HTML/JSON·오류 로그에 저장하지 않는다.
2. 요청 기간은 전년 동월의 **동일 한 달**, 필수 결과코드 `00`와 원자료 행, 코드·기간·국가·수출입 구분을 검사한다.
3. 해당 API의 **정확한 분류코드·나라·방향·기간**이 일치할 때만 증감률을 계산한다. 미관측값·0분모는 증감률 미산출로 기록한다.
4. `year=총계` 및 `priodTitle=총계`는 제외해 이중 집계하지 않는다. 통화 단위는 API별 명시.
5. 키워드 필터와 상위 15건은 **관심 산업 부분집합**일 뿐 원자료 전체가 아니며 단독 기사/미보도 근거가 아니다.
6. 신규 월 미공표·파싱오류·필수 데이터 누락 등 실패는 결과 파일을 덮어쓰지 않는다. 호출은 최대 4개 동시·(연결 12초/읽기 75초) 타임아웃.
7. JSON의 수치가 전년 대비 상승했다는 것만으로 실제 기업 수주·생산·공급·원산지 변경을 추론하지 않는다. 보도여부와 기업 답변은 별도 취재.

## 운영
- `python -m unittest discover -s tests -p test_customs_five.py -v`
- `CUSTOMS_API_KEY=<local-secret> python scripts/customs_five.py --output /tmp/customs_five_probe.json`
- `Actions → Customs Five Statistics → Run workflow` (main) 또는 매월 16일/18일 11:30(KST).
- 정상 생성: `digests/customs_five_latest.json`(5개 서비스) → `data-lab.html`의 추가 관세청 섹션.
- 오류 발생 시 기존 JSON 보존, 새 자료가 없는데 0건·단독·최신 통계로 표시하지 않는다.
