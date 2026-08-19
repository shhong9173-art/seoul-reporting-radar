// Source definitions kept separate so each district's public-information endpoints can be refined without rewriting the crawler.
// The crawler starts from the official homepage, then discovers likely public-information links.
export const PUBLIC_INFO_PATTERNS = [
  /보도자료|보도\/자료|뉴스|알림|소식/i,
  /고시|공고|입법예고|행정예고/i,
  /통계|데이터|현황|지표|자료실|정책자료/i,
  /예산|결산|재정|계약|입찰|수의계약|보조금/i,
  /위원회|회의|감사|감사결과/i,
  /주택|건축|도시계획|재개발|재건축/i,
  /교통|복지|안전|재난/i
];

export function isPublicInfoLink(text='') {
  return PUBLIC_INFO_PATTERNS.some(re => re.test(text));
}
