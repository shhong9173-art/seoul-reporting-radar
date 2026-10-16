# KIPRISPlus 22 관측 후 자동 재요청 간격 (2026-10-16)

공식 API 상태 페이지(2026-10-16 16:02 KST)는 공개·등록 특허 공보 서비스에 응답 지표를 표시하지만 **사용자 인증키의 서비스 승인과 성공을 증명하지 않는다**. 기존 GitHub Actions의 KIPRISPlus 첫 출입처 호출은 XML resultCode=22로 중단되었다. 이 응답코드가 특정 쿼터/서비스 승인 문제라는 공개 공식 근거는 아직 없다.

코드: 최초 오류 응답코드 22를 받은 실행에서 보수적 72시간 자동 재확인 대기(backoff)를 키 없이 공개 장부에 기록한다. 대기 중 스케줄은 **API 호출 0회**이며 이전 검증 특허 데이터를 보존하고 상태 파일에 24개 회사 provider_22_probe_cooldown 표시, **신규 특허 0건으로 판정하지 않는다**. 기간 경과 후 한 번 다시 실제 호출해 원인 지속 여부를 확인한다. 성공한 전체 출입처 공식 수집에 한해 backoff 지운다.

GitHub Actions 수동 Run workflow의 force_provider_probe는 긴급 수동 확인에 한해 허용한다. 실행당/월 소스 API 호출 한도를 무시하지 않는다. 계정 전체 API 호출량·결과코드 정확한 의미는 제공기관 공식 관리화면과 담당자 확인이 필요하다.

공식 상태: https://plus.kipris.or.kr/portal/main/apiStatus.do?menuNo=210157
이용문의: https://plus.kipris.or.kr/portal/bbs/list_Hdesk.do?bbsId=B0000019&menuNo=210131
