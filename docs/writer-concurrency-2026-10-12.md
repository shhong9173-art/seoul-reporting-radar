# 취재 레이더 자동화 충돌 완화

## 관측된 오류
2026-10-12 Scoop Radar Independent Refresh 실행(38263354622)에서 수집/검증은 통과했으나 JSON 커밋 rebase가 실패했다.
main 자동 업데이트와 동시에 scoop.json 및 dart_numeric.json을 수정해 충돌한 것이 로그에서 확인됐다.
비슷한 이전 실행(38260565363)에서도 rebase 중 두 JSON 충돌로 종료됐다.

## 변경
- auto-desk.yml, scoop-radar.yml을 같은 GitHub Actions concurrency group인 newsroom-radar-writers로 설정.
- cancel-in-progress=false로 실행 중인 수집기가 종료될 때까지 다른 작성기를 대기시킴.
- 두 워크플로가 공유 파일을 동시에 쓰는 상황을 줄이고 JSON 반영 실패를 완화한다.
- 기존 수집기 기능, 단독 판단 규칙, 수집 대상·시간대는 변경하지 않는다.

## 한계와 관측
GitHub Actions는 같은 그룹에서 한 번에 실행 1개, 대기 1개만 유지할 수 있으므로
연속 트리거 중 오래된 대기 실행은 최신 대기 실행으로 대체될 수 있다.
다른 외부 커밋에 따른 충돌 가능성까지 제거한 것은 아니다.
변경 후 예정 실행을 확인해 실제 데이터 게시 성공률을 따로 검증해야 한다.
