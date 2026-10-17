# Auto Desk 저장 충돌 복구 / 소스별 소유권 (2026-10-17)

## 실제 원인과 수집 구분

10월 17일 13:51~13:52 KST 운영 RSS 진단: 국내/해외 검색 19건 중 오류 0건, 검사 통과 기사 220건; 해외 전문매체 12건 중 오류 0건, 번역/중복제거 후 32건. 해외 검색 결과 0건인 6개 RSS 검색은 정상적으로 수행됐으며 쿼리 실패가 아님. 따라서 정상 RSS 공급처를 임의 교체하지 않는다.

반면 Auto Desk 실행 #39004131439, #38986470275 등 실패의 주요 원인은 `Commit updated feed, pitches, changes and archive` 단계. Scoop Radar Independent Refresh와 Auto Desk가 동일한 scoop.json, dart_numeric.json을 서로 다른 시점에 작성하면서 자동 rebase 중 충돌. Auto Desk는 작동 중 pitch_builder.py도 수정하고 이를 스테이징하지 않아 건강진단 별도 커밋의 `git pull --rebase origin main` 역시 'unstaged changes'로 실패했다.

## 변경

`scripts/publish_newsroom_outputs.py`에는 고정 파일 소유권 3가지가 있다.

- 뉴스 소유자: data.js, data.json, global.json, archive.json, changes.json, strategic_shifts.json, dart.json, pitch.json, industry.json, dig_today.json, dart_refresh_status.json 및 존재하는 dart_corp_codes.json.
- 단독 소유자: pre_scoop.json, scoop.json, dart_numeric.json.
- RSS 진단 소유자: digests/auto_news_feed_health_latest.json, digests/global_news_feed_health_latest.json.

뉴스 워크플로가 scoop.json 등 단독 소유 결과를 **업로드하지 않는 것**이 핵심. 스스로 생성한 수집 결과와 공식 근거 게이트가 통과한 경우만 파일을 올린다.

모든 업로드는 기존 작업 디렉터리와 완전히 분리한 임시 git worktree로 수행한다. 매번 원격 main을 새로 받아 고정된 허용목록 파일만 복사→staging→commit→fast-forward push. 다른 봇의 무관한 업데이트로 push 충돌 시 재원격 조회 후 새로운 임시 commit으로 최대 4회 재시도하고, 원본 작업 폴더의 unstaged 수정은 건드리지 않는다. rebase를 실행하지 않는다. 무관한 파일·인증키·소스코드를 업로드하지 않는다.

원천 RSS 수집 실패 시 본문 뉴스 게시 단계는 중단하되 건강진단만 `always()` 경로로 별도 게시한다. 그래도 뉴스 기사 0건/단독 0건은 주장의 근거가 아니다. 최종 GitHub Pages 배포는 검증된 출고 완료 후에만 진행한다.

## 검증

`tests/test_publish_newsroom_outputs.py`는 **실제 로컬 bare Git 저장소**로 (1) 뉴스/단독 파일 소유권 분리, (2) 원본 dirty 수정 보존, (3) 경쟁자의 원격 커밋에 따른 non-fast-forward 재시도, (4) 장애 RSS 진단 별도 게시, (5) data.js/data.json 불일치 차단을 확인한다. 새로운 원천 API 요청이나 GitHub Secret 추가가 필요 없다.
