"""출입처 공장이 있는 시·군의 고시·공고(새올 전자민원창구) 감시: 제목에 출입처 이름·공장 사업이 나온 새 고시·공고.

- 공장 증설·신설은 회사 발표보다 지자체 고시·공고가 먼저인 경우가 많다: 건설공사 안전점검 수행기관 지정 공고(발주자·공사명),
  환경영향평가 공람, 산업단지 계획 변경, 공유수면 점용·매립, 도시관리계획 결정. 10-30 탐침: 울주군 '건설공사 안전점검 수행기관 지정
  공고[온산 고려아연(주), Ga 2차 …]'(09-14), '[온산 고려아연(주), 정련로 신규 …]'(09-09), 여수시 'GS칼텍스 우순도 공장증설용지 …
  환경영향평가'(2024-11), 당진시 '현대제철㈜ LNG 자가용전기설비 설치사업 환경영향평가(초안)'(2024-11).
- 시·군마다 새올 고시·공고 목록 최신 60건(30건×2쪽)을 받아 처음 보는 관리번호만 본다. 첫 실행은 기준선.
- 등급: 출입처 이름 + 사업 낱말(증설·신설·설치·건설·공장·환경영향평가·매립·산업단지 등) = A, 출입처 이름만 = B,
  출입처 이름 없이 제철소·제련소·산업단지 계획·발전사업 = C. 담배 소매인 지정 같은 생활 공고는 버린다.
  출입처 이름이 없는 소규모 발전사업 양도·양수 인가·공시송달·용역 입찰도 버린다(이름이 있으면 그대로 A·B).
- 고시·공고 제목만 본다(첨부 HWP·PDF는 열지 않는다). 사업 규모·내용은 첨부 원문과 회사 확인.
- 해외 IP에서 응답이 느린 시·군(포항 33초·평택 57초)은 75초까지 기다린다. 그래도 시간 초과면 '실패' — 0건이 아니라 미확인.
- 결과는 기자 전용 저장소(kr-local)로만. 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_local/v1"
PATH = "/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
LIST = {"method": "selectListOfrNotAncmt", "methodnm": "selectListOfrNotAncmtHomepage", "homepage_pbs_yn": "Y", "subCheck": "Y",
        "ofr_pageSize": "30", "not_ancmt_se_code": "01,02,03,04,05", "initValue": "Y", "countYn": "Y", "list_gubun": "A",
        "jndinm": "OfrNotAncmtEJB", "context": "NTIS", "method_type": ""}
PAGES = 2
TIMEOUT = 75  # 10-30 탐침: 포항 33초·평택 57초 걸려 응답(45초에선 시간 초과)
KEEP_DAYS = 120
KEEP_MAX = 500
SEEN_MAX = 400  # management numbers kept per city

# (시·군, 새올 주소, 이 시·군의 출입처 공장) — 10-30 탐침으로 GitHub 러너에서 목록이 열린 곳 + 느린 곳(시간 초과면 미확인)
CITIES = [
    ("당진시", "https://eminwon.dangjin.go.kr", "현대제철·KG스틸·동국제강"),
    ("아산시", "https://eminwon.asan.go.kr", "현대차"),
    ("여수시", "https://eminwon.yeosu.go.kr", "GS칼텍스·DL케미칼·한화솔루션"),
    ("울주군", "http://eminwon.ulju.ulsan.kr", "고려아연·LS MnM·현대차"),
    ("울산 남구", "https://eminwon.ulsannamgu.go.kr", "현대모비스·고려아연"),
    ("군산시", "https://eminwon.gunsan.go.kr", "세아베스틸·OCI"),
    ("익산시", "http://eminwon.iksan.go.kr", "OCI"),
    ("서산시", "https://eminwon.seosan.go.kr", "현대모비스·한화"),
    ("화성시", "https://eminwon.hscity.go.kr", "기아"),
    ("금산군", "https://eminwon.geumsan.go.kr", "한국타이어"),
    ("대전 대덕구", "https://eminwon.daedeok.go.kr", "한국타이어"),
    ("창녕군", "https://eminwon.cng.go.kr", "넥센타이어"),
    ("곡성군", "http://eminwon.gokseong.go.kr", "금호타이어"),
    ("동해시", "https://eminwon.dh.go.kr", "LS전선"),
    ("진천군", "https://eminwon.jincheon.go.kr", "한화"),
    ("음성군", "https://eminwon.eumseong.go.kr", ""),
    ("영주시", "https://eminwon.yeongju.go.kr", ""),
    ("포항시", "https://eminwon.pohang.go.kr", "포스코·현대제철·동국제강·세아"),
    ("광양시", "https://eminwon.gwangyang.go.kr", "포스코"),
    ("창원시", "https://eminwon.changwon.go.kr", "현대위아·세아창원특수강"),
    ("평택시", "https://eminwon.pyeongtaek.go.kr", "KG모빌리티"),
    ("천안시", "https://eminwon.cheonan.go.kr", "LS일렉트릭"),
    ("양산시", "https://eminwon.yangsan.go.kr", "넥센타이어"),
    # 10-30 추가(탐침으로 목록 30줄 확인): 출입처 공장이 있는데 빠져 있던 시·군
    ("울산 북구", "https://eminwon.bukgu.ulsan.kr", "현대차·현대모비스"),
    ("울산 동구", "http://eminwon.donggu.ulsan.kr", "HD현대일렉트릭"),
    ("완주군", "https://eminwon.wanju.go.kr", "현대차(전주공장)"),
    ("봉화군", "https://eminwon.bonghwa.go.kr", "영풍(석포제련소)"),
    ("부산 강서구", "https://eminwon.bsgangseo.go.kr", "르노코리아"),
    ("부산 사하구", "https://eminwon.saha.go.kr", "동국씨엠·동성케미컬"),
    ("원주시", "https://eminwon.wonju.go.kr", "HL만도"),
    ("예산군", "https://eminwon.yesan.go.kr", "현대제철"),
    # 10-30 오후 탐침: 광주 광산구는 목록 형식이 달라(제목 링크에 관리번호) 파서를 넓혀 붙인다. 광주 서구(기아 오토랜드 광주)는 목록을
    # <ul><li> 목록 형식이라 따로 읽고(아래), 부평(한국GM)·구미·순천·경주·시흥·양산은 접속 시간 초과, 청주·인천 동구는 SSL 오류 — 빼 둔다.
    ("광주 광산구", "https://eminwon.gwangsan.go.kr", "금호타이어(광주공장)"),
    ("광주 서구", "https://eminwon.seogu.gwangju.kr", "기아(오토랜드 광주)"),  # 목록이 표가 아니라 <ul><li> 형식(10-30)
    ("광명시", "https://eminwon.gm.go.kr", "기아(오토랜드 광명)"),  # 칸 사이 빈 <td> 형식(10-30), 접속이 들쑥날쑥(시간 초과면 미확인)
]

# 해외 IP(GitHub 러너)에서는 접속 시간 초과지만 국내 컴퓨터에서는 열리는 시·군(10-30 기자 컴퓨터 브라우저로 확인: 부평 목록 30줄 5초,
# 나머지 0.4초 안 접속). 기자 컴퓨터의 브라우저로 읽는 예약 작업이 sdds `local_notice_submit`으로 칸 글자를 올리면(kr-local-browser),
# 이 감시가 같은 규칙으로 읽는다. 브라우저 수집이 30시간 넘게 없으면 미확인(컴퓨터·앱이 꺼졌을 수 있음).
BROWSER_CITIES = [
    ("인천 부평구", "https://eminwon.icbp.go.kr", "한국GM(부평공장)"),
    ("구미시", "https://eminwon.gumi.go.kr", "LS전선(구미)"),
    ("청주시", "https://www.cheongju.go.kr", "LS일렉트릭(청주)"),  # 홈페이지 고시공고 게시판(HOMEPAGE_BOARDS)
    ("순천시", "https://eminwon.suncheon.go.kr", "현대제철(순천)"),
    ("함평군", "https://eminwon.hampyeong.go.kr", "금호타이어(함평 이전 공장)"),
]
BROWSER_BACKUP = {"양산시", "광주 광산구"}  # GitHub에서 들쑥날쑥한 곳: 직접 조회가 실패하면 브라우저 수집으로 대신
BROWSER_FRESH_HOURS = 30
BROWSER_FRESH_MONDAY = 78  # 예약 작업은 평일 오전뿐: 월요일 오전 실행은 금요일 수집(약 70시간 전)까지 받아 준다


def browser_limit(now):
    return BROWSER_FRESH_MONDAY if now.weekday() == 0 and now.hour < 12 else BROWSER_FRESH_HOURS


def browser_rows(browser, city, now):
    """브라우저 수집 문서에서 그 시·군 줄(파싱 뒤)과 수집 시각. 없거나 오래됐으면 (None, 이유)."""
    for c in (browser or {}).get("cities") or []:
        if not isinstance(c, dict) or c.get("city") != city:
            continue
        try:
            at = dt.datetime.fromisoformat(str(c.get("fetchedAt")))
            age = (now - at).total_seconds() / 3600
        except (TypeError, ValueError):
            return None, "브라우저 수집 시각 미상"
        if age > browser_limit(now):
            return None, f"브라우저 수집이 {age:.0f}시간 전 — 컴퓨터·앱이 꺼졌을 수 있음"
        if c.get("error"):
            return None, f"브라우저 수집 실패({str(c['error'])[:40]})"
        rows = [r for r in (parse_cells(x.get("mgt"), x.get("cells") or []) for x in c.get("rows") or [] if isinstance(x, dict)) if r]
        if not rows:  # 빈 목록으로 기준선을 만들면 다음 수집 때 첫 쪽 전체가 '신규'가 된다
            return None, "브라우저 수집 0줄(형식 변경 가능)"
        return rows, at.astimezone(KST).strftime("%Y-%m-%dT%H:%M") + " KST"
    return None, "브라우저 수집 없음(예약 작업 전이거나 컴퓨터·앱이 꺼짐)"


# (출입처, 제목 규칙)
COMPANIES = [
    ("현대차", r"현대자동차|현대차(?!증권)"), ("기아", r"기아(?:\s*\(주\)|㈜|자동차|\s*오토랜드)"), ("현대모비스", r"현대모비스"),
    ("현대위아", r"현대위아"), ("HL만도", r"HL만도|에이치엘만도"), ("한국GM", r"한국지엠|한국GM"), ("KG모빌리티", r"케이지모빌리티|KG모빌리티"),
    ("르노코리아", r"르노코리아"), ("한국타이어", r"한국타이어"), ("넥센타이어", r"넥센타이어"), ("금호타이어", r"금호타이어"),
    ("포스코", r"포스코(?!퓨처엠|인터내셔널|이앤씨|DX|엠텍|스틸리온|모빌리티솔루션)|POSCO"), ("현대제철", r"현대제철"),
    ("KG스틸", r"KG스틸|케이지스틸"), ("세아", r"세아(?:제강|베스틸|창원특수강|홀딩스|씨엠)"), ("동국제강", r"동국제강"),
    ("동국씨엠", r"동국씨엠"), ("고려아연", r"고려아연"), ("영풍", r"영풍\s*(?:석포|\(주\)|㈜)|석포제련소"),
    ("HD현대일렉트릭", r"HD현대일렉트릭|에이치디현대일렉트릭|현대일렉트릭"), ("LS일렉트릭", r"LS일렉트릭|엘에스일렉트릭"),
    ("대한전선", r"대한전선"), ("LS전선", r"LS전선|엘에스전선"), ("LS MnM", r"LS\s*MnM|엘에스엠앤엠|LS엠앤엠"),
    ("두산에너빌리티", r"두산에너빌리티"), ("GS칼텍스", r"GS칼텍스|지에스칼텍스"), ("한화솔루션", r"한화솔루션"),
    ("OCI", r"OCI(?![A-Za-z])|오씨아이"), ("태광", r"태광산업"), ("동성케미칼", r"동성케미[칼컬]"), ("DL케미칼", r"DL케미칼|디엘케미칼"),
    ("효성중공업(관련)", r"효성중공업"),
]
PROJECT = re.compile(r"증설|신설|신규|설치|건설|건립|공장|라인|환경영향평가|매립|산업단지|착공|확장|이전|안전점검|사업")
GENERIC = re.compile(r"제철소|제련소|공장\s*(?:증설|신설|설립)|공장증설|산업단지\s*계획|일반산업단지|국가산업단지|산업단지.{0,12}(?:지정|변경|승인)|발전사업|전기사업|발전소\s*(?:건설|설치)")
NOISE = re.compile(r"담배\s*소매|소매인\s*지정|일자리\s*박람회|채용|봉사자|도로명주소")
# 출입처 이름이 없을 때만 버리는 일상 행정: 소규모 발전사업(3MW 이하는 시·도·시군 허가 — 큰 것은 전기위원회 감시) 양도·양수 인가,
# 전기사업법 위반 처분 공시송달, 산업단지 도로·용수 공사의 용역 입찰. 10-27~10-30 운영: 참고(C) 12건 중 9건이 이것
# (청주 '다다2호 태양광발전소 등 4건 양도·양수 인가', 예산 '예당2일반산업단지 진입도로 건설공사 폐기물처리용역 입찰' 등).
ROUTINE = re.compile(r"양도\s*[·ㆍ・,]?\s*양수|양수\s*인가|전기사업법\s*위반|공시\s*송달|입찰\s*공고|용역\s*입찰|폐기물\s*처리\s*용역")
RULES = [
    "지자체 고시·공고 목록 제목을 본다. 출입처 이름이 든 새 공고(A·B)는 상세 페이지의 전체 제목·본문 앞부분·첨부 파일 이름까지 읽는다"
    "(첨부 원문은 열지 않음). 사업 규모·내용은 첨부와 회사·지자체 확인.",
    "출입처 이름 + 사업 낱말 = A, 출입처 이름만 = B, 출입처 이름 없이 제철소·제련소·산업단지 계획·발전사업 = C"
    "(이름 없는 소규모 발전사업 양도·양수 인가·공시송달·용역 입찰은 버림).",
    "건설공사 안전점검 수행기관 지정 공고는 공사가 정해졌다는 뜻이지 착공·완공이 아니다.",
    "첫 실행은 기준선. 시간 초과·실패한 시·군은 0건이 아니라 미확인.",
]


def norm_space(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def cell_text(h):
    return norm_space(htmllib.unescape(re.sub(r"<[^>]+>", " ", h)))


NOTICE_NO = re.compile(r"(?:고시|공고|공시)\s*제?\s*[\d-]+\s*호")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_rows(page):
    """Rows of one 새올 list page. Two layouts (10-30): onclick on each <td> (당진·여수) or an <a onclick> inside each <td>
    (울주·아산). Cells run 번호, 공고번호, 제목, 담당부서, 등록일(, 게재기간, 조회수)."""
    out = []
    blocks = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", page or "")
    if "dbody" in (page or ""):
        # 광주 서구 형식(10-30): <div class="dbody"><ul><li class="col01">번호</li><li class="col02 blind">공고번호</li>
        # <li class="title">제목</li><li class="col03">부서</li><li class="col04">등록일</li>… — 표 대신 목록, 칸마다 searchDetail('…')
        body = page[page.find("dbody"):]
        blocks += [re.sub(r"<(/?)li\b", r"<\1td", ul) for ul in re.findall(r"<ul[^>]*>([\s\S]*?)</ul>", body)]
    for tr in blocks:
        m = (re.search(r"searchDetail\(\s*['\"]([0-9A-Za-z_-]+)['\"]\s*\)", tr)
             or re.search(r"not_ancmt_mgt_no=([0-9A-Za-z_-]+)", tr))  # 광주 광산구 형식(10-30): 제목 <a href="…not_ancmt_mgt_no=56345…">
        if not m:
            continue
        # 빈 칸은 뺀다: 광명시 형식(10-30)은 칸 사이마다 빈 <td>가 있다(번호 없이 공고번호·제목·부서·등록일·조회수)
        row = parse_cells(m.group(1), [cell_text(c) for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", tr)])
        if row:
            out.append(row)
    return out


def parse_cells(mgt, cells):
    """한 줄의 칸 글자들 → {관리번호, 공고번호, 제목, 부서, 등록일}. 브라우저 수집(local_notice_submit)도 칸 글자만 보내 같은 규칙으로 읽는다."""
    cells = [re.sub(r"\s+", " ", str(c or "")).strip() for c in cells]
    cells = [c for c in cells if c]
    i = next((k for k, c in enumerate(cells) if NOTICE_NO.search(c)), None)
    if i is not None and i + 1 < len(cells):
        no, t = cells[i], i + 1
    else:
        # 울산 남구 형식(10-30): 번호, 제목, 담당부서, 등록일, 조회수 — 공고번호 칸이 없다
        no = None
        t = next((k for k, c in enumerate(cells) if c and not re.fullmatch(r"[\d,]+", c) and not DATE.fullmatch(c)), None)
        if t is None:
            return None
    title = cells[t]
    if not title or not re.fullmatch(r"[0-9A-Za-z_-]{1,40}", str(mgt or "")):
        return None
    dept = cells[t + 1] if t + 1 < len(cells) and not DATE.fullmatch(cells[t + 1]) and not re.fullmatch(r"[\d,]+", cells[t + 1]) else None
    date = next((c for c in cells[t + 1:] if DATE.fullmatch(c)), None)
    return {"mgt": str(mgt), "no": no, "title": title[:200], "dept": dept, "date": date}


DETAIL_MAX = 8  # 실행당 상세 페이지(새 A·B만)
DETAIL_TIMEOUT = 45
DETAIL_BACKFILL_DAYS = 3
BODY_CHARS = 400
FILE_EXT = re.compile(r"\.(?:pdf|hwpx?|docx?|xlsx?|zip|jpg|png)$", re.I)
BODY_END = re.compile(r"^(?:첨부\s*파일|목록\s*보기|목록|이전\s*글|다음\s*글)\b")


def parse_detail(page, title):
    """새올 상세 페이지 → 전체 제목·본문 앞부분·첨부 파일 이름. 목록 제목은 길면 '...'로 잘린다(10-31 탐침: 울주 68156 목록
    「…[온산 고려아연(주), #2ASU O...」 → 상세 「…[온산 고려아연(주), #2ASU O2 COMPRESSOR ROOM 토건공사]」, 본문 '온산읍 원산리
    892번지 일원 상 공장 용도의 건축공사'). 제목을 못 찾으면 None — 형식을 짐작해 채우지 않는다."""
    html = re.sub(r"<(script|style)\b[\s\S]*?</\1>", " ", page or "", flags=re.I)
    nodes = [norm_space(htmllib.unescape(t)) for t in re.findall(r">([^<]+)<", html)]
    nodes = [t for t in nodes if t]
    prefix = re.sub(r"(?:\.{2,}|…)\s*$", "", norm_space(title)).strip()[:30]
    if len(prefix) < 6:
        return None
    i = next((k for k, t in enumerate(nodes) if prefix in t), None)
    if i is None:
        return None
    full = nodes[i][:300]
    body, files = [], []
    for t in nodes[i + 1:]:
        if BODY_END.match(t):
            break
        body.append(t)
    for t in nodes[i + 1:]:  # 첨부 파일은 링크마다 한 덩어리(이름에 띄어쓰기·괄호가 있다)
        if FILE_EXT.search(t) and t not in files:
            files.append(t[:120])
    text = norm_space(" ".join(body))
    return {"title": full, "body": text[:BODY_CHARS] + ("…" if len(text) > BODY_CHARS else ""), "files": files[:6]}


def classify(title):
    if NOISE.search(title):
        return None, []
    hits = [c for c, rx in COMPANIES if re.search(rx, title)]
    if hits:
        return ("A" if PROJECT.search(title) else "B"), hits
    if GENERIC.search(title) and not ROUTINE.search(title):
        return "C", []
    return None, []


# 새올 목록이 기자 컴퓨터에서도 시간 초과인 곳은 시·군 홈페이지의 고시공고 게시판(같은 새올 관리번호)을 읽는다.
# 10-30 청주: eminwon.cheongju.go.kr 목록 POST·GET 모두 90초·40초 시간 초과, www.cheongju.go.kr/www/selectEminwonNoticeList.do는
# 1초 안 200(robots.txt가 /www/ 허용).
HOMEPAGE_BOARDS = {
    "https://www.cheongju.go.kr": ("/www/selectEminwonNoticeList.do?key=281&pageUnit=60",
                                   "/www/selectEminwonNoticeView.do?key=281&notAncmtMgtNo={mgt}"),
}


def list_url(base):
    return base + (HOMEPAGE_BOARDS[base][0] if base in HOMEPAGE_BOARDS else PATH)


def detail_url(base, mgt):
    if base in HOMEPAGE_BOARDS:
        return base + HOMEPAGE_BOARDS[base][1].format(mgt=mgt)
    return (f"{base}{PATH}?method=selectOfrNotAncmt&methodnm=selectOfrNotAncmtRegst&not_ancmt_mgt_no={mgt}"
            "&homepage_pbs_yn=Y&subCheck=Y&jndinm=OfrNotAncmtEJB&context=NTIS")


def fetch_page(base, page, post, sleep):
    last = None
    for attempt in range(2):  # 10-30: 포항은 같은 날 33초에 응답하다가 75초도 넘기기도 했다 — 한 번 더
        try:
            r = post(base + PATH, data={**LIST, "pageIndex": str(page)}, headers={**UA, "Referer": base + PATH}, timeout=TIMEOUT)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            sleep(5.0)
    raise last


def fetch_city(city, base, post, sleep):
    """Rows of the first PAGES pages, and a note when a later page failed (the first page's rows are kept)."""
    rows = []
    for page in range(1, PAGES + 1):
        try:
            text = fetch_page(base, page, post, sleep)
        except Exception as e:  # noqa: BLE001
            if page == 1:
                raise
            return rows, f"{page}쪽 {error_kind(e)} — 최신 {len(rows)}건만 봄"
        got = parse_rows(text)
        if not got:
            if page == 1:
                raise RuntimeError("목록 형식 미상")
            break
        rows += got
        sleep(0.5)
    return rows, None


def error_kind(e):
    name = type(e).__name__
    return name if name in ("ConnectTimeout", "ReadTimeout", "ConnectionError", "SSLError", "Timeout") else (str(e)[:40] or name)


def read_details(items, get, sleep, budget=DETAIL_MAX):
    """새 A·B 공고의 상세 페이지를 읽어 전체 제목으로 다시 매긴다. 실패는 detailError로 남긴다(제목만 확인한 상태 그대로)."""
    read = failed = 0
    for x in items[:budget]:
        try:
            r = get(x["url"], headers={**UA, "Referer": x["url"].split("?")[0]}, timeout=DETAIL_TIMEOUT)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            d = parse_detail(r.text, x["title"])
            if not d:
                raise RuntimeError("상세 형식 미상")
        except Exception as e:  # noqa: BLE001
            x["detailError"] = error_kind(e)
            failed += 1
            continue
        x["detail"] = d
        read += 1
        tier, hits = classify(d["title"])
        if tier and (tier, hits) != (x["tier"], x["companies"]):
            x["listTier"] = x["tier"]
            x["tier"], x["companies"] = tier, hits or x["companies"]
            x["company"] = x["companies"][0] if x["companies"] else None
        sleep(1.0)
    return {"read": read, "failed": failed, "skipped": max(0, len(items) - budget)}


def run(*, now, previous=None, post=None, sleep=time.sleep, cities=CITIES, browser=None, browser_cities=BROWSER_CITIES, get=None):
    if post is None:
        import requests
        post = requests.post
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    seen = {k: list(v) for k, v in (prev.get("seen") or {}).items()}
    old = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    out = dict(old)
    checks = []

    def one(c):
        city, base, plants = c
        try:
            rows, note = fetch_city(city, base, post, sleep)
            return c, rows, note
        except Exception as e:  # noqa: BLE001
            return c, None, error_kind(e)

    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(one, cities))
    sources = {}
    for i, ((city, base, plants), rows, err) in enumerate(results):
        if rows is None and city in BROWSER_BACKUP:
            brows, note = browser_rows(browser, city, now)
            if brows is not None:
                results[i] = ((city, base, plants), brows, None)
                sources[city] = f"직접 조회 실패({err}) — 기자 컴퓨터 브라우저 수집 {note}"
    for c in browser_cities:
        brows, note = browser_rows(browser, c[0], now)
        results.append((c, brows, None if brows is not None else note))
        if brows is not None:
            sources[c[0]] = f"기자 컴퓨터 브라우저 수집 {note}"
    for (city, base, plants), rows, err in results:
        if rows is None:
            checks.append({"source": city, "status": "failed", "error": err})
            continue
        known = set(seen.get(city) or [])
        baseline = city not in seen  # a city read for the first time is its own baseline
        new = 0
        for r in rows:
            if r["mgt"] in known:
                continue
            known.add(r["mgt"])
            tier, hits = classify(r["title"])
            if not tier:
                continue
            iid = f"local:{city}:{r['mgt']}"
            if iid in out:
                continue
            out[iid] = {"id": iid, "city": city, "plants": plants, "no": r["no"], "title": r["title"], "dept": r["dept"], "date": r["date"],
                        "companies": hits, "company": hits[0] if hits else None, "tier": tier, "url": detail_url(base, r["mgt"]),
                        "listUrl": list_url(base), "firstSeen": stamp, "baseline": baseline, "isNew": not baseline}
            new += 1
        order = [r["mgt"] for r in rows] + [m for m in seen.get(city) or [] if m not in {r["mgt"] for r in rows}]
        seen[city] = order[:SEEN_MAX]
        oldest_seen_reached = any(r["mgt"] in set(prev.get("seen", {}).get(city) or []) for r in rows) or baseline
        notes = [n for n in (err, None if oldest_seen_reached else f"최신 {len(rows)}건 안에 지난 실행 공고가 없음 — 그 사이 공고 일부 미확인") if n]
        checks.append({"source": city, "status": "partial" if notes else "ok", "returned": len(rows), "matched": new,
                       **({"via": sources[city]} if city in sources else {}), **({"error": "; ".join(notes)} if notes else {})})
    for iid, x in out.items():
        if iid in old and x is old[iid]:
            x["isNew"] = False
            # 저장된 참고(C) 중 지금 규칙으로 버릴 일상 행정은 지우지 않고 표시만(화면에서 뺌)
            if not x.get("company") and classify(x.get("title") or "")[0] is None:
                x["routine"] = True
    # 새 A·B 공고는 상세 페이지까지(기자 컴퓨터 브라우저로 읽은 시·군과 홈페이지 게시판은 GitHub에서 상세가 안 열려 뺀다)
    via_browser = {c[0] for c in browser_cities} | set(sources)
    # 이번에 새로 잡힌 것 + 최근 3일 안에 잡혔는데 아직 상세를 안 읽은 것(이 기능 전 저장분, 한 번만 — 실패도 기록돼 다시 안 읽음)
    since = (now - dt.timedelta(days=DETAIL_BACKFILL_DAYS)).isoformat()
    fresh = [x for x in out.values() if x["tier"] in ("A", "B") and not x.get("baseline") and x["city"] not in via_browser
             and (x.get("isNew") or (str(x.get("firstSeen")) >= since and "detail" not in x and "detailError" not in x))
             and not any(x["url"].startswith(b) for b in HOMEPAGE_BOARDS)]
    fresh.sort(key=lambda x: (not x.get("isNew"), x["tier"]))
    details = read_details(fresh, get, sleep) if get and fresh else None
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    items = sorted((x for x in out.values() if str(x.get("firstSeen")) >= keep_from),
                   key=lambda x: (str(x.get("date") or ""), x["id"]), reverse=True)[:KEEP_MAX]
    failed = [c for c in checks if c["status"] == "failed"]
    status = "failed" if len(failed) == len(checks) else "partial" if any(c["status"] != "ok" for c in checks) else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "items": items, "seen": seen,
            "rules": RULES, "cities": len(cities) + len(browser_cities), **({"details": details} if details else {})}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("kr-local", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-local-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    browser = None
    if token:
        try:
            browser = private_store.get("kr-local-browser", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-local-browser::브라우저 수집 문서 조회 실패({e}) — 그 시·군은 미확인")
    import requests
    doc = run(now=now, previous=previous, browser=browser, get=requests.get)
    new = [x for x in doc["items"] if x.get("isNew")]
    tiers = {t: sum(1 for x in new if x["tier"] == t) for t in "ABC"}
    ok = [c["source"] for c in doc["checks"] if c["status"] == "ok"]
    bad = [f"{c['source']}({c.get('error') if c['status'] == 'failed' else '일부'})" for c in doc["checks"] if c["status"] != "ok"]
    det = doc.get("details") or {}
    print(f"::notice title=kr-local::상태 {doc['status']} · 시·군 {len(ok)}/{len(doc['checks'])} 정상 · 새 고시·공고 {tiers} · 보관 {len(doc['items'])}"
          + (f" · 상세 읽음 {det.get('read', 0)}·실패 {det.get('failed', 0)}" if det else "")
          + (f" · 미확인 {', '.join(bad)}" if bad else ""))
    if not token:
        print("::warning title=kr-local-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("지자체 고시·공고 전체 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-local", doc, token)
    print(f"::notice title=kr-local-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
