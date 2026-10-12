# 자동차 산업부 취재 레이더

자동차·부품·배터리 담당 기자용 뉴스 모니터링 대시보드입니다.

## 테스트
수집 파이프라인 즉시 실행 테스트용 커밋입니다.

## 기능
- 오늘 꼭 볼 것 / 단독·속보 후보 / 후속 취재 후보 / 전체 모니터링
- 완성차 / 부품 / 배터리 / 정책·관세 / 중국차 / 노조·생산
- 주요 자동차·배터리 기업 필터
- Google News RSS 기반 최근 72시간 자동 수집
- 기사 중복 제거 및 이슈 클러스터링
- 최초 관측 매체·보도량·커버리지 공백 표시
- 취재가치·후속취재 가치 점수
- 원문 링크 중심 모니터링

## 자동 갱신
`.github/workflows/auto-desk.yml`이 30분마다 `collector.py`를 실행하고 `data.js`를 갱신합니다. `data.js` 변경은 workflow 재실행 대상에서 제외합니다.

## 주의
‘단독 후보’는 기사형 단독 표기를 탐지한 후보이며 실제 단독 여부를 보증하지 않습니다. 기사 작성 전 원문과 취재원 확인이 필요합니다.

## 선배 취재 키트 기반 확장
- 출입처별 아침 공시 브리핑: [`morning.html`](morning.html) 및 `digests/latest.md` (첫 자동 실행 이후 생성).
- 독립 일정: `.github/workflows/reporter-morning.yml`, 평일 06:50 KST, 기존 `DART_API_KEY` Secrets 사용.
- 원자료 → 이미 보도 확인 → 본 기자 발제 → 팩트체크: [`reporter_kit/README.md`](reporter_kit/README.md)
- 관세청·네이버 API 도구: `scripts/customs.py`, `scripts/news_check.py` (별도 키 필요).
