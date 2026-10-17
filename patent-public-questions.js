/* Applies equally to retained historical records: no unpublished product questions. */
function patentPublicQuestions(number) {
  const label=/^[0-9-]{10,22}$/.test(number||'') ? '공개번호 '+number : '해당 공개 문헌';
  return [
    label+'의 제1항에서 확인할 수 있는 핵심 구성과 해당 문구는 무엇인가?',
    '공개 서지정보에 기재된 우선권·관련 출원·해외 패밀리 번호를 확인해 줄 수 있는가?',
    '이 기술의 제품·설비 적용을 이미 공개한 회사 발표가 있다면 발표일과 공개 URL은 무엇인가?',
    '종전 회사 발표와 달라진 내용이 공개 문헌에 있다면 문서 번호와 해당 부분은 어디인가?',
  ];
}
if(typeof module!=='undefined')module.exports={patentPublicQuestions};
