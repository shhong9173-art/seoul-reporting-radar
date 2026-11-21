// 베트남어·인도네시아어 무역구제 소식 줄 낱말 풀이(11-21 기자 "다음 업데이트 계속 진행해").
// 베트남 TRAV·인도네시아 KADI 목록 감시는 그 나라 말 제목을 그대로 보여 줬다 — 11-16 'thép mạ … Trung Quốc và Hàn Quốc'(한국·중국산 도금강판
// 반덤핑 범위 재심 신청 접수)가 무엇인지 줄만 봐서는 알 수 없었다. 번역이 아니라 아는 낱말만 짚는다(문장 뜻·누가 거는 조치인지는 원문).

const VI = [
  // 절차(앞에서부터 — 구체적인 것 먼저)
  [/rà soát phạm vi/i, '범위 재심(대상 품목 범위)'], [/rà soát cuối kỳ/i, '일몰(종료) 재심'], [/rà soát hành chính|rà soát lần/i, '행정 재심'],
  [/chống lẩn tránh/i, '우회 방지'], [/khởi xướng/i, '조사 개시'], [/kết luận sơ bộ/i, '예비 판정'], [/tạm thời/i, '잠정'],
  [/kết luận cuối cùng/i, '최종 판정'], [/chính thức/i, '확정(정식)'], [/gia hạn/i, '기한 연장'], [/chấm dứt|kết thúc/i, '종료'],
  [/tiếp nhận[^.]{0,40}hồ sơ/i, '신청서 접수'], [/bản câu hỏi|bảng câu hỏi/i, '질문서'], [/tham vấn công khai|phiên tham vấn/i, '공개 협의(공청회)'],
  [/miễn trừ/i, '적용 면제'], [/rà soát/i, '재심'],
  [/chống bán phá giá/i, '반덤핑'], [/chống trợ cấp/i, '상계관세'], [/tự vệ/i, '세이프가드'],
  // 품목
  [/thép mạ màu|tôn màu/i, '컬러강판'], [/thép mạ/i, '도금강판'], [/thép cán nguội/i, '냉연강판'], [/thép cán nóng/i, '열연강판'],
  [/thép không gỉ/i, '스테인리스강'], [/cáp thép/i, '강연선(강선 케이블)'], [/thép hình/i, '형강'], [/thép/i, '철강'],
  [/nhôm/i, '알루미늄'], [/sợi/i, '섬유'], [/phân bón/i, '비료'],
  // 나라
  [/hàn quốc/i, '한국'], [/trung quốc|trung hoa/i, '중국'], [/đài loan/i, '대만'], [/nhật bản/i, '일본'], [/ấn độ/i, '인도'],
  [/thái lan/i, '태국'], [/malaysia/i, '말레이시아'], [/indonesia/i, '인도네시아'], [/hoa kỳ/i, '미국'],
];
const ID = [
  [/dimulainya penyelidikan|inisiasi|pemberitahuan penyelidikan/i, '조사 개시'], [/peninjauan kembali|\breview\b/i, '재심'],
  [/laporan akhir/i, '최종 보고서'], [/sementara/i, '잠정'], [/perpanjangan/i, '연장'], [/dengar pendapat/i, '공청회'],
  [/penghentian|dihentikan/i, '종료'], [/bea masuk anti ?dumping|\bBMAD\b|anti ?dumping/i, '반덤핑'], [/imbalan|subsidi/i, '상계관세'],
  [/tindakan pengamanan|safeguard|\bBMTP\b/i, '세이프가드'],
  [/canai panas/i, '열연'], [/canai dingin/i, '냉연'], [/lapis seng|galvan/i, '아연도금'], [/tahan karat|stainless/i, '스테인리스'], [/baja/i, '철강'],
  [/korea/i, '한국'], [/tiongkok|china/i, '중국'], [/taiwan/i, '대만'], [/jepang/i, '일본'],
];
const LANG = { 'vn-trav': ['베트남어', VI], 'id-kadi': ['인도네시아어', ID] };

// pageId·글 → '베트남어 낱말 풀이: 범위 재심(대상 품목 범위) · 신청서 접수 · 반덤핑 · 도금강판 · 한국 · 중국' (없으면 '')
export function foreignGloss(pageId, text) {
  const lang = LANG[pageId];
  if (!lang) return '';
  const t = String(text ?? '');
  const got = [];
  for (const [rx, ko] of lang[1]) if (rx.test(t) && !got.includes(ko)) got.push(ko);
  // '재심'은 더 구체적인 재심(범위·일몰·행정)이 있으면 뺀다
  const steel = /도금|냉연|열연|스테인리스|강연선|형강|컬러강판/;
  const words = got.filter((w) => !(w === '재심' && got.some((x) => /재심/.test(x) && x !== '재심')) && !(w === '철강' && got.some((x) => steel.test(x))));
  return words.length ? `${lang[0]} 낱말 풀이: ${words.join(' · ')} (번역 아님 — 누가 거는 조치인지·문장 뜻은 원문)` : '';
}
