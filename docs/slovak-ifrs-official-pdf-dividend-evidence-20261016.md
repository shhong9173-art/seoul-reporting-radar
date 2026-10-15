# 2026-10-16 — 기아 슬로바키아 IFRS 감사 원문 PDF 증거 추적

## 새 원천과 이전 시스템과의 차이

슬로바키아 재무부 RÚZ Open API 2.5는 회계 보고서 상세 `/api/uctovny-vykaz?id=...`에서 원본 PDF 첨부의 식별번호 `prilohy[].id`, 바이트 수 `velkostPrilohy`, 파일형식 `mimeType`, 공식 `digest` (SHA-256)를 제공한다. 공식 원문 다운로드는 `/cruz-public/domain/financialreport/attachment/<id>`이다. `/domain/financialreport/pdf/<id>`는 표 구조 데이터의 재출력 PDF일 수 있으므로 원본 IFRS 첨부와 혼동하지 않는다. 자료: https://registeruz.sk/cruz-public/home/api .

**대상 법인**은 Kia Slovakia s.r.o. 생산법인 IČO 35876832, 회계연도 2024 공식 결산번호 6499422/IFRS 보고번호 9718744, 2025 공식 결산번호 6995571/IFRS 보고번호 10298519로 엄격히 제한한다. 다른 기아 판매법인 IČO 35942894가 들어오면 중단한다.

## 자동화 흐름
1. 이미 공식 RÚZ 검색에서 확인한 동일 법인·결산번호·IFRS 보고번호·보고서 URL을 검증한다.
2. 해당 IFRS 보고서의 `/api/uctovny-vykaz?id=` JSON을 조회하고 결산번호와 연결되는지 확인한다. 정부가 일반 공개로 선언한 문서 중, 하나의 PDF 첨부와 공식 해시/파일크기 모두 확인되는 경우만 자동 다운로드한다. 중복 PDF 첨부라면 임의로 하나를 선택하지 않고 수동 확인으로 남긴다.
3. PDF 최대 14MB/문서, 페이지 최대 90쪽에 `pdftotext`를 적용한다. 정부가 제공한 바이트 크기 + SHA256가 모두 정확히 일치해야 원문 페이지 문맥을 사용한다. 키워드 'dividend', 'dividendy', 'retained earnings', 'nerozdelený zisk' 주변의 310자 이하 원문 단서를 최대 10건만 남긴다.
4. 원문에서 찾은 키워드/문장과 PDF 원본 링크, 문서 해시, 페이지 번호를 `digests/slovak_ifrs_primary_pages_latest.json`으로 게시하고 `crossborder-scoops.html` 취재 조사서에 연결한다. 전문 PDF 파일 자체는 GitHub에 저장하지 않는다.
5. 다운로드 실패·해시 불일치·비공개/스캔본·PDF 내 키워드 0건은 **배당금 0원, 배당 결의 없음, 실적 0원이라는 뜻이 아니다**. 구별된 상태 메시지로 남긴다.

## 기사화 기준

기아 DART 반기보고서(2026-09-16)에 기재된 'Kia Slovakia s.r.o.(KaSK)로부터 인식한 1,610,458백만원'은 **기아 회계상 배당수익 인식액**이다. 2024·2025년 슬로바키아 법인 재무제표에 'dividend'라는 단어가 등장한다고 해서 이 금액의 현금이 부모회사에 송금된 시점, 현지 이익 재원, 배당결의와 연결됐다고 자동 판단할 수 없다. 회계연도·지급주체·수익인식연도·별도/연결 기준·주석의 수치가 실제로 일치하는지 취재 검증 필요.

선행 언론보도의 동일 금액·동일 이슈 보도 여부, 현지 결의서 원문, 국내 공식 현금흐름 공시 및 공개 가능한 회사 확인이 나오기 전 `confirmedScoops`, `approvedArticles`는 **0**으로 유지한다. 자동 자료 확보 성공은 기사 확정이 아니다.

## 재현 테스트

`tests/test_slovak_ifrs_primary_pages.py`는 가짜 PDF/가짜 회계보고서 API를 이용해 파일 SHA 불일치, 다른 결산에 연결된 보고서, 다른 법인, 미공개/비정상 문서, 스캔 PDF를 검증한다. `tests/test_crossborder_source_gap_triage.py`는 원천 생성시각 불일치·금액 검증 미실시·현금 송금 미확인 플래그 유지 등을 테스트한다. PR 테스트 이후 실제 운영 재수집 결과와 공식 원문 PDF 접근·키워드 검출 상태를 별도로 점검한다.
