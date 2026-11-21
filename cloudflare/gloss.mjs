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
// 태국어(11-21): 태국 무역구제과 사건 쪽의 상태·가장 최근 공고·단계 이름이 태국어 그대로였다(11-06 AD1009 스테인리스 '판단 근거 사실 공개'
// 단계가 의견 마감 11-23인데 줄만 봐서는 무엇인지 몰랐다). 품목 이름은 이미 한국어(productKo)라 절차 낱말 위주.
const TH = [
  [/ทบทวนการเรียกเก็บอากร\S{0,40}ต่/, '일몰 재심(관세 계속 부과 여부)'], [/เปิดการทบทวน/, '재심 개시'], [/อยู่ระหว่างการทบทวน|ในระหว่าง(?:การ)?ทบทวน/, '재심 진행 중'],
  [/เปิดการไต่สวน/, '조사 개시'], [/ผลการไต่สวนขั้นต้น|ขั้นต้น/, '예비 판정'], [/ขั้นสุดท้าย/, '최종 판정'],
  [/รายละเอียดข้อมูลและข้อเท็จจริง/, '판단 근거 사실 공개(필수 사실)'], [/ร่างผล/, '결과 초안'],
  [/เรียกหลักประกัน/, '담보(관세 납부 보증) 요구'], [/ยุติ/, '종료'], [/ใช้มาตรการ/, '조치 시행 중'],
  [/ประกาศกรมการค้าต่างประเทศ/, '외국무역국(DFT) 공고'], [/คณะกรรมการพิจารณาการทุ่มตลาดและการอุดหนุน|คณะกรรมการ\s*ทตอ/, '반덤핑·보조금 심의위원회 공고'],
  [/อากรตอบโต้การอุดหนุน/, '상계관세'], [/อากรตอบโต้การทุ่มตลาด|การทุ่มตลาด/, '반덤핑'], [/มาตรการปกป้อง/, '세이프가드'],
  [/ทบทวน/, '재심'],
  [/เกาหลี/, '한국'], [/จีน/, '중국'], [/ญี่ปุ่น/, '일본'], [/ไต้หวัน/, '대만'], [/เวียดนาม/, '베트남'],
];
// 튀르키예어(11-21): 관보 무역구제 고시(tr-rg)는 제목에 나라·품목이 없고 본문 대목만 튀르키예어로 보인다
const TR = [
  [/Haks[ıi]z\s+Rekabetin\s+[ÖO]nlenmesi/i, '무역구제(불공정 수입 방지) 고시'], [/Korunma\s+[ÖO]nlem/i, '세이프가드'],
  [/s[üu]resinin\s+sona\s+ermesi|nihai\s+g[öo]zden\s+ge[çc]irme/i, '일몰(종료) 재심'], [/g[öo]zden\s+ge[çc]irme/i, '재심'],
  [/soru[şs]turma\s+a[çc][ıi]lmas/i, '조사 개시'], [/ge[çc]ici/i, '잠정'], [/nihai/i, '최종'], [/[öo]nlem/i, '조치'],
  [/dampinge\s+kar[şs][ıi]\s+vergi/i, '반덤핑 관세'], [/damping/i, '덤핑'], [/s[üu]bvansiyon|telafi\s+edici/i, '보조금(상계관세)'],
  [/s[ıi]cak\s+haddelenmi[şs]/i, '열연'], [/so[ğg]uk\s+haddelenmi[şs]/i, '냉연'], [/paslanmaz/i, '스테인리스'], [/galvaniz|kapl[ıi]/i, '도금'],
  [/yass[ıi]/i, '판재'], [/[çc]elik/i, '철강'], [/polietilen\s+tereftalat|\bPET\b/i, 'PET'], [/polivinil\s+kl[oö]r[üu]r|\bPVC\b/i, 'PVC'],
  [/lastik/i, '타이어'], [/kablo/i, '케이블'], [/polyester/i, '폴리에스터'], [/men[şs]e(?:li|yli)/i, '원산지(~산)'],
  [/Kore/i, '한국'], [/[ÇC]in\s+Halk/i, '중국'], [/Hindistan/i, '인도'], [/Endonezya/i, '인도네시아'], [/Vietnam/i, '베트남'],
  [/Tayland/i, '태국'], [/Malezya/i, '말레이시아'], [/Tayvan/i, '대만'], [/Japonya/i, '일본'],
];
// EU 기업결합 사전 신고 본문(영어, 11-21 #958): 거래 문장·사업 내용을 원문 그대로 붙였다 — 거래 형태 낱말만 짚는다('Merger Regulation'은 모든 공고에 있어 뺀다)
const EUM = [
  [/joint control/i, '공동 지배(합작)'], [/sole control/i, '단독 지배(인수)'],
  [/newly created (?:company|undertaking|joint venture)|constituting a joint venture|\bJV\b/i, '신설 합작사'],
  [/purchase of shares|acquisition of shares/i, '지분 매입'], [/purchase of assets|acquisition of assets/i, '자산 매입'],
  [/\bmerger\b(?!\s+Regulation)/i, '합병'], [/by contract|by other means/i, '계약 등 다른 방식'],
  [/does not have any business|no (?:current )?business (?:activities|operations)|not (?:currently )?active/i, '현재 사업 없음(신설·휴면 법인)'],
  [/simplified procedure/i, '간이 절차(통상 신고 뒤 25영업일 안 결정)'],
  [/Republic of Korea|\bKorea\b/, '한국'], [/\bIndia\b/, '인도'], [/\bChina\b/, '중국'], [/\bJapan\b/, '일본'], [/United States|\(US\)/, '미국'],
  [/\bGermany\b/, '독일'], [/\bFrance\b/, '프랑스'], [/\bItaly\b/, '이탈리아'], [/\bSpain\b/, '스페인'], [/\bNetherlands\b/, '네덜란드'],
  [/\bPoland\b/, '폴란드'], [/\bHungary\b/, '헝가리'], [/Czech/, '체코'], [/United Kingdom|\(UK\)/, '영국'], [/Indonesia/, '인도네시아'],
  [/Viet ?Nam/i, '베트남'], [/\bMexico\b/, '멕시코'],
];
const LANG = { 'vn-trav': ['베트남어', VI], 'id-kadi': ['인도네시아어', ID], 'th-trade': ['태국어', TH], 'tr-rg': ['튀르키예어', TR], 'eu-merger': ['영어', EUM] };

// pageId·글 → '베트남어 낱말 풀이: 범위 재심(대상 품목 범위) · 신청서 접수 · 반덤핑 · 도금강판 · 한국 · 중국' (없으면 '')
export function foreignGloss(pageId, text) {
  const lang = LANG[pageId];
  if (!lang) return '';
  const t = String(text ?? '');
  const got = [];
  for (const [rx, ko] of lang[1]) if (rx.test(t) && !got.includes(ko)) got.push(ko);
  // '재심'은 더 구체적인 재심(범위·일몰·행정)이 있으면 뺀다
  const steel = /도금|냉연|열연|스테인리스|강연선|형강|컬러강판/;
  const words = got.filter((w) => !(w === '재심' && got.some((x) => /재심/.test(x) && x !== '재심')) && !(w === '철강' && got.some((x) => steel.test(x)))
    && !(w === '덤핑' && got.includes('반덤핑 관세')));
  const note = pageId === 'eu-merger' ? '번역 아님 — 누가 무엇을 얼마에 사는지·지분율은 원문과 회사' : '번역 아님 — 누가 거는 조치인지·문장 뜻은 원문';
  return words.length ? `${lang[0]} 낱말 풀이: ${words.join(' · ')} (${note})` : '';
}
