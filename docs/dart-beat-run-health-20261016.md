# 산업부 DART 자동수집 실행 상태와 마지막 정상 데이터 분리

## 문제

전체 48개사 DART 스캐너는 정상 데이터 파일을 `digests/dart_beat_monitor_latest.json`에 저장합니다. 다만 GitHub Actions의 DART API 또는 발행회사 고유번호 ZIP 조회가 실패했을 때 **마지막 정상 JSON이 그대로 존재**하므로, 이 파일만 보면 금일 공시 0건과 마지막 실행 실패를 구별하기 어렵습니다.

## 새 실행 상태 증거

- `scripts/dart_beat_run_health.py`는 성공·실패·건너뜀·취소의 **GitHub Actions 단계 결과**만 받아 `digests/dart_beat_run_health_latest.json`에 기록합니다. 인증키나 응답 본문/에러 URL은 포함하지 않습니다.
- 공식 회사 목록 스캐너가 오류로 종료돼도 저장된 마지막 정상 파일을 삭제하거나 0건으로 덮지 않습니다. 마지막 데이터의 생성시각, 법인코드 확인 회사 수, 누락 수, 원문 미검토 수를 상태파일에도 반복해 보여줍니다.
- 회사 고유번호 ZIP 갱신만 실패했지만 기존 확인 코드로 공식 공시 조회가 성공한 경우는 `official_list_published_registry_refresh_incomplete`로, 공시 본문 스캔 또는 결과 게시가 실패한 경우는 `failed_or_skipped_last_execution_old_data_preserved`로 구분합니다.
- 전체 수집 후 `git fetch origin main; git reset --hard origin/main`로 실패해서 원격 저장소에 **게시되지 않은 부분 원문 결과·로컬 임시 커밋을 버리고**, 오직 실제 `main`에 남은 마지막 정상 데이터를 기준으로 실행 상태를 게시합니다. 다른 공식자료를 덮어쓰지 않습니다.
- 홈페이지는 상태 파일이 없거나 공식 데이터 시간과 서로 맞지 않으면 **검증 미완료**라고 표시합니다. 마지막 API 실패를 신규 공시 0건이라고 설명하지 않습니다.
- Actions는 이미 기존 공시/산업부 수집 워크플로와 같은 concurrency 그룹을 사용합니다. **수집 중 오류가 나도 건강상태 기록 단계에 도달**하되, 원래 공식 수집 작업은 실패 상태로 남아 경고를 지우지 않습니다.

## 테스트

`tests/test_dart_beat_run_health.py`에는 작업 실패/고유번호 일부 실패/전체 성공, 오래된 데이터, 비정상 상태문구, 잘못된 JSON, `if: always()` 및 `git reset --hard origin/main` 검증이 있습니다. 실제 2026-10-15 실행분은 48개사 중 43곳 정상 조회·5곳 코드 미확인·30건 공개문서·원문 4건 대기였으며, 새로운 조회 결과가 아니므로 계속 이전 시점을 명시해야 합니다.

이 작업은 보도 독점 여부나 실제 사업 영향에 대한 근거가 아닙니다. 공시 내용의 최초 공개 날짜 및 선행기사 내용은 별도 확인해야 합니다.
