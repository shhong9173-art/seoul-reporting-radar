"""출입처 임원 명단 변화 감시 (OpenDART 정기보고서 '임원 현황').

분기·반기·사업보고서의 임원 현황을 바로 앞 보고서와 비교해 새로 보인 임원·빠진 임원·직위 변경을 남기고, 경력·관계 칸에서
기사로 이어질 수 있는 표시를 붙인다. 선배 '매의눈'이 보고서 임원 명단에서 한 회사 전 대표의 이사 등재를 잡은 것과 같은 일을
출입처 회사에 한다(기자 요청 11-05). 출입처 출신이 다른 회사 이사로 가는 반대 방향은 kr_exec_market.py.

원천
- 임원 현황 API(exctvSttus): 보고서 제출 여부·접수번호, 원문을 못 읽을 때 대신 쓰는 등기임원 줄
- 보고서 원문(document.xml)의 '가. 임원 현황': 등기·미등기 표와 '보고서 제출일 현재 변동사항'(기준일 뒤 제출일까지 바뀐 임원).
  큰 회사는 API에 등기임원만 있다(11-05 probe 171·172: 현대차 API 12명, 원문 등기 12명·미등기 446명 — 기아·현대위아·현대제철·
  포스코홀딩스·한국타이어·금호타이어·두산에너빌리티·SK이노베이션도 API는 등기만).

표시(판정이 아니라 읽을 거리 — 기자가 판단한다)
- 오너 일가: '최대주주와의 관계' 칸의 본인·친인척·특수관계인 등(원문 글자 그대로). 이름·성으로 추정하지 않는다.
- 주의 회사 출신: 경력 칸에 data/kr_exec_watch.json의 회사(기자가 따로 정한 곳만 — 11-05 기준 비어 있음)
- 경쟁사 출신: 경력 칸에 다른 출입처(같은 그룹 계열은 뺌) 또는 해외 경쟁사 이름
- 전관: 경력 칸에 정부 부처·규제기관·검찰·법원·국회·대통령실
- 임기 중 빠짐: 바로 앞 보고서의 등기임원이 임기 만료일 전에 명단에서 빠짐
- 다른 출입처 임원: 같은 사람(이름·출생년월)이 다른 출입처 명단에도 있음

원칙
- 공개 공시다. 명단에 '새로 보임'은 두 보고서 기준일 사이에 바뀌었다는 뜻일 뿐 선임일·사유가 아니다 — 회사 확인.
- 같은 사람은 이름(띄어쓰기·괄호 뺌)과 출생년월이 같을 때만. 표 형식이 바뀌어 새로·빠짐이 명단(12명 이상)의 60%를 넘으면 항목을 만들지 않는다.
- 미제출·조회 실패·원문 못 읽음은 0건이 아니라 미확인이다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import earnings_compare as ec  # noqa: E402  (call, TransientError, target_period, REPORTS)
import governance_watch as gw  # noqa: E402  (resolve_codes)

SCHEMA = "kr_exec/v1"
API = ec.API
KST = ec.KST
WATCH_FILE = ROOT / "data" / "kr_exec_watch.json"
KEEP_DAYS = 120
DOC_BUDGET = 40          # 원문 내려받기 한 실행 한도(11-05 실측 원문 1개 20초 안팎) — 넘으면 다음 실행(대기, 0건 아님)
DOC_TIMEOUT = 150
PAUSE = 0.3
PROGRESS = bool(os.environ.get("KR_EXEC_PROGRESS"))  # 회사별 걸린 시간(이름 없음)을 stderr로
MIDTERM_DAYS = 60        # 임기 만료일이 앞 보고서 기준일 뒤 이만큼 넘게 남았는데 빠지면 '임기 중 빠짐'
FORMAT_SHIFT = (0.6, 12)  # 명단 12명 이상에서 새로+빠짐이 60%를 넘으면 표 형식 변화로 보고 항목을 만들지 않는다
COUNT_SHIFT = (5, 0.10)  # 미등기 임원 수가 5명 이상이면서 10% 넘게 바뀌면 '임원 수 변화'

AS_OF = {"11013": "03-31", "11012": "06-30", "11014": "09-30", "11011": "12-31"}
# 바로 앞 보고서: 3분기 ← 반기 ← 1분기 ← 전년 사업보고서 ← 전년 3분기
BASE = {"11014": (0, "11012"), "11012": (0, "11013"), "11013": (-1, "11011"), "11011": (0, "11014")}
# 3분기(7~9월)·반기(4~6월) 사이 변화는 수시 인사(중간 영입·경질)라 더 무겁게 본다. 1분기·사업보고서는 정기 주총·연말 정기 인사 철.
MID_SEASON = {"11014", "11012"}

# 출입처(정기보고서를 내는 곳) — (회사 이름(DART), 팀, 그룹)
BEATS = [
    ("현대자동차", "자동차", "현대차그룹"), ("기아", "자동차", "현대차그룹"), ("현대모비스", "자동차", "현대차그룹"),
    ("현대위아", "자동차", "현대차그룹"), ("HL만도", "자동차", "HL"), ("KG모빌리티", "자동차", "KG"),
    ("한국타이어앤테크놀로지", "자동차", "한국앤컴퍼니"), ("넥센타이어", "자동차", "넥센"), ("금호타이어", "자동차", "금호타이어"),
    ("포스코홀딩스", "철강·비철", "포스코"), ("포스코", "철강·비철", "포스코"), ("현대제철", "철강·비철", "현대차그룹"),
    ("KG스틸", "철강·비철", "KG"), ("세아홀딩스", "철강·비철", "세아"), ("세아제강", "철강·비철", "세아"),
    ("동국제강", "철강·비철", "동국"), ("동국씨엠", "철강·비철", "동국"), ("고려아연", "철강·비철", "고려아연"),
    ("영풍", "철강·비철", "영풍"),
    ("HD현대일렉트릭", "전력·에너지", "HD현대"), ("엘에스일렉트릭", "전력·에너지", "LS"), ("대한전선", "전력·에너지", "대한전선"),
    ("LS전선", "전력·에너지", "LS"), ("LS MnM", "전력·에너지", "LS"), ("LS", "전력·에너지", "LS"),
    ("두산에너빌리티", "전력·에너지", "두산"), ("GS", "전력·에너지", "GS"), ("GS칼텍스", "정유", "GS"),
    ("한화솔루션", "화학·소재", "한화"), ("OCI", "화학·소재", "OCI"), ("OCI홀딩스", "화학·소재", "OCI"),
    ("태광산업", "화학·소재", "태광"), ("동성케미칼", "화학·소재", "동성"), ("LG화학", "화학·소재", "LG"),
    ("롯데케미칼", "화학·소재", "롯데"), ("금호석유화학", "화학·소재", "금호석유화학"),
    ("S-Oil", "정유", "S-OIL"), ("SK이노베이션", "정유", "SK"), ("HD현대오일뱅크", "정유", "HD현대"),
]
SPELLINGS = {"동성케미칼": ["동성케미컬"], "S-Oil": ["에쓰-오일", "에쓰오일"]}
GROUP = {name: group for name, _, group in BEATS}
# 경쟁 구역: 같은 구역의 다른 그룹 출신만 '경쟁사 출신'(11-05 probe 173: 현대모비스 임원 경력의 S-Oil은 경쟁사가 아니다). 화학·정유는 석유화학으로 겹친다.
AREA = {"자동차": "자동차", "철강·비철": "철강·비철", "전력·에너지": "전력", "화학·소재": "화학·정유", "정유": "화학·정유"}
TEAM = {name: team for name, team, _ in BEATS}
UNLISTED_AREA = {"한국GM": {"자동차"}, "르노코리아": {"자동차"}, "벤츠코리아": {"자동차"}, "BMW코리아": {"자동차"}, "폭스바겐코리아": {"자동차"},
                 "혼다코리아": {"자동차"}, "DL케미칼": {"화학·정유"}}
SHORT = {"현대자동차": "현대차", "한국타이어앤테크놀로지": "한국타이어", "엘에스일렉트릭": "LS일렉트릭", "S-Oil": "S-OIL", "태광산업": "태광"}

# 경력 칸에서 찾는 출입처 이름(옛 이름·같은 그룹 회사 포함) → (출입처, 그룹). 같은 그룹이면 경쟁사로 보지 않는다.
RIVALS = {
    "현대차그룹": ["현대자동차", "현대차", "기아자동차", "기아차", "기아", "현대모비스", "현대위아", "현대제철", "현대하이스코"],
    "포스코": ["포스코홀딩스", "포스코", "POSCO"],
    "LS": ["LS전선", "LS산전", "LS일렉트릭", "LS ELECTRIC", "LS MnM", "LS니꼬동제련", "LS-Nikko", "LS엠트론", "LS"],
    "GS": ["GS칼텍스", "LG칼텍스", "GS에너지", "GS"],
    "OCI": ["OCI홀딩스", "OCI", "동양제철화학"],
    "세아": ["세아홀딩스", "세아제강", "세아베스틸", "세아창원특수강"],
    "동국": ["동국제강", "동국씨엠", "유니온스틸"],
    "KG": ["KG스틸", "동부제철", "KG모빌리티", "쌍용자동차", "쌍용차"],
    "HD현대": ["HD현대일렉트릭", "현대일렉트릭", "HD현대오일뱅크", "현대오일뱅크", "HD현대중공업", "현대중공업"],
    "한국앤컴퍼니": ["한국타이어앤테크놀로지", "한국타이어", "한국앤컴퍼니"],
    "넥센": ["넥센타이어"], "금호타이어": ["금호타이어"], "HL": ["HL만도", "만도"],
    "고려아연": ["고려아연"], "영풍": ["영풍"], "대한전선": ["대한전선"], "두산": ["두산에너빌리티", "두산중공업"],
    "한화": ["한화솔루션", "한화케미칼", "한화큐셀", "한화첨단소재"], "태광": ["태광산업"], "동성": ["동성케미칼", "동성케미컬"],
    "LG": ["LG화학", "LG Chem"], "롯데": ["롯데케미칼", "호남석유화학", "롯데첨단소재"],
    "금호석유화학": ["금호석유화학", "금호석화"], "S-OIL": ["S-OIL", "S-Oil", "에쓰오일", "에쓰-오일"],
    "SK": ["SK이노베이션", "SK에너지", "SK지오센트릭", "SK종합화학", "SK온"],
    # 비상장 출입처(정기보고서는 없지만 경력 칸에 나온다)
    "한국GM": ["한국GM", "한국지엠", "GM대우", "GM Korea"], "르노코리아": ["르노코리아", "르노삼성"],
    "벤츠코리아": ["메르세데스-벤츠 코리아", "메르세데스벤츠코리아", "벤츠코리아"], "BMW코리아": ["BMW코리아", "BMW 코리아"],
    "폭스바겐코리아": ["폭스바겐코리아", "폭스바겐그룹코리아"], "혼다코리아": ["혼다코리아"], "DL케미칼": ["DL케미칼"],
}
# 해외 경쟁사(완성차·부품·타이어·철강·비철·전력기기·전선·화학·정유). 그 회사의 대주주·합작 상대는 뺀다(S-OIL ← 아람코).
FOREIGN = ["테슬라", "Tesla", "BYD", "비야디", "CATL", "도요타", "토요타", "Toyota", "혼다", "Honda", "닛산", "Nissan", "폭스바겐", "Volkswagen",
           "메르세데스", "Mercedes", "벤츠", "다임러", "Daimler", "BMW", "제너럴모터스", "General Motors", "GM", "포드", "Ford", "스텔란티스",
           "Stellantis", "르노", "Renault", "리비안", "Rivian", "루시드", "Lucid", "샤오미", "Xiaomi", "지리자동차", "Geely", "보쉬", "Bosch",
           "콘티넨탈", "Continental", "덴소", "Denso", "마그나", "Magna", "ZF", "발레오", "Valeo", "미쉐린", "Michelin", "브리지스톤",
           "Bridgestone", "굿이어", "Goodyear", "일본제철", "신일본제철", "닛폰스틸", "Nippon Steel", "바오산", "바오우", "Baosteel", "Baowu",
           "아르셀로미탈", "ArcelorMittal", "US스틸", "U.S. Steel", "뉴코어", "Nucor", "글렌코어", "Glencore", "유미코아", "Umicore", "지멘스",
           "Siemens", "ABB", "히타치", "Hitachi", "GE버노바", "GE Vernova", "제너럴일렉트릭", "General Electric", "GE", "슈나이더", "Schneider",
           "프리즈미안", "Prysmian", "넥상스", "Nexans", "이튼", "Eaton", "바스프", "BASF", "다우케미칼", "Dow", "듀폰", "DuPont", "Dupont", "사빅",
           "SABIC", "아람코", "Aramco", "엑손모빌", "ExxonMobil", "Exxon", "쉘", "Shell", "시노펙", "Sinopec", "이네오스", "INEOS"]
FOREIGN_OWNER = {"S-Oil": {"아람코", "Aramco"}}
# 전관: 정부 부처·규제기관·수사기관·법원·국회·대통령실(공기업·국책은행은 뺀다). '검사'만으로는 품질검사와 섞여 수사기관 낱말만.
GOV = re.compile(r"산업통상자원부|산업통상부|산업자원부|지식경제부|통상교섭본부|기획재정부|재정경제부|공정거래위원회|공정위|국세청|관세청|"
                 r"금융감독원|금감원|금융위원회|금융위|검찰|검사장|부장검사|지방검찰청|고등검찰청|[가-힣]{1,3}지검|[가-힣]{1,3}고검|"
                 r"지방법원|고등법원|대법원|법원장|판사|대법관|헌법재판|환경부|기후에너지환경부|국토교통부|국토해양부|고용노동부|노동부|감사원|"
                 r"청와대|대통령실|대통령비서실|국무조정실|국무총리|국회의원|국가정보원|국정원|경찰청|조달청|특허청|방위사업청|외교부|외교통상부|"
                 r"중소벤처기업부|장관|차관")
OWNER_REL = re.compile(r"본인|친인척|친족|자녀|배우자|형제|자매|부친|모친|장남|차남|삼남|장녀|차녀|사위|며느리|혈족|인척|특수관계(인|자)")
TOP = re.compile(r"(?<!부)사장|회장|대표이사|대표집행|\bC[EFOTS]O\b")
RANK = ["이사대우", "상무보", "이사", "상무", "전무", "부사장", "사장", "부회장", "회장"]
REGISTERED = re.compile(r"사내이사|사외이사|독립이사|기타비상무|비상무이사|감사")
OK_SUFFIX = ("㈜", "(주)", "주식회사", "그룹", "에서", "의", "社", "사장", "부사장", "상무", "전무", "대표", "회장", "부회장", "이사", "본부",
             "사업", "연구", "법인", "경영", "전략", "출신", "근무", "재직", "팀", "실", "센터", "공장", "제철소", "담당", "부문", "고문")
CELL = re.compile(r"<(TD|TE|TU|TH)\b[^>]*>(.*?)</\1>", re.S | re.I)
ROW = re.compile(r"<TR\b.*?</TR>", re.S | re.I)
TABLE_SPLIT = re.compile(r"(<TABLE\b.*?</TABLE>)", re.S | re.I)


# ---------- text helpers ----------

def clean(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    s = html.unescape(s.replace("&cr;", " "))
    return re.sub(r"\s+", " ", s).strip()


def name_key(name):
    return re.sub(r"\s+|\(.*?\)|（.*?）", "", str(name or ""))


def birth_key(v):
    d = re.findall(r"\d+", str(v or ""))
    if not d or len(d[0]) != 4:
        return ""
    return d[0] + (d[1].zfill(2) if len(d) > 1 and len(d[1]) <= 2 else "")


def person_key(p):
    return f"{name_key(p.get('name'))}|{birth_key(p.get('birth'))}"


def norm_reg(v):
    v = re.sub(r"\s+", "", str(v or ""))
    v = v.replace("독립이사", "사외이사").replace("미등기임원", "미등기")
    if not v or v in ("-", "미등기"):
        return "미등기"
    return v


def norm_ofcps(v):
    return re.sub(r"\s+", "", str(v or "")).replace("독립이사", "사외이사")


def end_day(v):
    d = re.findall(r"\d+", str(v or ""))
    if len(d) >= 3 and len(d[0]) == 4:
        try:
            return dt.date(int(d[0]), int(d[1]), int(d[2]))
        except ValueError:
            return None
    return None


def mentions(text, alias):
    """alias가 낱말로 나오는가: 앞은 한글·영문이 아니고, 뒤는 영문이 아니며 한글이면 직함·조직 낱말만 허용(포스코퓨처엠 ≠ 포스코)."""
    t = str(text or "")
    for m in re.finditer(re.escape(alias), t):
        before = t[m.start() - 1] if m.start() else " "
        after = t[m.end()] if m.end() < len(t) else " "
        if re.match(r"[가-힣A-Za-z0-9]", before):
            continue
        if re.match(r"[A-Za-z0-9]", after):
            continue
        if re.match(r"[가-힣]", after) and not t.startswith(OK_SUFFIX, m.end()):
            continue
        return (m.start(), m.end())
    return None


def rank_of(ofcps):
    o = norm_ofcps(ofcps)
    hits = [i for i, r in enumerate(RANK) if r in o]
    return max(hits) if hits else None


def load_watch(path=WATCH_FILE):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for c in doc.get("companies") or []:
        if isinstance(c, dict) and c.get("name"):
            out.append({"name": c["name"], "aliases": [a for a in c.get("aliases") or [c["name"]] if a], "reason": c.get("reason", "")})
    return out


# ---------- flags ----------

def career_flags(company, career, watch):
    """경력 칸에서 주의 회사·경쟁사·해외 경쟁사·전관 낱말을 찾는다(원문 글자를 그대로 붙인다)."""
    text = str(career or "")
    flags, taken = [], []
    for w in watch:
        for a in w["aliases"]:
            if mentions(text, a):
                flags.append({"kind": "주의 회사 출신", "match": a, "text": f"경력에 '{a}' — {w['reason']}".strip(" —")})
                break
    own = GROUP.get(company)
    rivals, others = [], []
    my_area = AREA.get(TEAM.get(company))
    for group, aliases in RIVALS.items():
        for a in sorted(aliases, key=len, reverse=True):
            span = mentions(text, a)
            if span:
                taken.append(span)
                if group != own:
                    (rivals if my_area in group_areas(group) else others).append(a)
                break
    if rivals:
        flags.append({"kind": "경쟁사 출신", "match": rivals, "text": "경력에 같은 업종 출입처 " + "·".join(f"'{a}'" for a in rivals)})
    if others:
        flags.append({"kind": "다른 출입처 출신", "match": others, "text": "경력에 다른 업종 출입처 " + "·".join(f"'{a}'" for a in others)})
    foreign = []
    skip = FOREIGN_OWNER.get(company, set())
    for a in FOREIGN:
        span = mentions(text, a)
        if not span or a in skip or any(s <= span[0] < e for s, e in taken):
            continue
        if a not in foreign and not any(a in f or f in a for f in foreign):
            foreign.append(a)
    if foreign:
        flags.append({"kind": "해외 경쟁사 출신", "match": foreign[:4], "text": "경력에 " + "·".join(f"'{a}'" for a in foreign[:4])})
    gov = []
    for m in GOV.finditer(text):
        if m.group(0) not in gov:
            gov.append(m.group(0))
    if gov:
        flags.append({"kind": "전관", "match": gov[:4], "text": "경력에 " + "·".join(f"'{g}'" for g in gov[:4])})
    return flags


def group_areas(group):
    return {AREA.get(team) for name, team, g in BEATS if g == group} | UNLISTED_AREA.get(group, set())


def owner_flag(p):
    rel = str(p.get("rel") or "")
    if OWNER_REL.search(rel):
        return {"kind": "오너 일가", "text": f"최대주주와의 관계 '{clean(rel)}'(원문 그대로)"}
    return None


# ---------- document parsing ----------

def _cols(head):
    """머리 칸 이름 → 뜻. 소유주식수는 아래 줄에서 두 칸(의결권 있는·없는)으로 나뉜다."""
    want = {"name": r"성\s*명|이\s*름", "sex": r"성\s*별", "birth": r"출생", "ofcps": r"직\s*위", "reg": r"등기",
            "fte": r"상근", "job": r"담당", "career": r"경력", "shares": r"소유\s*주식", "rel": r"최대\s*주주", "period": r"재직",
            "end": r"임기"}
    cols = {}
    for i, h in enumerate(head):
        for k, pat in want.items():
            if k not in cols and re.search(pat, h):
                if k == "reg" and re.search(r"등기임원\s*여부|등기\s*여부|등기임원여부", h) is None and "등기" not in h:
                    continue
                cols[k] = i
                break
    return cols


def _person_rows(rows):
    # 머리 줄이 첫 줄이 아닐 수 있다(11-05 probe 173d: 포스코홀딩스·포스코·넥센·금호타이어는 기준일 줄이 같은 표 안에 먼저 온다)
    for hi, head in enumerate(rows[:3]):
        cols = _cols(head)
        if {"name", "ofcps", "career", "birth"} <= set(cols):
            break
    else:
        return None
    sh = cols.get("shares")
    out = []
    for r in rows[hi + 1:]:
        if len(r) < len(head) - 1:
            continue
        shift = 1 if sh is not None and len(r) == len(head) + 1 else 0

        def at(k):
            i = cols.get(k)
            if i is None:
                return ""
            j = i + shift if (sh is not None and i > sh) else i
            return r[j] if j < len(r) else ""
        name, birth = at("name"), at("birth")
        if not name or not re.search(r"\d{4}", birth) or re.search(r"합\s*계|의결권", name):
            continue
        reg = norm_reg(at("reg")) if "reg" in cols else "미등기"
        out.append({"name": name, "birth": birth, "sex": at("sex"), "ofcps": at("ofcps"), "reg": reg, "fte": at("fte"),
                    "job": at("job")[:80], "career": at("career")[:400], "rel": at("rel")[:60], "period": at("period")[:30],
                    "end": at("end")[:20]})
    return out


def _change_rows(rows):
    head = rows[0]
    if not any(re.search(r"성\s*명|이\s*름", h) for h in head) or any("경력" in h for h in head):
        return None
    ix = {k: next((i for i, h in enumerate(head) if re.search(p, h)), None) for k, p in
          {"kind": r"구\s*분|변동", "name": r"성\s*명|이\s*름", "ofcps": r"직\s*위", "job": r"담당", "note": r"비\s*고|사\s*유|일\s*자|일$"}.items()}
    out, last = [], ""
    for r in rows[1:]:
        if not any(r):
            continue
        if ix["kind"] == 0 and len(r) == len(head) - 1:
            r = [last] + r      # '구분' 칸이 위 줄과 합쳐진 줄(rowspan)
        if ix["kind"] is not None and ix["kind"] < len(r) and r[ix["kind"]]:
            last = r[ix["kind"]]

        def at(k):
            i = ix.get(k)
            return r[i] if i is not None and i < len(r) else ""
        if not at("name") or at("name") in ("-", "해당사항 없음", "해당사항없음"):
            continue
        out.append({"kind": at("kind")[:20], "name": at("name")[:30], "ofcps": at("ofcps")[:30], "job": at("job")[:60], "note": at("note")[:60]})
    return out


def parse_document(text):
    """'임원 현황' 구역의 사람 표(등기·미등기)와 '보고서 제출일 현재 변동사항'(표 또는 글)을 읽는다."""
    persons, changes, notes = [], [], []
    started, want_change = False, False
    for part in TABLE_SPLIT.split(text):
        if part[:6].upper() == "<TABLE":
            rows = [[clean(c[1]) for c in CELL.findall(tr)] for tr in ROW.findall(part)]
            rows = [r for r in rows if any(r)]
            if not rows:
                continue
            head = " ".join(rows[0])
            if started and re.search(r"직원\s*수|평균\s*근속|근속\s*연수", head):
                break
            ppl = _person_rows(rows) if len(rows) > 1 else None
            # 구역 시작은 '등기임원 여부' 칸이 있는 표(VIII. 임원 현황)부터. 앞 장(이사회·감사위원회)의 이름·경력 표는 건너뛴다
            # (11-05 probe 173e: 포스코홀딩스·포스코·넥센·금호타이어는 이사회 장의 '성명·출생년월·직위·주요경력' 표가 먼저 나와 엉뚱한 곳에서 시작했다)
            if ppl is not None and not started:
                hc = _cols(next((r for r in rows[:3] if _cols(r).get("name") is not None), rows[0]))
                # 두산에너빌리티(탐침 173f)는 이사회 장 표에도 '등기임원여부'가 있다 — 임원 현황 표는 소유주식수·최대주주 관계 칸이 있다
                if "reg" not in hc or not ({"shares", "rel"} & set(hc)):
                    continue
            if ppl is not None:
                started = True
                persons += ppl
                want_change = False
                continue
            if started and want_change:
                ch = _change_rows(rows)
                if ch:
                    changes += ch
                    want_change = False
            continue
        t = clean(part)
        if not started:
            continue
        if re.search(r"나\.\s*직원|직원\s*등\s*(의\s*)?현황", t):
            m = re.search(r"나\.\s*직원|직원\s*등\s*(의\s*)?현황", t)
            t = t[:m.start()]
            stop = True
        else:
            stop = False
        m = re.search(r"(보고서\s*제출일\s*현재[^.]{0,20}변동|변동된\s*(미?등기)?임원|이후\s*보고서\s*제출일)", t)
        if m:
            want_change = True
            tail = t[m.start():m.start() + 400].strip()
            if re.search(r"신규|선임|퇴임|사임|추가|변경|승진|해임|전보|위촉", tail[20:]):
                notes.append(tail)
        if stop:
            break
    return persons, changes, notes


def fetch_document(key, rcept, *, get, sleep, want="임원"):
    """document.xml(zip) → 본문 파일 글자들('임원' 낱말이 든 파일, 큰 순). 실패는 None과 이유.
    11-05 probe 173: 포스코홀딩스·포스코·넥센타이어·금호타이어 반기보고서는 zip 안 가장 큰 파일이 본문이 아니었다."""
    last = None
    for attempt in range(2):
        try:
            r = get(f"{API}/document.xml", params={"crtfc_key": key, "rcept_no": rcept}, headers=ec.HEADERS, timeout=DOC_TIMEOUT)
            if getattr(r, "status_code", 200) >= 500:
                raise ec.TransientError(f"HTTP {r.status_code}")
            body = r.content
            if not body.startswith(b"PK"):
                return None, f"원문 대신 응답 {body[:80].decode('utf-8', 'replace')}"
            z = zipfile.ZipFile(io.BytesIO(body))
            texts = []
            for n in sorted(z.namelist(), key=lambda n: z.getinfo(n).file_size, reverse=True):
                raw = z.read(n)
                text = None
                for enc in ("utf-8", "cp949"):
                    try:
                        text = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                text = text if text is not None else raw.decode("utf-8", "replace")
                if not want or want in text:
                    texts.append(text)
            return (texts or None), (None if texts else f"원문 파일에 '{want}' 낱말 없음")
        except (ec.TransientError, OSError, ValueError, zipfile.BadZipFile) as e:
            last = f"{type(e).__name__}: {str(e)[:60]}"
        except Exception as e:  # noqa: BLE001 — requests errors: unconfirmed, not zero
            last = f"{type(e).__name__}: {str(e)[:60]}"
        if attempt == 0:
            sleep(3)
    return None, last


def api_people(body):
    out = []
    for x in (body or {}).get("list") or []:
        out.append({"name": x.get("nm") or "", "birth": x.get("birth_ym") or "", "sex": x.get("sexdstn") or "", "ofcps": x.get("ofcps") or "",
                    "reg": norm_reg(x.get("rgist_exctv_at")), "fte": x.get("fte_at") or "", "job": clean(x.get("chrg_job"))[:80],
                    "career": clean(x.get("main_career"))[:400], "rel": clean(x.get("mxmm_shrholdr_relate"))[:60],
                    "period": clean(x.get("hffc_pd"))[:30], "end": clean(x.get("tenure_end_on"))[:20]})
    return out


def latest_rcept(body):
    return max((x.get("rcept_no") or "" for x in (body or {}).get("list") or []), default="") or None


# ---------- one company ----------

def api_roster(key, code, year, report, *, get, sleep):
    """(상태, API 줄, 접수번호). 미제출(013)은 'no_data'."""
    st, body = ec.call("exctvSttus.json", {"corp_code": code, "bsns_year": str(year), "reprt_code": report},
                       get=lambda u, params, **kw: get(u, params={"crtfc_key": key, **params}, **kw), sleep=sleep)
    sleep(PAUSE)
    if st != "ok":
        return "no_data", [], None
    return "ok", api_people(body), latest_rcept(body)


def doc_roster(key, rcept, api, *, get, sleep, budget):
    """원문 표로 명단을 만든다(못 읽으면 API 줄). (상태, 사람들, 변동 표, 변동 글, 범위 설명). budget: 남은 원문 수(한 칸 list)."""
    if budget[0] <= 0:
        return "waiting", api, [], [], "원문 대기"
    budget[0] -= 1
    texts, err = fetch_document(key, rcept, get=get, sleep=sleep) if rcept else (None, "접수번호 없음")
    sleep(PAUSE)
    reg_api = sum(1 for p in api if p["reg"] != "미등기")
    for text in texts or []:
        ppl, changes, notes = parse_document(text)
        reg_doc = sum(1 for p in ppl if p["reg"] != "미등기")
        if ppl and reg_doc >= max(1, reg_api // 2):
            unreg = len(ppl) - reg_doc
            return "ok", ppl, changes, notes, f"원문 표(등기 {reg_doc}·미등기 {unreg})"
    if texts:
        err = "원문에서 임원 표를 못 찾음"
        if PROGRESS:   # 표 머리 줄만(이름 없음) — 왜 못 찾았는지
            for text in texts[:3]:
                for t in re.findall(r"<TABLE\b.*?</TABLE>", text, re.S | re.I):
                    if "경력" not in t or "직위" not in t:
                        continue
                    rows = [[clean(c[1]) for c in CELL.findall(tr)] for tr in ROW.findall(t)][:4]
                    shown = [" ".join(r)[:120] if re.search(r"성\s*명|이\s*름|직\s*위|경\s*력", " ".join(r)) else f"(데이터 줄 {len(r)}칸)" for r in rows]
                    print(f"[kr-exec] 원문 {len(text)}자 표: {' || '.join(shown)}", file=sys.stderr, flush=True)
    unreg = sum(1 for p in api if p["reg"] == "미등기")
    return "ok", api, [], [], f"API 줄만(등기 {len(api) - unreg}·미등기 {unreg}) — {err}"


def diff(cur, base):
    """새로 보인·빠진·직위·등기 변경. 한쪽에 미등기 줄이 없으면 등기임원끼리만 비교한다."""
    full = any(p["reg"] == "미등기" for p in cur) and any(p["reg"] == "미등기" for p in base)
    if not full:
        cur = [p for p in cur if p["reg"] != "미등기"]
        base = [p for p in base if p["reg"] != "미등기"]
    a = {person_key(p): p for p in base}
    b = {person_key(p): p for p in cur}
    new = [b[k] for k in b if k not in a]
    gone = [a[k] for k in a if k not in b]
    # 이름 표기만 바뀐 사람(한자·영문 덧붙임 등): 출생년월·직위가 같고 이름 앞 두 글자가 같으면 같은 사람
    for p in list(new):
        twin = next((g for g in gone if birth_key(g["birth"]) == birth_key(p["birth"]) and norm_ofcps(g["ofcps"]) == norm_ofcps(p["ofcps"])
                     and name_key(g["name"])[:2] == name_key(p["name"])[:2]), None)
        if twin:
            new.remove(p)
            gone.remove(twin)
    changed = []
    for k in set(a) & set(b):
        x, y = a[k], b[k]
        if norm_ofcps(x["ofcps"]) != norm_ofcps(y["ofcps"]) or norm_reg(x["reg"]) != norm_reg(y["reg"]):
            changed.append((x, y))
    return new, gone, changed, full


def season_of(report):
    return "mid" if report in MID_SEASON else "annual"


def period_label(year, report):
    return f"{year}년 {ec.REPORTS[report]['label']}({AS_OF[report][:2].lstrip('0')}-{AS_OF[report][3:]} 기준)"


def who(p):
    bits = [p["name"]]
    if birth_key(p["birth"])[:4]:
        bits.append(f"{birth_key(p['birth'])[:4]}년생")
    role = norm_ofcps(p["ofcps"]) or "직위 미기재"
    reg = "등기 " + p["reg"] if p["reg"] != "미등기" else "미등기"
    return f"{' '.join(bits)} {role}({reg}{'·' + p['fte'] if p.get('fte') else ''})"


def company_events(company, code, cur_label, base_label, season, cur, base, changes, notes, *, url, base_as_of, watch, others):
    """한 회사의 변화 → 항목. others: {다른 출입처: set(사람 키)}"""
    new, gone, changed, full = diff(cur, base)
    size = max(len(base), 1)
    events = []
    short = SHORT.get(company, company)
    if (len(new) + len(gone)) > FORMAT_SHIFT[0] * size and size >= FORMAT_SHIFT[1]:
        events.append({"kind": "명단 형식 변화", "tier": "C", "company": short, "dartName": company, "corpCode": code,
                       "text": f"{short} {cur_label} 임원 명단이 {base_label}와 60% 넘게 달라짐(새로 {len(new)}·빠짐 {len(gone)} / {len(base)}명) — "
                               "표 형식·이름 표기 변화일 수 있어 항목을 만들지 않음. 원문 확인",
                       "url": url, "key": "format"})
        return events, {"new": len(new), "gone": len(gone), "changed": len(changed), "full": full, "suppressed": True}
    mid = season == "mid"
    for p in new:
        flags = [f for f in [owner_flag(p)] if f] + career_flags(company, p["career"], watch)
        cross = [SHORT.get(o, o) for o, keys in others.items() if o != company and person_key(p) in keys and GROUP.get(o) != GROUP.get(company)]
        if cross:
            flags.append({"kind": "다른 출입처 임원", "text": "같은 이름·출생년월이 " + "·".join(cross) + " 명단에도 있음"})
        kinds = {f["kind"] for f in flags}
        top = bool(TOP.search(norm_ofcps(p["ofcps"])))
        if kinds & {"오너 일가", "주의 회사 출신"} or (mid and (top or "경쟁사 출신" in kinds)):
            tier = "A"
        elif p["reg"] != "미등기" or top or kinds:
            tier = "B"
        else:
            tier = "C"
        events.append(_event("새 임원", tier, company, code, p, flags, url,
                             f"{short} {cur_label} 임원 명단에 새로 보임 — {who(p)}"
                             f"{' · 담당 ' + p['job'] if p.get('job') and p['job'] != '-' else ''}"
                             f"{' · 경력 「' + p['career'][:160] + '」' if p.get('career') and p['career'] != '-' else ''}"
                             f" · {base_label}에는 없음"))
    for p in gone:
        flags = [f for f in [owner_flag(p)] if f]
        end = end_day(p.get("end"))
        if p["reg"] != "미등기" and end and base_as_of and end > base_as_of + dt.timedelta(days=MIDTERM_DAYS):
            flags.append({"kind": "임기 중 빠짐", "text": f"임기 만료일 {end.isoformat()} 전에 명단에서 빠짐"})
        kinds = {f["kind"] for f in flags}
        top = bool(TOP.search(norm_ofcps(p["ofcps"])))
        if kinds & {"오너 일가", "임기 중 빠짐"} or (mid and top):
            tier = "A"
        elif p["reg"] != "미등기" or top:
            tier = "B"
        else:
            tier = "C"
        events.append(_event("명단에서 빠짐", tier, company, code, p, flags, url,
                             f"{short} {cur_label} 임원 명단에서 빠짐 — {base_label} {who(p)}"
                             f"{' · 담당 ' + p['job'] if p.get('job') and p['job'] != '-' else ''}"
                             f"{' · 임기 만료일 ' + p['end'] if p.get('end') and p['end'] != '-' else ''}"))
    for x, y in changed:
        flags = [f for f in [owner_flag(y)] if f]
        up = (rank_of(y["ofcps"]) or 0) > (rank_of(x["ofcps"]) or 0)
        reg_up = x["reg"] == "미등기" and y["reg"] != "미등기"
        # 등기임원(이사회)에서 내려와 미등기로 남은 사람(11-05 probe 173: 기아 1분기→반기 사내이사 1명이 빠지고 직위 변경 1건)
        reg_down = x["reg"] != "미등기" and y["reg"] == "미등기"
        end = end_day(x.get("end"))
        if reg_down and end and base_as_of and end > base_as_of + dt.timedelta(days=MIDTERM_DAYS):
            flags.append({"kind": "임기 중 빠짐", "text": f"등기임원 임기 만료일 {end.isoformat()} 전에 이사회에서 내려와 미등기로 남음"})
        top = bool(TOP.search(norm_ofcps(y["ofcps"]))) and not TOP.search(norm_ofcps(x["ofcps"]))
        kind = "등기임원 됨" if reg_up else "등기임원에서 내려옴" if reg_down else "직위 변경"
        if flags or (mid and top):
            tier = "A"
        elif reg_up or reg_down or top:
            tier = "B"
        else:
            tier = "C"
        events.append(_event(kind, tier, company, code, y, flags, url,
                             f"{short} {cur_label} 임원 {kind} — {y['name']} {norm_ofcps(x['ofcps'])}({x['reg']}) → {norm_ofcps(y['ofcps'])}({y['reg']})"
                             f"{' · 승진' if up else ''}", extra={"before": {"ofcps": x["ofcps"], "reg": x["reg"]}}))
    if full:
        n0 = sum(1 for p in base if p["reg"] == "미등기")
        n1 = sum(1 for p in cur if p["reg"] == "미등기")
        if n0 and abs(n1 - n0) >= COUNT_SHIFT[0] and abs(n1 - n0) / n0 > COUNT_SHIFT[1]:
            events.append({"kind": "임원 수 변화", "tier": "B", "company": short, "dartName": company, "corpCode": code, "key": "count",
                           "text": f"{short} 미등기 임원 {n0}→{n1}명({n1 - n0:+d}, {(n1 - n0) / n0 * 100:+.0f}%) · {base_label}→{cur_label}",
                           "url": url, "counts": [n0, n1]})
    roster_keys = {name_key(p["name"]): p for p in cur}
    for c in changes:
        known = roster_keys.get(name_key(c["name"]))
        flags = [f for f in [owner_flag(known)] if f] if known else []
        if known:
            flags += career_flags(company, known["career"], watch)
        kinds = {f["kind"] for f in flags}
        top = bool(TOP.search(norm_ofcps(c["ofcps"])))
        leaving = bool(re.search(r"퇴임|사임|해임|사직|퇴직|면직|임기만료", c["kind"] + c["note"]))
        if kinds & {"오너 일가", "주의 회사 출신"} or (top and leaving and mid):
            tier = "A"
        elif top or kinds:
            tier = "B"
        else:
            tier = "C"
        events.append({"kind": "제출일까지 변동", "tier": tier, "company": short, "dartName": company, "corpCode": code,
                       "key": f"chg|{name_key(c['name'])}|{c['kind']}", "person": {"name": c["name"], "ofcps": c["ofcps"], "job": c["job"]},
                       "flags": flags, "url": url,
                       "text": f"{short} {cur_label} '보고서 제출일 현재 변동사항' — {c['kind'] or '변동'} {c['name']} {c['ofcps']}"
                               f"{' · ' + c['job'] if c['job'] and c['job'] != '-' else ''}{' · ' + c['note'] if c['note'] and c['note'] != '-' else ''}"
                               " (기준일 뒤 제출일까지 바뀐 것)"})
    for n in notes[:2]:
        events.append({"kind": "제출일까지 변동", "tier": "C", "company": short, "dartName": company, "corpCode": code,
                       "key": f"note|{hashlib.sha256(n.encode()).hexdigest()[:10]}", "url": url, "flags": [],
                       "text": f"{short} {cur_label} 원문 주석 — 「{n[:300]}」"})
    return events, {"new": len(new), "gone": len(gone), "changed": len(changed), "full": full, "suppressed": False}


def _event(kind, tier, company, code, p, flags, url, text, extra=None):
    return {"kind": kind, "tier": tier, "company": SHORT.get(company, company), "dartName": company, "corpCode": code,
            "key": f"{kind}|{person_key(p)}", "person": {k: p.get(k) for k in ("name", "birth", "ofcps", "reg", "fte", "job", "career", "rel", "end")},
            "flags": flags, "url": url, "text": text, **(extra or {})}


# ---------- run ----------

PACK = ("name", "birth", "ofcps", "reg", "end", "rel", "job")


def pack(people):
    """다음 분기 비교용 명단 줄(경력은 빼고 짧게)."""
    return [[str(p.get(k) or "")[:30] for k in PACK] for p in people]


def unpack(rows):
    return [{**dict(zip(PACK, r)), "career": "", "fte": "", "sex": ""} for r in rows if isinstance(r, list) and len(r) >= 4]


def run(key, *, now=None, year=None, report=None, previous=None, get=None, sleep=time.sleep, registry=None, table=None, watch=None,
        baseline=False, only=None):
    """baseline=True: 이번 기간 명단만 읽어 저장(항목 없음) — 다음 분기 비교의 앞 보고서로 쓴다. only: 이 회사들만(검증용)."""
    if get is None:
        import requests
        get = requests.get
    now = now or dt.datetime.now(KST)
    stamp = now.isoformat(timespec="seconds")
    if not year or not report:
        year, report = ec.target_period(now)
    dy, base_report = BASE[report]
    base_year = year + dy
    cur_label, base_label = period_label(year, report), period_label(base_year, base_report)
    base_as_of = dt.date(base_year, int(AS_OF[base_report][:2]), int(AS_OF[base_report][3:]))
    season = season_of(report)
    watch = load_watch() if watch is None else watch
    prev = previous if isinstance(previous, dict) and (previous.get("period") or {}).get("report") == report \
        and (previous.get("period") or {}).get("year") == year else {}
    seen = dict(prev.get("seen") or {})
    # 회사별 마지막으로 읽은 명단(기간·접수번호·사람 줄) — 다음 분기의 '앞 보고서'로 다시 쓴다(원문을 또 받지 않음)
    rosters = {k: v for k, v in ((previous or {}).get("rosters") or {}).items() if isinstance(v, dict) and v.get("people")}
    keys = {k: {person_key(p) for p in unpack(v["people"])} for k, v in rosters.items()}
    old = {e["id"]: e for e in (previous or {}).get("events") or [] if isinstance(e, dict) and e.get("id")}
    budget = [DOC_BUDGET]
    names = [n for n, _, _ in BEATS]
    codes, missing = gw.resolve_codes(names, registry, table)
    for name, alts in SPELLINGS.items():
        if name not in codes:
            for alt in alts:
                c2, _ = gw.resolve_codes([alt], registry, table)
                if alt in c2:
                    codes[name] = c2[alt]
                    missing = [m for m in missing if m != name]
    codes.pop("_spellings", None)
    checks, fresh = [], []
    pending = []
    for name in names:
        code = codes.get(name)
        if not code:
            checks.append({"source": SHORT.get(name, name), "status": "failed", "error": "DART 고유번호 못 찾음"})
            continue
        pending.append((name, code))
    if only:
        pending = [(n, c) for n, c in pending if n in only or SHORT.get(n, n) in only]
    for name, code in pending:
        short = SHORT.get(name, name)
        t0 = time.monotonic()
        try:
            st, api, rcept = api_roster(key, code, year, report, get=get, sleep=sleep)
            if st == "no_data":
                checks.append({"source": short, "status": "no_data", "note": f"{ec.REPORTS[report]['label']} 미제출"})
                continue
            if seen.get(name) == rcept and (rosters.get(name) or {}).get("rcept") == rcept:
                checks.append({"source": short, "status": "ok", "note": "이미 본 보고서", "rcept": rcept})
                continue
            if budget[0] < (1 if baseline else 2):
                checks.append({"source": short, "status": "waiting", "reason": "원문 내려받기 한도", "rcept": rcept})
                continue
            _, cur, changes, notes, how = doc_roster(key, rcept, api, get=get, sleep=sleep, budget=budget)
            if baseline:
                rosters[name] = {"period": f"{year}{report}", "rcept": rcept, "coverage": how, "people": pack(cur)}
                seen[name] = rcept
                checks.append({"source": short, "status": "ok", "rcept": rcept, "returned": len(cur), "coverage": how, "note": "기준선 — 명단만 저장"})
                continue
            bst, bapi, brcept = api_roster(key, code, base_year, base_report, get=get, sleep=sleep)
            cached = rosters.get(name) or {}
            rosters[name] = {"period": f"{year}{report}", "rcept": rcept, "coverage": how, "people": pack(cur)}
            keys[name] = {person_key(p) for p in cur}
            if bst == "no_data":
                checks.append({"source": short, "status": "ok", "rcept": rcept, "returned": len(cur), "coverage": how,
                               "note": f"앞 보고서({base_label}) 없음 — 비교 못 함"})
                seen[name] = rcept
                continue
            if cached.get("period") == f"{base_year}{base_report}" and cached.get("rcept") == brcept:
                base, bhow = unpack(cached["people"]), f"{cached.get('coverage', '')} · 지난 실행에 읽은 명단"
            else:
                _, base, _, _, bhow = doc_roster(key, brcept, bapi, get=get, sleep=sleep, budget=budget)
            evs, s = company_events(name, code, cur_label, base_label, season, cur, base, changes, notes,
                                    url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}",
                                    base_as_of=base_as_of, watch=watch, others=keys)
            for e in evs:
                e["id"] = f"exec:{code}:{year}{report}:{e['key']}"
                e.update({"team": TEAM.get(name), "period": cur_label, "base": base_label, "season": season, "rcept": rcept, "baseRcept": brcept,
                          "baseUrl": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={brcept}" if brcept else None})
                if e["id"] in old:
                    continue
                e["detectedAt"] = stamp
                fresh.append(e)
            seen[name] = rcept
            checks.append({"source": short, "status": "ok", "rcept": rcept, "baseRcept": brcept, "returned": len(cur), "coverage": how,
                           "baseCoverage": bhow, **({"note": "표 형식 변화 — 항목 안 만듦"} if s["suppressed"] else {}),
                           "new": s["new"], "gone": s["gone"], "changed": s["changed"], "full": s["full"]})
        except (ec.TransientError, RuntimeError) as e:
            checks.append({"source": short, "status": "failed", "error": str(e)[:100]})
        if PROGRESS:
            print(f"[kr-exec] {short} {checks[-1]['status']} {time.monotonic() - t0:.1f}s 원문 남은 {budget[0]}", file=sys.stderr, flush=True)
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    events = [e for e in list(old.values()) + fresh if str(e.get("detectedAt", "")) >= keep]
    events.sort(key=lambda e: (e.get("detectedAt", ""), {"A": 0, "B": 1, "C": 2}.get(e.get("tier"), 3)), reverse=True)
    ok = sum(1 for c in checks if c["status"] in ("ok", "no_data"))
    status = "complete" if ok == len(checks) else "failed" if not any(c["status"] in ("ok", "no_data") for c in checks) else "partial"
    filed = sum(1 for c in checks if c["status"] in ("ok", "waiting"))
    return {
        "schema": SCHEMA, "generatedAt": stamp, "status": status, "season": season, **({"baseline": True} if baseline else {}),
        "period": {"year": year, "report": report, "label": cur_label, "base": {"year": base_year, "report": base_report, "label": base_label},
                   "deadline": f"{year + 1 if report == '11011' else year}-{ec.REPORTS[report]['deadline']}"},
        "checks": checks, "events": events, "seen": seen,
        "rosters": rosters,
        "counts": {"companies": len(names), "filed": filed, "notFiled": sum(1 for c in checks if c["status"] == "no_data"),
                   "failed": sum(1 for c in checks if c["status"] == "failed"), "waiting": sum(1 for c in checks if c["status"] == "waiting"),
                   "newEvents": len(fresh), **{t: sum(1 for e in fresh if e["tier"] == t) for t in ("A", "B", "C")}},
        "unresolvedCompanies": missing,
        "watchCompanies": [w["name"] for w in watch],
        "rules": [
            "분기·반기·사업보고서 '임원 현황'을 바로 앞 보고서와 비교한다(3분기←반기←1분기←전년 사업보고서). '새로 보임'은 두 기준일 사이 변화일 뿐 선임일·사유가 아니다 — 회사 확인.",
            "같은 사람은 이름과 출생년월이 같을 때만. 한쪽 보고서에 미등기 임원이 없으면 등기임원끼리만 비교한다.",
            "오너 일가는 '최대주주와의 관계' 칸 글자(본인·친인척·특수관계인 등) 그대로다. 이름·성으로 추정하지 않는다.",
            "경쟁사·해외 경쟁사·전관·주의 회사 표시는 경력 칸 낱말이다. 같은 이름의 다른 회사·직책일 수 있어 원문 확인. 주의 회사 목록은 기자가 정한다(data/kr_exec_watch.json).",
            "3분기·반기(수시 인사 철)의 사장급 변동·경쟁사 출신 영입은 A, 1분기·사업보고서(정기 주총·연말 인사 철)는 B. 오너 일가·주의 회사·임기 중 빠짐은 늘 A.",
            "'보고서 제출일 현재 변동사항'은 기준일 뒤 제출일까지 회사가 적은 변동이다(가장 새 정보).",
            "미제출·조회 실패·원문 못 읽음은 0건이 아니라 미확인.",
        ],
    }


def annotate(doc):
    """격리 검증: 공개 로그라 이름은 첫 글자만, 출생년월·경력 원문은 줄여서."""
    def mask(s):
        s = str(s or "")
        return s[:1] + "*" * max(0, len(s) - 1)
    print(f"::notice title=kr-exec-summary::{doc['period']['label']} ← {doc['period']['base']['label']} · {json.dumps(doc['counts'], ensure_ascii=False)}"
          f" · 미해결 {doc['unresolvedCompanies']}")
    lines = [f"{c['source']}|{c['status']}|{c.get('coverage', c.get('note', c.get('error', c.get('reason', ''))))}|새{c.get('new', '-')} 빠짐{c.get('gone', '-')} 변경{c.get('changed', '-')}"
             for c in doc["checks"]]
    for i in range(0, len(lines), 8):
        print(f"::notice title=kr-exec-checks-{i // 8 + 1}::" + " ;; ".join(lines[i:i + 8]))
    shown = [e for e in doc["events"] if e["tier"] in ("A", "B")][:40]
    for i, e in enumerate(shown):
        p = e.get("person") or {}
        text = e["text"].replace(p.get("name") or "\0", mask(p.get("name"))) if p.get("name") else e["text"]
        print(f"::notice title=kr-exec-{e['tier']}-{i + 1}::{e['kind']} · {text[:260]} · 표시: {'; '.join(f['text'][:80] for f in e.get('flags') or [])}")


def main():
    global DOC_BUDGET
    ap = argparse.ArgumentParser(description="출입처 임원 명단 변화 감시")
    ap.add_argument("--year", type=int)
    ap.add_argument("--report", choices=sorted(AS_OF))
    ap.add_argument("--annotate-only", action="store_true", help="저장하지 않고 요약만(격리 검증)")
    ap.add_argument("--doc-budget", type=int, help="원문 내려받기 한도(기본 %d)" % DOC_BUDGET)
    ap.add_argument("--baseline", action="store_true", help="이번 기간 명단만 저장(항목 없음) — 다음 분기 비교용")
    ap.add_argument("--only", help="이 회사들만(쉼표, 검증용)")
    a = ap.parse_args()
    DOC_BUDGET = a.doc_budget or DOC_BUDGET
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        sys.exit("DART_API_KEY 없음 — 이전 결과 유지")
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = None
    if token and not a.annotate_only:
        try:
            previous = private_store.get("kr-exec", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-exec-state::이전 결과 조회 실패({e}) — 처음부터 비교")
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    try:
        import dart_watch
        table = dart_watch.load_corp_codes(key)
    except SystemExit:
        table = None
    only = {x.strip() for x in (a.only or "").split(",") if x.strip()} or None
    doc = run(key, year=a.year, report=a.report, previous=previous, registry=registry, table=table, baseline=a.baseline, only=only)
    if a.annotate_only:
        annotate(doc)
        return
    c = doc["counts"]
    print(f"::notice title=kr-exec::{doc['period']['label']} · 제출 {c['filed']}/{c['companies']} · 미제출 {c['notFiled']} · 실패 {c['failed']}"
          f" · 대기 {c['waiting']} · 새 항목 {c['newEvents']}(A {c['A']}·B {c['B']}·C {c['C']})")
    if not token:
        print("::warning title=kr-exec-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("임원 현황 조회 전체 실패 — 이전 결과 유지(0건 아님)")
    print(f"::notice title=kr-exec-push::기자 전용 저장소 전송 HTTP {private_store.put('kr-exec', doc, token)}")


if __name__ == "__main__":
    main()
