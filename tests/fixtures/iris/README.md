# IRIS 공식 응답 발췌

2026-10-12 KST 읽기 전용 조회에서 확보했다. 개인 로그인·쿠키 없이 조회했다.

- `list.json`: `POST https://www.iris.go.kr/contents/retrieveBsnsAncmBtinSituList.do`, `pageIndex=1&prgmId=&ancmPrg=ancmIng`. 공고 목록과 paginationInfo만 보존.
- `detail.html`: `https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId=024237&ancmPrg=ancmIng`의 공고 메타데이터와 본문 영역. 첨부 목록·메뉴·스크립트 제외.
- `old-detail.html`: `https://www.iris.go.kr/contents/retrieveBsnsAncmView.do?ancmId=024199`의 동일 영역. 공고일은 9월 14일, 접수 마감은 10월 12일로 서로 다르다.

테스트는 기준시각을 2026-10-12 KST로 고정한다. 응답 발췌를 운영 데이터로 사용하지 않는다.
