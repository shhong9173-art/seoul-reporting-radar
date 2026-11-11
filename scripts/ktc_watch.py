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
import time

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
KEEP_NEWS = 60
NEWS_BACKFILL = 12   # 신청인 규칙 전 판정 보도자료를 한 실행에 읽는 수(PDF 사이 1초)
APPLICANTS_V = 2     # 신청인 읽기 규칙 판(11-11: 2 = 대리인 괄호·품목 꼬리·글자 띄운 머리 정리) — 판이 다르면 다시 읽는다
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


# 보도자료 첨부 PDF의 신청인(11-11 probe 210~212): 누리집 보도자료 상세엔 본문이 없고 첨부(hwpx·pdf, POST /boardFileDownload.do
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
NOT_APPLICANT = re.compile(r"법무법인|회계법인|관세법인|컨설팅|특허법인")
SENT_PRODUCT = re.compile(r"((?:[가-힣]+(?:·|‧|,\s*|\s및\s))*[가-힣]+산\s[^.,]{2,30}?)(?:에\s*대한|의)\s*(?:반?덤핑)")
NOT_NAME = {"신청인", "업계", "국내업계", "우리", "국내기업", "기업", "국내", "동", "이", "당사자", "피신청인"}
CORP_MARK = re.compile(r"㈜|\(주\)|주식회사|\s+")
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


def _names(raw):
    out = []
    for part in re.split(r"(?<=[가-힣㈜)])(?:과|와)\s+|\s*[,·‧]\s*|\s및\s", AGENT.sub("", raw or "")):
        tok = (re.findall(r"[가-힣A-Za-z0-9㈜()\-]+", part) or [""])[-1]
        name = CORP_MARK.sub("", tok).strip("()")
        if len(name) >= 2 and name not in NOT_NAME and not NOT_APPLICANT.search(name) and not re.fullmatch(r"\d+월?|작년|올해|지난해|금년", name):
            out.append(name)
    return out


def applicants_in(text):
    """보도자료 PDF 글 → [{'product', 'names', 'beat', 'how'}]. 표('(신청인) …')를 먼저, 없으면 '…이 조사를 신청' 문장."""
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
        add(heads[-1] if heads else None, _names(m.group(1)), "표")
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


def attachment_pdf(http, bid, sleep):
    """보도자료 첨부 중 PDF(첫 4바이트 %PDF) — seq 0001 먼저(대개 hwpx 다음), 없으면 0000. (bytes|None, 오류|None)."""
    for seq in ("0001", "0000"):
        sleep(1)
        try:
            st, body = http.post_binary("/boardFileDownload.do", {"bbs_id": bid, "seq_no": seq}, f"{SITE}/boardView.do?bbs_id={bid}&menuId={NEWS[1]}")
        except Exception as e:  # noqa: BLE001
            return None, type(e).__name__
        if st == 200 and body[:4] == b"%PDF":
            return body, None
    return None, "PDF 첨부 없음"


def pdf_text(data):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, "PDF 읽기 도구 없음"
    try:
        return " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:5]), None
    except Exception as e:  # noqa: BLE001 — a broken attachment is recorded, not fatal
        return None, f"PDF 해석 실패({type(e).__name__})"


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
        data, err = attachment_pdf(http, rec["id"], sleep)
        text, err2 = pdf_text(data) if data else (None, err)
        if text is None:
            rec["applicantsError"] = err2 or err
            return
        rec["applicants"] = applicants_in(text)
        rec["applicantsV"] = APPLICANTS_V
        rec.pop("applicantsError", None)

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
                  + (f" · 첨부 PDF의 신청인 — {who}" if who else ""), rec["url"], "B" if beat_names else "C", beat,
                  company="·".join(beat_names) or None)
        news[row["id"]] = rec
    # 신청인을 아직 안 읽은 지난 판정 보도자료(이 규칙 전 것) — 한 실행 NEWS_BACKFILL건, 이벤트 없이 기록만
    if not baseline:
        for rec in sorted(news.values(), key=lambda n: n["id"], reverse=True):
            if pdf_reads >= NEWS_BACKFILL + 3:
                break
            if rec.get("applicantsV") == APPLICANTS_V or rec.get("applicantsError") or not APPLICANT_TITLE.search(rec.get("title") or ""):
                continue
            read_applicants(rec)
    news = sorted(news.values(), key=lambda n: n["id"], reverse=True)[:KEEP_NEWS]

    listed = [c for c in cases if not c.get("stale")]
    status = "failed" if not listed and sched is None and newsp is None else ("partial" if errors or not listed else "ok")
    check = {"source": "무역위원회", "status": status, "returned": len(listed), **({"error": "; ".join(errors[:4])} if errors else {})}
    ktc = {"checkedAt": stamp, "baselineSince": prev.get("baselineSince") or stamp, "listComplete": list_done,
           "cases": cases, "left": left[:KEEP_LEFT], "meetings": meetings, "news": news}
    return ktc, events, check
