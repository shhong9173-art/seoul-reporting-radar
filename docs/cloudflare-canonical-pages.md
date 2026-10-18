# Cloudflare 빌드 복구와 운영 주소

2026-10-19 로그인된 Cloudflare 빌드 `13a17452`의 실제 오류:
`Missing entry-point to Worker script or to assets directory`.
기존 설정은 main에서 `npx wrangler deploy`, 다른 브랜치에서
`npx wrangler versions upload`를 실행하지만 저장소에 Wrangler 진입점이 없었다.
기존 Worker는 별도 정적 자산 배포였으며 API/비밀값/바인딩은 없었다.

`wrangler.json`이 `cloudflare/redirect.mjs`를 가리키도록 한다.
기존 workers.dev 주소의 GET/HEAD는 경로와 질의 문자열을 보존하여
https://shhong9173-art.github.io/seoul-reporting-radar/ 로 307 이동한다.
캐시하지 않는 임시 이동이므로 운영 변경/복구 시 브라우저에 영구 이동이 남지 않는다.
쓰기 메서드는 405로 차단한다. 저장소 원본 파일이나 별도 JSON 사본을 업로드하지 않는다.

운영 기준은 GitHub Pages이며 기존 Pages 수집·검증·배포 workflow는 유지한다.
PR 버전 업로드 성공은 운영 배포가 아니다. main 병합 후 Workers 배포 성공,
실제 307 목적지, Pages JSON의 새 검증 필드 및 브라우저 화면을 별도로 확인한다.
장애 시 Cloudflare Deployments에서 이전 배포로 복원할 수 있다.

공식 설정 근거: https://developers.cloudflare.com/workers/wrangler/configuration/
