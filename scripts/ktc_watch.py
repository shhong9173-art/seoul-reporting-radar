"""무역위원회(KTC) 국내 무역구제 감시 — 'trade-remedy' 저장소의 ktc 구역.

- 진행 사건 목록(/proInvestList.do, 쪽 넘김)과 사건별 진행일정(/viewInvest.do): 새 사건, 진행일정의 새 줄(판정시한 연장·
  공청회·예비판정 등), 목록 진행단계 변화, 진행 목록에서 빠진 사건(상세의 판정결과).
- 위원회 개최 안내(/noticeScheduleList.do)와 첨부 '본회의 개요' PDF: 회의 약 1주 전에 올라오는 안건(의결·보고) 목록.
- 보도자료 목록(/reportNewsList.do): 새 제목.
첫 실행은 기준선(이벤트 없음). 누리집에는 신청인(국내 생산자)·피신청인 이름이 대개 없다 — 품목이 출입 업종이어도
회사 사건으로 단정하지 않는다. 조회 실패는 0건이 아니라 미확인.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import re
import struct
import time
import zipfile
import zlib

SITE = "https://www.ktc.go.kr"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
PROGRESS = ("/proInvestList.do", "11")
SCHEDULE = ("/noticeScheduleList.do", "24")
NEWS = ("/reportNewsList.do", "57")
TIMEOUT = 40
LIST_PAGES = 10
DETAIL_MAX = 40
# 진행 목록에는 2000년대 불공정무역행위 사건도 '조사실행'으로 남아 있다(10-30 실제 44건 중 20건이 2019년 전). 이런 사건은
# 상세를 매번 읽지 않는다 — 목록에서 빠지면 그때 상세를 읽는다.
DETAIL_SINCE = "2019-01-01"
MEETINGS_READ = 3
AGENDA_TRIES = 6
KEEP_MEETINGS = 12
KEEP_NEWS = 120
NEWS_PAGES = 8       # 보도자료 목록을 거슬러 읽는 쪽 수(한 실행에 한 쪽씩, 11-12 판정 예고 — 진행 사건의 개시·예비판정 보도자료 신청인)
NEWS_BACKFILL = 12   # 신청인 규칙 전 판정 보도자료를 한 실행에 읽는 수(PDF 사이 1초)
APPLICANTS_V = 5     # 신청인 읽기 규칙 판(11-11: 2 = 대리인 괄호·품목 꼬리·글자 띄운 머리 정리, 3 = 표 칸 이름 안 띄어쓰기 붙임, 11-12: 4 = 각주·긴 이름 뺌,
                     # 5 = 한글 첨부(hwpx·hwp)·PDF 뒤쪽 쪽·옛 '신청인 :' 꼴) — 판이 다르면 다시 읽는다(실패한 것도 판이 바뀌면 한 번 더)
PRESS_PDF_PAGES = 20  # 보도자료 PDF를 읽는 쪽 수(11-12 probe 214: 앞 5쪽만 읽어 뒤쪽 참고(석도강판 티씨씨스틸·PVC 서스펜션 한화솔루션)를 놓쳤다)
FROM_LABEL = {"pdf": "PDF", "hwpx": "한글 파일", "hwp": "한글 파일"}
APPLICANT_TITLE = re.compile(r"덤핑|상계|세이프가드|판정|부과\s*건의|조사\s*개시|무역구제조치")
KEEP_LEFT = 40
LEFT_MAX = 5  # 한 번에 이보다 많이 빠지면 누리집 이상으로 보고 판단을 미룬다
# 출입 업종(철강·비철·전력기기·자동차·배터리·화학·에너지) 품목 낱말. 품목 표시일 뿐 회사 사건 근거가 아니다.
BEAT = re.compile(r"강관|강판|냉연|열연|후판|형강|봉강|철근|선재|스테인리스|도금|석도|아연|강선|철강|합금철|페로|빌릿|슬래브|"
                  r"변압기|차단기|케이블|전선|광섬유|동관|알루미늄|구리|동박|"
                  r"자동차|전기차|타이어|이차전지|배터리|양극재|음극재|전해액|분리막|"
                  r"PET|폴리|수지|에틸|아크릴|페놀|에폭시|가소제|초산|프로필렌|부타디엔|카본블랙|스티렌|글리콜|메탄올|흑연|리튬|수산화나트륨|가성소다|염소|"
                  r"태양광|폴리실리콘|수소|LNG", re.I)
AGENDA = re.compile(r"\(\s*(정기|일반|의결)\s*제?\s*(\d{4}\s*-\s*\d+)\s*호\s*\)\s*(.+?)(?=\s*ㅇ\s*\(\s*(?:정기|일반|의결)|\s*□|\s+\*\s|\s+-\s*\d+\s*-|$)", re.S)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def plain(raw):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", t))).strip()


def iso_dot(s):
    m = re.search(r"(\d{4})[.\-](\d{1,2})[.\-](\d{1,2})", s or "")
    if not m or m.group(1) == "1900":  # 누리집의 빈 날짜 자리값
        return None
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"


def rows_of(page):
    return re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", page or "")


def tds(tr):
    return [plain(x) for x in re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)]


def parse_cases(page):
    """진행 사건 목록 한 쪽: 조사건명 ¦ 조사번호 ¦ 조사품명 ¦ 조사개시일 ¦ 진행단계, viewInvest('ID','유형')."""
    out = []
    for tr in rows_of(page):
        m = re.search(r"viewInvest\(\s*'(\d+)'\s*,\s*'(\d+)'\s*\)", tr)
        c = tds(tr)
        if not m or len(c) < 5:
            continue
        out.append({"id": m.group(1), "type": m.group(2), "title": c[0], "no": c[1], "product": c[2], "opened": iso_dot(c[3]), "stage": c[4]})
    return out


def parse_detail(page):
    """사건 상세: 관리정보(th/td 짝)와 진행일정 표. 날짜가 찬 줄만 진행한 단계, 빈 줄은 남은 단계. 판정결과 요약."""
    info = {plain(th): plain(td) for th, td in re.findall(r"<th[^>]*>([\s\S]*?)</th>\s*<td[^>]*>([\s\S]*?)</td>", page or "")}
    if "조사번호" not in info:
        return None
    timeline, pending = [], []
    i = page.find("진행일정 테이블")
    if i >= 0:
        for tr in rows_of(page[i:page.find("</table>", i)]):
            c = tds(tr)
            if len(c) >= 2 and c[0]:
                (timeline.append([c[0], c[1]]) if DATE.match(c[1]) else pending.append(c[0]))
    result = None
    j = page.find("판정결과 요약 테이블")
    if j >= 0:
        cells = [x for tr in rows_of(page[j:page.find("</table>", j)]) for x in tds(tr) if x]
        result = " · ".join(x for x in cells if "없습니다" not in x) or None
    return {"country": info.get("대상국") or None, "kind": info.get("조사유형") or None, "review": info.get("재심종류") or None,
            "timeline": timeline, "pending": pending, "result": result}


def parse_meetings(page):
    """위원회 일정 목록: 번호 ¦ 제목 ¦ 첨부 ¦ 작성자 ¦ 등록일 ¦ 조회, dltncView('ID')."""
    out = []
    for tr in rows_of(page):
        m = re.search(r"dltncView\(\s*'(\d+)'\s*\)", tr)
        c = tds(tr)
        if m and len(c) >= 5:
            out.append({"id": m.group(1), "title": c[1], "posted": iso_dot(c[4])})
    return out


def parse_meeting_detail(page):
    """개최 안내 본문: 일시('26.10.23(금) …), 안건 요약(7건(정기보고1, …)), 첨부 파일(fileDownload('ID','순번'))."""
    body = plain(page)
    when = None
    m = re.search(r"일시\s*:?\s*[‘'’`]?\s*(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})", body)
    if m:
        when = f"20{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    s = re.search(r"회의 안건\s*:?\s*(\d+건(?:\([^)]*\))?)", body)
    files = [{"seq": q, "name": plain(n)} for d, q, n in re.findall(r"fileDownload\(\s*'(\d+)'\s*,\s*'(\d+)'\s*\)[^>]*>([^<]+)<", page or "")]
    return {"meetingOn": when, "summary": s.group(1) if s else None, "files": files}


def parse_agenda(text):
    """회의 개요 PDF 본문의 안건: (의결 제2026-24호) 중국산 … 최종판정. 정기(회의록)는 뺀다."""
    out = []
    for kind, no, what in AGENDA.findall(re.sub(r"\s+", " ", text or "")):
        if kind == "정기":
            continue
        what = re.sub(r"\s+", " ", what).strip(" -·")[:200]
        out.append({"kind": "의결" if kind == "의결" else "보고", "no": re.sub(r"\s+", "", no), "text": what, "beat": bool(BEAT.search(what))})
    return out


def parse_news(page):
    """보도자료 목록: 번호 ¦ 제목 ¦ 첨부 ¦ 작성자 ¦ 조회, boardView('ID'). 목록에 날짜가 없어 새 글만 상세에서 등록일을 읽는다."""
    out = []
    for tr in rows_of(page):
        m = re.search(r"boardView\(\s*'(\d+)'\s*\)", tr)
        c = tds(tr)
        if m and len(c) >= 2:
            out.append({"id": m.group(1), "title": re.sub(r"\s*새글$", "", c[1]).strip()})
    return out


# 보도자료 첨부의 신청인(11-11 probe 210~212, 11-12 probe 214부터 PDF가 없으면 한글 파일): 누리집 보도자료 상세엔 본문이 없고 첨부(hwpx·pdf, POST /boardFileDownload.do
# bbs_id·seq_no)에 있다. 판정 보도자료 PDF엔 '참고N (최종판정) 중국산 아연도금냉연 덤핑조사 (원심) □ 조사 개요 ㅇ (신청인) 동국씨엠㈜,
# 케이지스틸㈜, ㈜세아씨엠 ㅇ (조사대상공급자) …' 표와 '작년 7월 엘지화학이 조사를 신청한 건으로' 같은 문장이 있다(부틸 아크릴레이트·
# 수산화나트륨(영진)·봉강(세아베스틸·세아창원특수강)·무계목강관(일진제강)·동관(능원금속공업·엘에스메탈)·산업용로봇(HD현대로보틱스)).
# 누리집 사건 상세엔 신청인 이름이 없으니, 출입처가 신청인으로 적힌 보도자료는 출입처 항목으로 올린다.
APPLICANT_ROW = re.compile(r"\(\s*신청인\s*\)\s*(.{2,120}?)\s*(?=ㅇ|□|\(\s*조사대상|$)")
APPLICANT_SENT = re.compile(r"([^.。]{2,40}?)(?:이|가)\s*(?:반?덤핑)?\s*조사\s*(?:를\s*)?신청")
REF_HEAD = re.compile(r"참고\s*\d*\s*[\(\[]?\s*(?:최종판정|예비판정|의결|판정|조사개시|조사종결)?\s*[\)\]]?\s*(.{2,50}?)\s*(?:덤핑조사|덤핑사실|조사)")
# 글자 사이를 띄운 머리(probe 213: '참고1[의 결] 독·프·노 르 웨 이 및 스 웨 덴 산 폴 리 염 화 비 닐 페 이 스 트 수 지 덤 핑 조 사') — 공백을 빼고 다시 본다
REF_HEAD_NS = re.compile(r"참고\d*[\(\[]?(?:최종판정|예비판정|의결|판정|조사개시|조사종결)?[\)\]]?(.{2,50}?)(?:덤핑조사|덤핑사실|조사)")
AGENT = re.compile(r"\(\s*대리인[^)]*\)")   # '㈜엘지화학(대리인: 법무법인 정률, DKC글로벌컨설팅)' — 대리인은 신청인이 아니다
# 옛 보도자료(2019~2022, 한글 파일만 첨부 — probe 214): '참고 1 베트남산 스테인리스강 냉간압연 제품 (원심) 개요 □ 조사 개요 ㅇ 신청인 : ㈜포스코 ㅇ …',
# '참고2 대만 및 이탈리아산 스테인리스스틸바 원심 개요 □ 원심 개요 ㅇ 신청인(신청일) : ㈜세아창원특수강, ㈜세아특수강, 동일제강㈜ (‘18.4.19.) ㅇ 피신청인 …',
# '참고 2 중국산 더블레이어 옵셋인쇄판 반덤핑조사(원심) 개요 □ 조사 개요 ㅇ 신청인 : 제일씨앤피(주) (‘21.3.4. 신청접수) * 대리인 : …'.
# '피신청인 :'·'신청인 주장 덤핑률 :'·'신청인은 …'은 아니다.
APPLICANT_COLON = re.compile(r"(?<![가-힣])신청인\s*(?:\(\s*신청일\s*\))?\s*[:：]\s*(.{2,120}?)\s*(?=ㅇ|○|◦|□|■|\*|※)")
REF_OLD = re.compile(r"참고\s*\d+\s*(.{2,70}?)\s*(?:개요|□|ㅇ)")
HEAD_TAIL = re.compile(r"\s*(?:[\(\[]\s*(?:원심|재심)\s*[\)\]]|원심|재심|반?덤핑\s*조사|조사\s*개시|개시\s*결정|결정|조사|의)\s*$")
DATE_PAREN = re.compile(r"\(\s*[‘’'`´]?\s*\d{2,4}\s*\.[^)]*\)")   # '(‘18.4.19.)', '(’20.11.26.접수)', '(‘21.3.4. 신청접수)'
NOT_APPLICANT = re.compile(r"법무법인|회계법인|관세법인|컨설팅|특허법인")
SENT_PRODUCT = re.compile(r"((?:[가-힣]+(?:·|‧|,\s*|\s및\s))*[가-힣]+산\s[^.,]{2,30}?)(?:에\s*대한|의)\s*(?:반?덤핑)")
NOT_NAME = {"신청인", "업계", "국내업계", "우리", "국내기업", "기업", "국내", "동", "이", "당사자", "피신청인"}
CORP_MARK = re.compile(r"㈜|\((?:주|사|재|유)\)|주식회사|사단법인|\s+")   # (사)한국합판보드협회
# 신청인 이름 → 출입처(AGENTS.md 명시 기업만). 세아씨엠·세아베스틸·엘에스메탈 같은 계열·관련 회사는 출입처로 바꾸지 않는다.
BEAT_ALIAS = {"엘지화학": "LG화학", "LG화학": "LG화학", "케이지스틸": "KG스틸", "KG스틸": "KG스틸", "동국씨엠": "동국씨엠", "동국제강": "동국제강",
              "현대제철": "현대제철", "포스코": "포스코", "POSCO": "포스코", "세아제강": "세아제강", "롯데케미칼": "롯데케미칼", "한화솔루션": "한화솔루션",
              "금호석유화학": "금호석유화학", "고려아연": "고려아연", "영풍": "영풍", "오씨아이": "OCI", "OCI": "OCI", "태광산업": "태광",
              "에스오일": "S-OIL", "S-OIL": "S-OIL", "에쓰오일": "S-OIL", "에이치디현대일렉트릭": "HD현대일렉트릭", "HD현대일렉트릭": "HD현대일렉트릭",
              "엘에스일렉트릭": "LS일렉트릭", "LS일렉트릭": "LS일렉트릭", "엘에스전선": "LS전선", "LS전선": "LS전선", "대한전선": "대한전선",
              "엘에스엠앤엠": "LS MnM", "LS엠앤엠": "LS MnM", "LSMnM": "LS MnM", "디엘케미칼": "DL케미칼", "DL케미칼": "DL케미칼", "동성케미칼": "동성케미칼",
              "에스케이이노베이션": "SK이노베이션", "SK이노베이션": "SK이노베이션", "에이치디현대오일뱅크": "HD현대오일뱅크", "HD현대오일뱅크": "HD현대오일뱅크",
              "지에스칼텍스": "GS칼텍스", "GS칼텍스": "GS칼텍스", "현대자동차": "현대차", "기아": "기아", "현대모비스": "현대모비스", "현대위아": "현대위아",
              "에이치엘만도": "HL만도", "HL만도": "HL만도", "한국타이어앤테크놀로지": "한국타이어", "금호타이어": "금호타이어", "넥센타이어": "넥센타이어",
              "두산에너빌리티": "두산에너빌리티"}


def _product(p):
    """'중국산 부틸 아크릴레이트 (원심)□' → '중국산 부틸 아크릴레이트', '조사종결) 자동차용 배터리팩 특허권 침해' → '자동차용 배터리팩 특허권 침해'."""
    p = re.sub(r"\s*\((?:원심|재심)\)\s*", " ", p or "")
    p = re.sub(r"^[^(]*?\)\s*", "", p) if re.match(r"^[^(]*\)", p) else p
    return p.strip(" □ㅇ·-") or None


def _names(raw, table=False):
    """table=True: '(신청인)' 칸 — 쉼표로 나뉜 한 마디가 한 회사(마디 안 띄어쓰기는 PDF 글자 조각이라 붙인다: 11-11 운영
    '튤립 이노베이션케이에프티'가 '이노베이션케이에프티'로 잘렸다). 문장 꼴은 날짜 낱말을 버리려고 마디의 마지막 낱말만."""
    out = []
    raw = re.sub(r",\s*(?=(?:Ltd|Inc|LLC|Corp|GmbH)\b)", " ", AGENT.sub("", raw or ""))   # 'Sekisui Chemical Co., Ltd.'는 한 회사
    for part in re.split(r"(?<=[가-힣㈜)])(?:과|와)\s+|\s*[,·‧]\s*|\s및\s", raw):
        tok = part if table else (re.findall(r"[가-힣A-Za-z0-9㈜()\-]+", part) or [""])[-1]
        tok = re.split(r"\*|※", tok)[0]   # 각주(11-12 운영: '와이어쓰엘엘씨**미국화이자(PfizerInc.)가‘09년인수한자회사…')
        name = re.sub(r"\([^)]*\)?", "", CORP_MARK.sub("", tok)).strip("()")   # '유닉스(UNIX)' → 유닉스(괄호 안 영문 이름은 뺀다)
        if len(name) > 25:
            continue
        if len(name) >= 2 and name not in NOT_NAME and not NOT_APPLICANT.search(name) and not re.fullmatch(r"\d+월?|작년|올해|지난해|금년", name):
            out.append(name)
    return out


def _old_head(window):
    """'… 참고 6 중국산 스티렌모노머 반덤핑조사(원심) 개요 □ 조사신청 개요 ㅇ' → '중국산 스티렌모노머'. 머리가 없으면 None."""
    heads = REF_OLD.findall(window)
    if not heads:
        return None
    p = heads[-1]
    while True:
        q = HEAD_TAIL.sub("", p)
        if q == p:
            break
        p = q
    return p.strip() or None


def applicants_in(text):
    """보도자료 첨부 글 → [{'product', 'names', 'beat', 'how'}]. 표('(신청인) …')·옛 개요('신청인 : …')를 먼저, 없으면 '…이 조사를 신청' 문장."""
    t = re.sub(r"\s+", " ", text or "")
    out, seen = [], set()

    def add(product, names, how):
        names = [n for n in names if n]
        key = (product or "", tuple(names))
        if names and key not in seen:
            seen.add(key)
            beat = []
            for n in names:
                b = BEAT_ALIAS.get(n)
                if b and b not in beat:
                    beat.append(b)
            out.append({"product": _product(product or "")[:60] if product else None, "names": names[:6], "beat": beat, "how": how})

    for m in APPLICANT_ROW.finditer(t):
        window = t[max(0, m.start() - 160):m.start()]
        heads = REF_HEAD.findall(window) or REF_HEAD_NS.findall(re.sub(r"\s+", "", window))
        add(heads[-1] if heads else None, _names(m.group(1), table=True), "표")
    for m in APPLICANT_COLON.finditer(t):
        add(_old_head(t[max(0, m.start() - 200):m.start()]), _names(DATE_PAREN.sub(" ", m.group(1)), table=True), "개요")
    tables = bool(out)
    for m in APPLICANT_SENT.finditer(t):
        # 문장 꼴은 '…것으로, 올해 2월 세아베스틸과 세아창원특수강이' — 마지막 쉼표 뒤 마디만 이름 자리
        names = _names(re.split(r"[,，]", m.group(1))[-1])
        if not names:
            continue
        prods = SENT_PRODUCT.findall(t[max(0, m.start() - 160):m.end()])
        known = {n for x in out for n in x["names"]}
        if set(names) <= known or (tables and not prods):   # 표에 이미 있거나, 표가 있는데 품목 모르는 문장('HD현대로보틱스가 조사 신청')
            continue
        add(prods[-1] if prods else None, names, "문장")
    return out


# 품목 맞추기(11-12 판정 예고): 같은 품목을 보도자료·사건 목록·회의 안건이 다르게 쓴다 — '중국산 아연도금냉연'(보도자료) ↔
# '중국산 아연 및 아연합금 표면처리 냉간압연 제품의 덤핑사실및국내산업 피해유무(원심) 최종판정'(안건) ↔ '… 유무 조사'(사건),
# '독·프·노르웨이및스웨덴산폴리염화비닐페이스트수지'(보도자료) ↔ '유럽 4개국산 PVC 페이스트 수지(PSR)'(보도자료 제목).
# 나라 이름·절차 낱말·띄어쓰기를 빼고 운영에서 본 줄임만 바꾼 뒤, 한쪽이 다른 쪽을 품거나 두 글자 조각이 60% 넘게 겹치면 같은 품목,
# 나라가 둘 다 적혔는데 하나도 안 겹치면 다른 품목으로 본다.
KTC_COUNTRIES = ("중국", "대만", "일본", "미국", "말레이시아", "태국", "인도네시아", "인도", "베트남", "러시아", "독일", "프랑스", "노르웨이",
                 "스웨덴", "아랍에미리트연합", "아랍에미리트연방", "아랍에미리트", "싱가포르", "사우디아라비아", "이탈리아", "스페인", "브라질", "튀르키예", "타이")
COUNTRY_SHORT = {"독": "독일", "프": "프랑스", "노": "노르웨이", "스": "스웨덴", "중": "중국", "일": "일본", "미": "미국", "대": "대만"}
PRODUCT_ALIAS = (("아연도금냉연", "아연및아연합금표면처리냉간압연"), ("아연표면처리냉연", "아연및아연합금표면처리냉간압연"),
                 ("PVC", "폴리염화비닐"), ("PSR", "폴리염화비닐페이스트수지"), ("고체수산화나트륨", "수산화나트륨"), ("BA", "부틸아크릴레이트"))
PRODUCT_NOISE = re.compile(r"\(\s*(?:원심|재심|PSR|BA)\s*\)|의?\s*덤핑\s*사실\s*및?\s*국내\s*산업\s*피해\s*유무|에\s*대한|덤핑\s*방지\s*관세|부과\s*종료\s*재심사"
                           r"|종료\s*재심사|\(\s*\d+\s*차\s*\)|\d+\s*차|조사\s*개시|개시\s*결정|최종\s*판정|예비\s*판정|판정|보고|조사|덤핑|제품|건의|부과|의결|원심|재심|유럽\s*\d+\s*개국"
                           # 불공정무역행위 사건의 공통 꼬리(11-12 운영: '임플란트 개질기 특허권 침해 불공정무역행위'가 공통 꼬리 때문에 다른 사건 신청인과 맞음)
                           r"|(?:특허권|디자인권|상표권|영업비밀|저작권)\s*침해|불공정\s*무역\s*행위|원산지\s*표시\s*위반|여부|이의\s*신청\s*결정|관련\s*무역위원회\s*처분")


def countries_in(text):
    t = str(text or "")
    found = {c for c in KTC_COUNTRIES if c in t}
    for m in re.finditer(r"(?<![가-힣])([독프노스중일미대])(?=\s*[·‧,])|(?<=[·‧,])\s*([독프노스중일미대])(?![가-힣])", t):
        found.add(COUNTRY_SHORT[m.group(1) or m.group(2)])
    return {"아랍에미리트" if c.startswith("아랍에미리트") else ("태국" if c == "타이" else c) for c in found}


def product_key(text):
    t = PRODUCT_NOISE.sub(" ", str(text or ""))
    head, sep, tail = t.rpartition("산 ")
    if sep and (countries_in(head) or re.search(r"[·‧,]", head)):   # '중국, 미국, 말레이시아산 …' → 뒤만
        t = tail
    t = re.sub(r"[^0-9A-Za-z가-힣]", "", t)
    for c in sorted(KTC_COUNTRIES, key=len, reverse=True):
        if t.startswith(c):
            t = t[len(c):]
    t = re.sub(r"^(?:및|산)+", "", t)
    for a, b in PRODUCT_ALIAS:
        t = t.replace(a, b)
    return t


def same_product(a, b):
    ka, kb = product_key(a), product_key(b)
    if len(ka) < 2 or len(kb) < 2:
        return False
    ca, cb = countries_in(a), countries_in(b)
    if ca and cb and not (ca & cb):
        return False
    if (len(ka) >= 3 and ka in kb) or (len(kb) >= 3 and kb in ka):
        return True
    ga = {ka[i:i + 2] for i in range(len(ka) - 1)}
    gb = {kb[i:i + 2] for i in range(len(kb) - 1)}
    return bool(ga and gb) and len(ga & gb) / len(ga | gb) >= 0.6


def applicant_index(news):
    """보도자료 신청인 → [{product, names, beat, newsId, title, posted}] 최근 보도자료 먼저."""
    out = []
    for n in sorted(news, key=lambda x: x.get("id") or "", reverse=True):
        for a in n.get("applicants") or []:
            if a.get("product") and a.get("names"):
                out.append({"product": a["product"], "names": a["names"], "beat": a.get("beat") or [], "newsId": n["id"],
                            "title": n.get("title"), "posted": n.get("posted")})
    return out


def applicant_for(text, index):
    return next((x for x in index if same_product(text, x["product"])), None)


def attachment_kind(body):
    return "pdf" if body[:4] == b"%PDF" else "hwpx" if body[:2] == b"PK" else "hwp" if body[:4] == b"\xd0\xcf\x11\xe0" else None


def attachment_file(http, bid, sleep):
    """보도자료 첨부 한 개: PDF(첫 4바이트 %PDF) 먼저, 없으면 한글 파일(hwpx·hwp) — seq 0001(대개 한글 파일 다음), 0000,
    둘 다 읽을 꼴이 아니면 0002까지(probe 214: 옛 보도자료 14건은 PDF 없이 hwp 12·hwpx 2, 빈 seq는 0바이트). (bytes|None, 꼴|None, 오류|None)."""
    spare = None
    for seq in ("0001", "0000", "0002"):
        if seq == "0002" and spare:
            break
        sleep(1)
        try:
            st, body = http.post_binary("/boardFileDownload.do", {"bbs_id": bid, "seq_no": seq}, f"{SITE}/boardView.do?bbs_id={bid}&menuId={NEWS[1]}")
        except Exception as e:  # noqa: BLE001
            return (*spare, None) if spare else (None, None, type(e).__name__)
        kind = attachment_kind(body) if st == 200 else None
        if kind == "pdf":
            return body, kind, None
        if kind and not spare:
            spare = (body, kind)
    return (*spare, None) if spare else (None, None, "읽을 첨부 없음(PDF·한글 파일 아님)")


def pdf_text(data, pages=5):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, "PDF 읽기 도구 없음"
    try:
        return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:pages]), None
    except Exception as e:  # noqa: BLE001 — a broken attachment is recorded, not fatal
        return None, f"PDF 해석 실패({type(e).__name__})"


def hwpx_text(data):
    """hwpx(zip): Contents/section*.xml의 글자."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        secs = sorted(n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n))
        if not secs:
            return None, "hwpx 본문 없음"
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", "ignore"))) for n in secs), None
    except Exception as e:  # noqa: BLE001
        return None, f"hwpx 해석 실패({type(e).__name__})"


# HWP 5.0 문단 글자(HWPTAG_PARA_TEXT=67)는 UTF-16LE 16비트 낱자 줄이다. 32 미만 값 중 아래는 8낱자짜리 제어(표·그림·구역 정의·필드 등)라
# 통째로 건너뛴다 — 안 건너뛰면 제어 이름('tbl '·'secd')이 '氠瑢'·'捤獥' 같은 한자로 읽힌다(probe 214).
HWP_CTRL8 = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23})


def hwp_para_text(data):
    n = len(data) // 2
    units, keep, i = struct.unpack_from(f"<{n}H", data), [], 0
    while i < n:
        c = units[i]
        if c in HWP_CTRL8:
            keep.append(32)
            i += 8
            continue
        keep.append(32 if c < 32 or 0xE000 <= c <= 0xF8FF else c)
        i += 1
    return struct.pack(f"<{len(keep)}H", *keep).decode("utf-16le", "ignore")


def hwp_section_text(data):
    """HWP 본문 레코드(머리 4바이트: 태그 10비트·크기 12비트, 크기 0xFFF면 다음 4바이트)에서 문단 글자(태그 67)만."""
    out, i = [], 0
    while i + 4 <= len(data):
        head = struct.unpack_from("<I", data, i)[0]
        tag, size = head & 0x3FF, (head >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:
            size = struct.unpack_from("<I", data, i)[0]
            i += 4
        if tag == 67:
            out.append(hwp_para_text(data[i:i + size]))
        i += size
    return " ".join(out)


def hwp_text(data):
    """HWP 5.0(OLE): BodyText/Section* 스트림(FileHeader 36번째 바이트 1비트가 압축 → raw deflate)."""
    try:
        import olefile
    except ImportError:
        return None, "hwp 읽기 도구 없음"
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
        compressed = bool(ole.openstream("FileHeader").read()[36] & 1)
        out = []
        for entry in sorted((e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText"), key=lambda e: int(re.sub(r"\D", "", e[1]) or 0)):
            raw = ole.openstream(entry).read()
            out.append(hwp_section_text(zlib.decompress(raw, -15) if compressed else raw))
        return " ".join(out), None
    except Exception as e:  # noqa: BLE001
        return None, f"hwp 해석 실패({type(e).__name__})"


def attachment_text(http, bid, sleep):
    """보도자료 첨부 글자 → (글자|None, 오류|None, 꼴|None)."""
    data, kind, err = attachment_file(http, bid, sleep)
    if data is None:
        return None, err, None
    text, err = pdf_text(data, PRESS_PDF_PAGES) if kind == "pdf" else hwpx_text(data) if kind == "hwpx" else hwp_text(data)
    return text, err, kind


class Http:
    """무역위원회 누리집: 첫 요청 전에 첫 화면으로 세션 쿠키를 받는다. 실패는 예외 대신 (상태, 본문)으로 돌려준다."""

    def __init__(self, session=None):
        self.s = session
        self.ready = False

    def _open(self):
        if self.s is None:
            import requests
            self.s = requests.Session()
        if not self.ready:
            self.ready = True
            try:
                self.s.get(SITE + "/", headers=UA, timeout=TIMEOUT)
            except Exception:  # noqa: BLE001 — the list request will report the failure
                pass

    @staticmethod
    def _text(r):
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = "utf-8"
        return r.text

    def post(self, path, data):
        self._open()
        r = self.s.post(SITE + path, data=data, headers={**UA, "Referer": SITE + "/"}, timeout=TIMEOUT)
        return r.status_code, self._text(r)

    def post_binary(self, path, data, referer=None):
        self._open()
        r = self.s.post(SITE + path, data=data, headers={**UA, "Referer": referer or SITE + "/"}, timeout=TIMEOUT)
        return r.status_code, r.content

    def get(self, path, params, referer=None, binary=False):
        self._open()
        r = self.s.get(SITE + path, params=params, headers={**UA, "Referer": referer or SITE + "/"}, timeout=TIMEOUT)
        return r.status_code, (r.content if binary else self._text(r))


def _try(errors, label, fn, *a, **k):
    try:
        status, body = fn(*a, **k)
    except Exception as e:  # noqa: BLE001 — network errors become a recorded gap
        errors.append(f"{label} {type(e).__name__}")
        return None
    if status != 200:
        errors.append(f"{label} HTTP {status}")
        return None
    return body


def case_url(cid, ctype):
    return f"{SITE}/viewInvest.do?menuId=11&masterId={cid}&invstg_type_code={ctype}"


def _meeting_url(mid):
    return f"{SITE}/noticeScheduleView.do?dltnc_id={mid}&menuId=24&pageIndex=1&searchCondition=&searchKeyword="


def _news_url(nid):
    return f"{SITE}/boardView.do?bbs_id={nid}&menuId=57&pageIndex=1&searchCondition=&searchKeyword="


def _agenda_line(agenda, n=6):
    dec = [a["text"] for a in agenda if a["kind"] == "의결"]
    rep = [a["text"] for a in agenda if a["kind"] == "보고"]
    parts = ([f"의결: {' / '.join(dec[:n])}"] if dec else []) + ([f"보고: {' / '.join(rep[:n])}"] if rep else [])
    return "; ".join(parts)


def read_meeting(http, row, sleep, errors):
    """개최 안내 상세와 회의 개요 PDF. 안건을 못 읽으면 agenda=None(다음 실행에서 다시)."""
    url = _meeting_url(row["id"])
    page = _try(errors, f"회의 {row['id']} 안내", http.get, "/noticeScheduleView.do",
                {"dltnc_id": row["id"], "menuId": "24", "pageIndex": "1", "searchCondition": "", "searchKeyword": ""})
    if page is None:
        return {**row, "url": url, "agenda": None, "agendaError": "안내 조회 실패"}
    d = parse_meeting_detail(page)
    rec = {**row, **d, "url": url, "agenda": None}
    pdfs = [f for f in d["files"] if f["name"].lower().endswith(".pdf")]
    pick = next((f for f in pdfs if "개요" in f["name"]), pdfs[0] if pdfs else None)
    if not pick:
        rec["agendaError"] = "PDF 첨부 없음"
        return rec
    sleep(0.7)
    data = _try(errors, f"회의 {row['id']} 개요 PDF", http.get, "/dltncFileDownload.do", {"dltnc_id": row["id"], "seq_no": pick["seq"]},
                referer=url, binary=True)
    if data is None:
        rec["agendaError"] = "PDF 받기 실패"
        return rec
    if not bytes(data[:5]).startswith(b"%PDF"):
        rec["agendaError"] = "PDF 아님"
        return rec
    text, err = pdf_text(data)
    if err:
        rec["agendaError"] = err
        return rec
    agenda = parse_agenda(text)
    if agenda:
        rec["agenda"] = agenda
    else:
        rec["agendaError"] = "안건 줄 없음"
    return rec


def collect(prev, now, http, *, sleep=time.sleep):
    """prev: 지난 doc['ktc'] 또는 None. 돌려줌: (ktc 구역, 새 이벤트, 원천 점검 한 줄)."""
    stamp = now.isoformat(timespec="seconds")
    baseline = not prev
    prev = prev or {}
    errors, events = [], []

    def event(kind, eid, label, text, url, tier, beat, product=None, company=None):
        events.append({"id": f"ktc:{kind}:{eid}", "pageId": "ktc", "country": "KR", "label": label, "text": text[:600], "url": url,
                       "detectedAt": stamp, "tier": tier, "beat": beat, "ktcKind": kind, **({"product": product} if product else {}),
                       **({"company": company} if company else {})})

    # 1) 진행 사건 목록 — 새 ID가 없는 쪽이 나오면 끝
    cases, ids, list_done = [], set(), False
    for p in range(1, LIST_PAGES + 1):
        page = _try(errors, f"진행 목록 {p}쪽", http.post, PROGRESS[0], {"menuId": PROGRESS[1], "pageIndex": str(p)})
        if page is None:
            break
        rows = [r for r in parse_cases(page) if r["id"] not in ids]
        if not rows:
            list_done = True
            break
        cases += rows
        ids |= {r["id"] for r in rows}
        sleep(0.7)
    else:
        errors.append(f"진행 목록 {LIST_PAGES}쪽까지만 읽음")
    prev_cases = {c["id"]: c for c in prev.get("cases") or [] if isinstance(c, dict) and c.get("id")}

    # 2) 사건 상세(진행일정)
    detail_fail, over, reads = 0, 0, 0
    for c in cases:
        old = prev_cases.get(c["id"]) or {}
        c["beat"] = bool(BEAT.search(f"{c['title']} {c['product']}"))
        c["firstSeen"] = old.get("firstSeen") or stamp
        c["url"] = case_url(c["id"], c["type"])
        d, read = None, False
        if (not c["opened"] or c["opened"] < DETAIL_SINCE) and old.get("checkedAt"):
            pass  # 오래된 사건은 한 번 읽은 뒤로는 목록만 본다
        elif reads < DETAIL_MAX:
            reads, read = reads + 1, True
            page = _try([], "", http.post, "/viewInvest.do", {"menuId": PROGRESS[1], "masterId": c["id"], "invstg_type_code": c["type"]})
            d = parse_detail(page) if page else None
            sleep(0.5)
        else:
            over += 1
        if d:
            c.update(d, checkedAt=stamp)
        else:
            for k in ("country", "kind", "review", "timeline", "pending", "result", "checkedAt"):
                if k in old:
                    c[k] = old[k]
            if read:
                detail_fail += 1
                c["detailError"] = "상세 조회 실패"
        if baseline:
            continue
        if not old:
            what = f"{c['title']} — 품목 {c['product']}, 개시 {c['opened'] or '날짜 미상'}" + (f", {c.get('kind')}/{c.get('review')}" if c.get("kind") else "") \
                + (f", 대상국 {c['country']}" if c.get("country") else "")
            event("case", c["id"], f"무역위 새 조사 · {c['no']}", what, c["url"], "B" if c["beat"] else "C", c["beat"], c["product"])
            continue
        fresh = []
        if d and old.get("timeline") is not None:
            had = {tuple(s) for s in old["timeline"]}
            fresh = [f"{s} {t}" for s, t in d["timeline"] if (s, t) not in had]
        if old.get("stage") and c["stage"] and old["stage"] != c["stage"]:
            fresh.insert(0, f"목록 진행단계 {old['stage']}→{c['stage']}")
        if fresh:
            event("step", f"{c['id']}:{len(c.get('timeline') or [])}:{c['stage']}", f"무역위 진행일정 · {c['no']}",
                  f"{c['title']} — 새 진행: {'; '.join(fresh[:6])}", c["url"], "B" if c["beat"] else "C", c["beat"], c["product"])
    if detail_fail:
        errors.append(f"상세 {detail_fail}/{reads}건 실패")
    if over:
        errors.append(f"상세 한도 {DETAIL_MAX}건 넘어 {over}건 다음 실행으로")

    # 3) 진행 목록에서 빠진 사건 — 목록을 끝까지 읽은 때만. 상세의 마지막 진행·판정결과를 붙인다
    left = [x for x in prev.get("left") or [] if isinstance(x, dict) and x.get("leftAt", "") >= (now - dt.timedelta(days=180)).isoformat()]
    gone = [oid for oid in prev_cases if oid not in ids]
    sane = len(gone) <= LEFT_MAX and len(ids) >= 0.7 * len(prev_cases)
    if list_done and cases and gone and not sane:
        errors.append(f"진행 목록 {len(prev_cases)}→{len(ids)}건 — 한꺼번에 {len(gone)}건 빠져 판단 보류")
    if list_done and cases and sane:
        for oid in gone:
            old = prev_cases[oid]
            page = _try([], "", http.post, "/viewInvest.do", {"menuId": PROGRESS[1], "masterId": oid, "invstg_type_code": old.get("type", "")})
            d = parse_detail(page) if page else None
            sleep(0.5)
            rec = {**old, **(d or {}), "leftAt": stamp}
            left.insert(0, rec)
            if not baseline:
                last = (rec.get("timeline") or [])[-3:]
                what = f"{old.get('title')} — 진행 목록에서 빠짐(종결 목록 확인)" + (f"; 마지막 진행: {'; '.join(f'{s} {t}' for s, t in last)}" if last else "") \
                    + (f"; 판정결과: {rec['result']}" if rec.get("result") else "") + ("" if d else "; 상세 조회 실패")
                event("left", oid, f"무역위 진행 목록에서 빠짐 · {old.get('no')}", what, case_url(oid, old.get("type", "")),
                      "B" if old.get("beat") else "C", bool(old.get("beat")), old.get("product"))
    elif gone:  # 목록을 다 못 읽었거나 한꺼번에 많이 빠졌으면 지난 사건을 그대로 둔다(빠짐으로 보지 않음)
        cases += [dict(prev_cases[oid], stale=True) for oid in gone]

    # 4) 위원회 개최 안내와 회의 개요(안건)
    prev_meet = {m["id"]: m for m in prev.get("meetings") or [] if isinstance(m, dict) and m.get("id")}
    meetings = dict(prev_meet)
    sched = _try(errors, "위원회 일정 목록", http.post, SCHEDULE[0], {"menuId": SCHEDULE[1]})
    for n, row in enumerate((parse_meetings(sched) if sched else [])[:MEETINGS_READ]):
        old = prev_meet.get(row["id"])
        if old and (old.get("agenda") or old.get("agendaTries", 0) >= AGENDA_TRIES):
            continue
        if baseline and n > 0:
            # 첫 실행은 가장 최근 회의 하나만 읽는다(기준선)
            meetings[row["id"]] = {**row, "url": _meeting_url(row["id"]), "agenda": None, "agendaError": "기준선(읽지 않음)", "agendaTries": AGENDA_TRIES}
            continue
        sleep(0.7)
        rec = read_meeting(http, row, sleep, errors)
        rec["firstSeen"] = (old or {}).get("firstSeen") or stamp
        rec["agendaTries"] = (old or {}).get("agendaTries", 0) + (0 if rec.get("agenda") else 1)
        meetings[row["id"]] = rec
        if baseline:
            continue
        agenda = rec.get("agenda") or []
        beat = any(a["beat"] for a in agenda)
        when = f"(개최 {rec['meetingOn']})" if rec.get("meetingOn") else ""
        if not old:
            text = f"{rec['title']} {when} 안건 {rec.get('summary') or '수 미상'}" + (f" — {_agenda_line(agenda)}" if agenda else f" — 안건 PDF 미확인({rec.get('agendaError')})")
            event("meeting", row["id"], f"무역위원회 회의 안내{when}", text, rec["url"], "B" if beat else "C", beat)
        elif agenda:
            event("agenda", row["id"], f"무역위원회 회의 안건 공개{when}", f"{rec['title']} — {_agenda_line(agenda)}", rec["url"], "B" if beat else "C", beat)
    meetings = sorted(meetings.values(), key=lambda m: m["id"], reverse=True)[:KEEP_MEETINGS]

    # 5) 보도자료
    prev_news = {n["id"]: n for n in prev.get("news") or [] if isinstance(n, dict) and n.get("id")}
    news = dict(prev_news)
    newsp = _try(errors, "보도자료 목록", http.post, NEWS[0], {"menuId": NEWS[1]})
    pdf_reads = 0

    def read_applicants(rec):
        nonlocal pdf_reads
        pdf_reads += 1
        if not rec.get("posted") and rec.get("older"):   # 지난 쪽 글은 목록에 날짜가 없다 — 신청인 출처에 날짜를 붙이려고 상세에서 등록일만
            sleep(0.5)
            page = _try([], "", http.get, "/boardView.do", {"bbs_id": rec["id"], "menuId": NEWS[1]})
            m = re.search(r"등록일\s*(\d{4}-\d{2}-\d{2})", plain(page)) if page else None
            if m:
                rec["posted"] = m.group(1)
        text, err, kind = attachment_text(http, rec["id"], sleep)
        if text is None:
            rec["applicantsError"] = err
            rec["applicantsErrorV"] = APPLICANTS_V
            return
        rec["applicants"] = applicants_in(text)
        rec["applicantsV"] = APPLICANTS_V
        rec["applicantsFrom"] = kind
        rec.pop("applicantsError", None)
        rec.pop("applicantsErrorV", None)

    # 지난 보도자료 쪽(11-12 판정 예고): 한 실행에 한 쪽씩 NEWS_PAGES쪽까지 — 이벤트 없이 기록만, 신청인은 아래 채우기에서
    depth = int(prev.get("newsDepth") or 1)
    if not baseline and newsp and depth < NEWS_PAGES:
        sleep(0.7)
        older = _try(errors, f"보도자료 목록 {depth + 1}쪽", http.post, NEWS[0], {"menuId": NEWS[1], "pageIndex": str(depth + 1)})
        if older is not None:
            depth += 1
            for row in parse_news(older):
                if row["id"] not in news:
                    news[row["id"]] = {**row, "url": _news_url(row["id"]), "firstSeen": stamp, "older": True}
    for row in parse_news(newsp) if newsp else []:
        if row["id"] in prev_news:
            continue
        rec = {**row, "url": _news_url(row["id"]), "firstSeen": stamp}
        if not baseline:
            sleep(0.5)
            body = _try([], "", http.get, "/boardView.do", {"bbs_id": row["id"], "menuId": "57"})
            m = re.search(r"등록일\s*(\d{4}-\d{2}-\d{2})", plain(body)) if body else None
            rec["posted"] = m.group(1) if m else None
            if APPLICANT_TITLE.search(row["title"]):
                read_applicants(rec)
            beat_names = [b for a in rec.get("applicants") or [] for b in a["beat"]]
            beat_names = list(dict.fromkeys(beat_names))
            beat = bool(BEAT.search(row["title"])) or bool(beat_names)
            who = "; ".join(f"{a['product'] or '품목 미상'}: {', '.join(a['names'])}" for a in rec.get("applicants") or [])
            event("news", row["id"], "무역위 보도자료", f"{row['title']}" + (f" (등록 {rec['posted']})" if rec["posted"] else "")
                  + (f" · 첨부({FROM_LABEL.get(rec.get('applicantsFrom'), '파일')})의 신청인 — {who}" if who else ""), rec["url"], "B" if beat_names else "C", beat,
                  company="·".join(beat_names) or None)
        news[row["id"]] = rec
    # 신청인을 아직 안 읽은 지난 판정 보도자료(이 규칙 전 것) — 한 실행 NEWS_BACKFILL건, 이벤트 없이 기록만
    if not baseline:
        for rec in sorted(news.values(), key=lambda n: n["id"], reverse=True):
            if pdf_reads >= NEWS_BACKFILL + 3:
                break
            failed = rec.get("applicantsError") and rec.get("applicantsErrorV") == APPLICANTS_V   # 이 판에서 이미 못 읽은 것은 다시 안 한다
            if rec.get("applicantsV") == APPLICANTS_V or failed or not APPLICANT_TITLE.search(rec.get("title") or ""):
                continue
            read_applicants(rec)
    news = sorted(news.values(), key=lambda n: n["id"], reverse=True)[:KEEP_NEWS]

    # 6) 판정 예고(11-12): 보도자료 신청인을 사건·회의 안건 품목에 붙인다. 다가오는 회의(오늘 이후 개최) 안건에 출입처 신청인이
    #    처음 붙으면 회의 전 출입처 항목(B)으로 — 판정 결과는 회의 뒤 보도자료·의결서로 확인.
    index = applicant_index(news)
    for c in cases:
        hit = applicant_for(c.get("title") or c.get("product"), index)
        if hit:
            c["applicant"] = {k: hit[k] for k in ("names", "beat", "newsId", "title", "posted")}
        else:
            c.pop("applicant", None)
    today = now.astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    for mt in meetings:
        for a in mt.get("agenda") or []:
            hit = applicant_for(a.get("text"), index)
            if not hit:
                continue
            had = a.get("applicant")
            a["applicant"] = {k: hit[k] for k in ("names", "beat", "newsId", "title", "posted")}
            upcoming = (mt.get("meetingOn") or "") >= today
            if baseline or not upcoming or not hit["beat"] or (had and had.get("beat")):
                continue
            posted = f" {hit['posted']}" if hit.get("posted") else ""
            event("preview", f"{mt['id']}:{a.get('no') or a.get('text', '')[:20]}", f"무역위 회의 예고(개최 {mt.get('meetingOn')})",
                  f"{a['kind']}: {a['text']} — 신청인 {', '.join(hit['names'])}(보도자료 「{hit['title']}」{posted} 첨부)"
                  f" · 결과(판정·세율)는 회의 뒤 보도자료·의결서로 확인", mt.get("url"), "B", True, company="·".join(hit["beat"]))

    listed = [c for c in cases if not c.get("stale")]
    status = "failed" if not listed and sched is None and newsp is None else ("partial" if errors or not listed else "ok")
    check = {"source": "무역위원회", "status": status, "returned": len(listed), **({"error": "; ".join(errors[:4])} if errors else {})}
    ktc = {"checkedAt": stamp, "baselineSince": prev.get("baselineSince") or stamp, "listComplete": list_done,
           "cases": cases, "left": left[:KEEP_LEFT], "meetings": meetings, "news": news,
           "newsDepth": depth if not baseline else int(prev.get("newsDepth") or 1)}
    return ktc, events, check
