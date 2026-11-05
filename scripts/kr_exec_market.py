"""타사 임원 명단 속 출입처 출신·주의 회사 출신 + 출입처 수시 임원 공시 (OpenDART, 11-05 기자 요청).

선배 매의눈이 다른 회사 보고서에서 한 회사 전 대표의 이사 등재를 잡은 것처럼, 출입처 회사 출신(전 대표·고위 임원)이 다른 회사
이사·대표로 오르는 것을 잡는다(11-05 기자: "내 출입처 회사들"). 출입처 보고서 밖, 상장사 전체로 넓힌다.

1) 수시 공시(실행마다, 최근 3일 시장 전체 목록)
   - 독립이사의 선임ㆍ해임 또는 중도퇴임에 관한 신고(기타공시 E — 2026 상법 개정 전 이름 '사외이사의 …'): 신임·퇴임 이사의
     출생년월·주요경력·사유 표. 출입처 회사면 전부(중도퇴임 A), 다른 회사면 출입처 임원 출신·주의 회사 출신만.
   - 대표이사(대표집행임원) 변경(거래소공시 I): 변경 전·후, 사유, 신임 대표 주요경력·최대주주와의 관계.
   - 주주총회소집공고(출입처만): 이사 후보 표 — '부실기업 경영진 여부'·'체납사실 여부'·'법령상 결격 사유 유무'와 세부경력.
2) 상장사 등기임원 명단 순환 조회(실행마다 ROSTER_BUDGET곳, 임원 현황 API exctvSttus): 경력 칸에 출입처 임원 직함이나
   주의 회사가 나오는 등기임원. 회사마다 처음 본 명단은 기준선(앞 기간 보고서로 깔아 둠), 다음 보고서에 새로 보인 사람만 항목.

원칙
- 공개 공시다. 경력 칸 낱말 일치일 뿐 — 같은 이름의 다른 회사·직책일 수 있다. 같은 그룹 계열사 사이 이동은 뺀다(회사 이름 규칙 — 틀릴 수 있음).
- '부실기업 경영진 여부' 등은 회사가 적은 칸 그대로다. '없음' 아닌 글자가 있으면 A — 내용은 원문 확인.
- 조회 실패·미제출·한도로 못 본 회사는 0건이 아니라 미확인이다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import earnings_compare as ec  # noqa: E402
import governance_watch as gw  # noqa: E402
import kr_exec_watch as kx  # noqa: E402

SCHEMA = "kr_exec_market/v1"
KST = ec.KST
LOOKBACK_DAYS = int(os.environ.get("KR_EXEC_LOOKBACK") or 3)
# 출입처 소집공고 되짚기(11-05 기자 승인 — 이사 후보 점검을 실제 공시로 확인): 0이면 끔. 켜면 출입처마다 이 기간 기타공시 목록에서 소집공고를 읽는다.
# 지난 공고에서 나온 후보 항목은 기준선(오늘의 레이더엔 안 올림) — 이미 주총이 끝났을 수 있다.
AGM_DAYS = int(os.environ.get("KR_EXEC_AGM_DAYS") or 0)
PROGRESS = bool(os.environ.get("KR_EXEC_PROGRESS"))  # 공시별 읽은 사람 수(이름 없음)를 stderr로
LIST_PAGES = 30          # 목록 한 종류당 쪽(100건) 한도 — 넘으면 미확인 표시
DOC_BUDGET = 40          # 수시 공시 원문 한도(작은 문서 — 대표이사 변경 5KB, 독립이사 신고 10KB, 소집공고 수 MB)
ROSTER_BUDGET = 400      # 등기임원 명단 순환 조회 회사 수(11-05 탐침 174: 임원 현황 API 1회 1.2초 안팎, 상장사 4,013곳)
INDUSTRY_BUDGET = 60     # 업종(company.json) 조회 한도 — 표시 있는 회사만
KEEP_DAYS = 120
SEEN_DAYS = 30
NOT_FILED_RETRY_DAYS = 30
PAUSE = 0.3

DIRECTOR_FILING = re.compile(r"(독립|사외)이사의\s*선임.{0,4}해임\s*또는\s*중도퇴임")
CEO_FILING = re.compile(r"대표이사\s*(\(대표집행임원\))?\s*변경")
AGM_FILING = re.compile(r"주주총회\s*소집\s*공고")

# 경력 칸의 출입처 이름 → 보여 줄 출입처(옛 이름 포함). 그룹 회사일 뿐 출입처가 아닌 이름(현대중공업·SK에너지 등)은 넣지 않는다.
BEAT_ALIAS = {
    "현대자동차": "현대차", "현대차": "현대차", "기아자동차": "기아", "기아차": "기아", "기아": "기아", "현대모비스": "현대모비스",
    "현대위아": "현대위아", "현대제철": "현대제철", "현대하이스코": "현대제철", "HL만도": "HL만도", "만도": "HL만도",
    "KG모빌리티": "KG모빌리티", "쌍용자동차": "KG모빌리티", "쌍용차": "KG모빌리티", "한국타이어앤테크놀로지": "한국타이어", "한국타이어": "한국타이어",
    "넥센타이어": "넥센타이어", "금호타이어": "금호타이어", "포스코홀딩스": "포스코홀딩스", "포스코": "포스코", "POSCO": "포스코",
    "KG스틸": "KG스틸", "동부제철": "KG스틸", "세아홀딩스": "세아홀딩스", "세아제강": "세아제강", "동국제강": "동국제강", "동국씨엠": "동국씨엠",
    "유니온스틸": "동국씨엠", "고려아연": "고려아연", "영풍": "영풍", "HD현대일렉트릭": "HD현대일렉트릭", "현대일렉트릭": "HD현대일렉트릭",
    "LS일렉트릭": "LS일렉트릭", "LS ELECTRIC": "LS일렉트릭", "LS산전": "LS일렉트릭", "대한전선": "대한전선", "LS전선": "LS전선",
    "LS MnM": "LS MnM", "LS니꼬동제련": "LS MnM", "LS-Nikko": "LS MnM", "LS": "LS", "두산에너빌리티": "두산에너빌리티", "두산중공업": "두산에너빌리티",
    "GS": "GS", "GS칼텍스": "GS칼텍스", "LG칼텍스": "GS칼텍스", "한화솔루션": "한화솔루션", "한화케미칼": "한화솔루션", "한화큐셀": "한화솔루션",
    "OCI홀딩스": "OCI홀딩스", "OCI": "OCI", "동양제철화학": "OCI", "태광산업": "태광", "동성케미칼": "동성케미칼", "동성케미컬": "동성케미칼",
    "DL케미칼": "DL케미칼", "LG화학": "LG화학", "LG Chem": "LG화학", "롯데케미칼": "롯데케미칼", "호남석유화학": "롯데케미칼",
    "금호석유화학": "금호석유화학", "금호석화": "금호석유화학", "S-OIL": "S-OIL", "S-Oil": "S-OIL", "에쓰오일": "S-OIL", "에쓰-오일": "S-OIL",
    "SK이노베이션": "SK이노베이션", "HD현대오일뱅크": "HD현대오일뱅크", "현대오일뱅크": "HD현대오일뱅크",
    "한국GM": "한국GM", "한국지엠": "한국GM", "GM대우": "한국GM", "GM Korea": "한국GM", "르노코리아": "르노코리아", "르노삼성": "르노코리아",
    "메르세데스-벤츠 코리아": "벤츠코리아", "벤츠코리아": "벤츠코리아", "BMW코리아": "BMW코리아", "폭스바겐코리아": "폭스바겐코리아",
    "아우디코리아": "아우디코리아", "혼다코리아": "혼다코리아",
}
BEAT_GROUP = {"현대차": "현대차그룹", "기아": "현대차그룹", "현대모비스": "현대차그룹", "현대위아": "현대차그룹", "현대제철": "현대차그룹",
              "HL만도": "HL", "KG모빌리티": "KG", "KG스틸": "KG", "한국타이어": "한국앤컴퍼니", "넥센타이어": "넥센", "금호타이어": "금호타이어",
              "포스코홀딩스": "포스코", "포스코": "포스코", "세아홀딩스": "세아", "세아제강": "세아", "동국제강": "동국", "동국씨엠": "동국",
              "고려아연": "고려아연", "영풍": "영풍", "HD현대일렉트릭": "HD현대", "HD현대오일뱅크": "HD현대", "LS일렉트릭": "LS", "LS전선": "LS",
              "LS MnM": "LS", "LS": "LS", "대한전선": "대한전선", "두산에너빌리티": "두산", "GS": "GS", "GS칼텍스": "GS", "한화솔루션": "한화",
              "OCI홀딩스": "OCI", "OCI": "OCI", "태광": "태광", "동성케미칼": "동성", "DL케미칼": "DL", "LG화학": "LG", "롯데케미칼": "롯데",
              "금호석유화학": "금호석유화학", "S-OIL": "S-OIL", "SK이노베이션": "SK", "한국GM": "한국GM", "르노코리아": "르노코리아",
              "벤츠코리아": "벤츠코리아", "BMW코리아": "BMW코리아", "폭스바겐코리아": "폭스바겐코리아", "아우디코리아": "아우디코리아", "혼다코리아": "혼다코리아"}
BEAT_AREA = {"현대차": "자동차", "기아": "자동차", "현대모비스": "자동차", "현대위아": "자동차", "HL만도": "자동차", "KG모빌리티": "자동차",
             "한국타이어": "자동차", "넥센타이어": "자동차", "금호타이어": "자동차", "한국GM": "자동차", "르노코리아": "자동차", "벤츠코리아": "자동차",
             "BMW코리아": "자동차", "폭스바겐코리아": "자동차", "아우디코리아": "자동차", "혼다코리아": "자동차",
             "포스코홀딩스": "철강·비철", "포스코": "철강·비철", "현대제철": "철강·비철", "KG스틸": "철강·비철", "세아홀딩스": "철강·비철",
             "세아제강": "철강·비철", "동국제강": "철강·비철", "동국씨엠": "철강·비철", "고려아연": "철강·비철", "영풍": "철강·비철", "LS MnM": "철강·비철",
             "HD현대일렉트릭": "전력", "LS일렉트릭": "전력", "대한전선": "전력", "LS전선": "전력", "LS": "전력", "두산에너빌리티": "전력",
             "GS": "화학·정유", "GS칼텍스": "화학·정유", "한화솔루션": "화학·정유", "OCI홀딩스": "화학·정유", "OCI": "화학·정유", "태광": "화학·정유",
             "동성케미칼": "화학·정유", "DL케미칼": "화학·정유", "LG화학": "화학·정유", "롯데케미칼": "화학·정유", "금호석유화학": "화학·정유",
             "S-OIL": "화학·정유", "SK이노베이션": "화학·정유", "HD현대오일뱅크": "화학·정유"}
# 표준산업분류(company.json induty_code) 앞자리 → 업종 구역
AREA_KSIC = {"자동차": ("30", "2211"), "철강·비철": ("24",), "전력": ("28",), "화학·정유": ("19", "20", "222")}
# 같은 그룹 계열사(대상 회사 이름 규칙) — 그룹 안 이동은 기사 가치가 낮아 뺀다
GROUP_NAMES = {
    "현대차그룹": ("현대자동차", "기아", "현대모비스", "현대위아", "현대제철", "현대글로비스", "현대로템", "현대오토에버", "현대건설", "현대비앤지스틸",
               "현대차증권", "이노션", "현대트랜시스", "현대케피코", "현대엔지니어링"),
    "포스코": ("포스코", "POSCO"), "LS": ("LS", "엘에스", "가온전선", "예스코"), "GS": ("GS", "지에스"), "OCI": ("OCI", "오씨아이"),
    "세아": ("세아",), "동국": ("동국제강", "동국씨엠", "동국홀딩스", "인터지스"), "KG": ("KG", "케이지"), "HD현대": ("HD현대", "HD한국조선해양", "현대오일뱅크", "현대일렉트릭", "현대중공업", "현대건설기계", "현대미포"),
    "한국앤컴퍼니": ("한국앤컴퍼니", "한국타이어"), "넥센": ("넥센",), "금호타이어": ("금호타이어",), "HL": ("HL", "에이치엘"),
    "고려아연": ("고려아연", "케이젯정밀"), "영풍": ("영풍", "시그네틱스", "코리아써키트", "인터플렉스"), "대한전선": ("대한전선",),
    "두산": ("두산",), "한화": ("한화",), "태광": ("태광산업", "대한화섬", "흥국"), "동성": ("동성케미칼", "동성코퍼레이션", "동성화인텍"),
    "DL": ("DL", "디엘"), "LG": ("LG", "엘지"), "롯데": ("롯데",), "금호석유화학": ("금호석유화학", "금호미쓰이"), "S-OIL": ("S-Oil", "에쓰오일"),
    "SK": ("SK", "에스케이"),
}
TITLE = re.compile(r"회장|부회장|사장|부사장|전무|상무보|상무|대표|CEO|CFO|CTO|COO|CSO|CHRO|본부장|사업부장|연구소장|연구원장|센터장|법인장|"
                   r"사외이사|독립이사|기타비상무이사|사내이사|이사(?!회|장)")
SENIOR = re.compile(r"회장|사장|전무|대표|CEO|CFO|CTO|COO|CSO|사내이사")
SEG = re.compile(r"[/ㆍ·•\n;|]|\s-\s|-(?=\s*[前現])|(?<=\S)\s*-(?=\s*\d)|(?<!~)(?<!~ )(?=\(?['’]\d{2}[.~)])|(?<![\d~])(?<!~ )(?=\d{4}\s*[.~년)])|(?=[前現]\s*\S)|(?=[전현]\s*\))|(?=\s[전현]\))")
NONE = re.compile(r"^\s*(-|–|없음|없\s*음|해당\s*사항\s*없음|해당\s*없음|해당사항없음|N/?A|無|×|x|X|미해당|0)?\s*\.?\s*$")
# 11-05 실제(고려아연 2026-08-11 소집공고): 결격 칸에 「결격사유 없음」 — 칸 이름 낱말 + '없음'도 없음이다. '있음'·내용이 적힌 칸만 남긴다.
NONE_WORDS = re.compile(r"(?:결격\s*사유|결격|체납\s*사실|체납|부실\s*기업\s*경영진|부실기업|해당\s*사항|해당\s*사실|해당|사실|사유)?\s*"
                        r"(?:없음|없습니다|없다|無|아님|아니오|아니요|미해당|해당\s*없음|해당\s*사항\s*없음)\s*\.?")


def none_value(v):
    t = str(v or "").strip()
    return bool(NONE.match(t) or re.fullmatch(NONE_WORDS, t))


def refresh_agm_flags(e):
    """저장된 이사 후보 항목의 결격·부실 칸 표시를 지금 규칙으로 다시(값이 '결격사유 없음' 같은 줄은 뺀다). 등급도 다시."""
    if e.get("kind") != "이사 후보":
        return False
    keep = [f for f in e.get("flags") or [] if not (f.get("kind") == "결격·부실 칸" and none_value((re.search(r"「(.*)」", f.get("text") or "") or [None, ""])[1]))]
    if len(keep) == len(e.get("flags") or []):
        return False
    kinds = {f["kind"] for f in keep}
    e["flags"], e["tier"] = keep, "A" if kinds & {"결격·부실 칸", "주의 회사 출신"} else "B" if kinds else "C"
    return True


# ---------- career rules ----------

def segments(text):
    return [s.strip() for s in SEG.split(str(text or "")) if s and s.strip()]


def beat_origin(career):
    """경력 칸에서 출입처 이름 + 임원 직함(30자 안)이 같은 마디에 있는 것. [{beat, alias, text, senior}]"""
    out, seen = [], set()
    aliases = sorted(BEAT_ALIAS, key=len, reverse=True)
    for seg in segments(career):
        taken = []
        for a in aliases:
            span = kx.mentions(seg, a)
            if not span or any(s <= span[0] < e for s, e in taken):
                continue
            taken.append(span)
            window = seg[span[1]:span[1] + 30]
            # 다음 회사 이름(㈜·주식회사·다른 출입처) 앞에서 끊는다 — '포스코 구매센터장, 포스메이트 대표이사'의 '대표'는 포스코 직함이 아니다
            cut = re.search(r"[,，]\s*\S+(㈜|\(주\)|주식회사)|[,，]\s*(前|現|전\)|현\))", window)
            window = window[:cut.start()] if cut else window
            title = TITLE.search(window)
            # '현대자동차 협력사 대표'·'포스코 납품업체 사장'은 그 회사 출신이 아니다
            if not title or re.search(r"협력|납품|대리점|거래처|고객사|지정|1차|2차|벤더", window[:title.start()]):
                continue
            beat = BEAT_ALIAS[a]
            if (beat, seg) in seen:
                continue
            seen.add((beat, seg))
            # 고위 여부는 그 회사 바로 뒤 첫 직함만 본다
            paren = re.match(r"\s*\(([^)]{0,12})\)", window[title.end():])      # '구매본부장(전무)'
            first = title.group(0) + (" " + paren.group(1) if paren else "")
            out.append({"beat": beat, "alias": a, "text": seg[:120],
                        "senior": bool(SENIOR.search(first)) and not re.search(r"사외이사|독립이사|비상무", first)})
    return out


def same_group(target, beat):
    t = re.sub(r"^\s*(주식회사|㈜|\(주\))\s*", "", str(target or ""))
    return any(t.startswith(n) for n in GROUP_NAMES.get(BEAT_GROUP.get(beat, ""), ()))


def area_of(code):
    c = str(code or "")
    return next((a for a, pre in AREA_KSIC.items() if c.startswith(pre)), None)


def watch_hits(career, watch):
    return [{"kind": "주의 회사 출신", "text": f"경력에 '{a}' — {w['reason']}".strip(" —")}
            for w in watch for a in w["aliases"][:1] if any(kx.mentions(career, x) for x in w["aliases"])]


def person_flags(target, career, watch, *, industry=None):
    """(표시들, 출입처 출신 목록). 같은 그룹 계열사 출신은 뺀다."""
    origins = [o for o in beat_origin(career) if not same_group(target, o["beat"])]
    flags = watch_hits(career, watch)
    if origins:
        same = area_of(industry) and any(BEAT_AREA.get(o["beat"]) == area_of(industry) for o in origins)
        flags.append({"kind": "출입처 출신", "beats": sorted({o["beat"] for o in origins}),
                      "text": "경력 「" + " / ".join(o["text"] for o in origins[:3]) + "」" + (" · 같은 업종 회사" if same else "")})
    gov = sorted({m.group(0) for m in kx.GOV.finditer(str(career or ""))})
    if gov and (origins or flags):
        flags.append({"kind": "전관", "text": "경력에 " + "·".join(f"'{g}'" for g in gov[:3])})
    return flags, origins


# ---------- filing parsers ----------

def _rows(part):
    return [r for r in ([kx.clean(c[1]) for c in kx.CELL.findall(tr)] for tr in kx.ROW.findall(part)) if any(r)]


def _ix(head, pats):
    return {k: next((i for i, h in enumerate(head) if re.search(p, h)), None) for k, p in pats.items()}


def parse_director_filing(text):
    """독립(사외)이사 선임·해임·중도퇴임 신고 → {date, appointed[], left[]}"""
    out = {"date": None, "appointed": [], "left": []}
    flat = kx.clean(text)
    m = re.search(r"변경\s*발생일\s*:?\s*(\d{4})\s*[.년-]\s*(\d{1,2})\s*[.월-]\s*(\d{1,2})", flat)
    out["date"] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    mode = None
    for part in kx.TABLE_SPLIT.split(text):
        if part[:6].upper() != "<TABLE":
            t = kx.clean(part)
            for mm in re.finditer(r"【([^】]*)】", t):
                mode = "left" if re.search(r"해임|중도\s*퇴임", mm.group(1)) else "appointed" if re.search(r"선임", mm.group(1)) else mode
            continue
        rows = _rows(part)
        if not rows:
            continue
        hi = next((i for i, r in enumerate(rows[:3]) if any(re.search(r"성\s*명", c) for c in r)), None)
        if hi is None:
            continue
        head = rows[hi]
        if any(re.search(r"정정|항\s*목", c) for c in head):
            continue
        ix = _ix(head, {"name": r"성\s*명", "birth": r"출생|생년", "sex": r"성\s*별", "kind": r"선임\s*구분|구\s*분", "start": r"임기\s*시작|시작일",
                        "term": r"^임\s*기$|임기\s*\(|임기$", "career": r"경력", "reason": r"사\s*유", "end": r"만료|종료|퇴임일|해임일"})
        kind = "left" if ix["reason"] is not None and mode != "appointed" else mode or ("appointed" if ix["career"] is not None else "left")
        for r in rows[hi + 1:]:
            def at(k):
                i = ix.get(k)
                return r[i] if i is not None and i < len(r) else ""
            name = at("name")
            if not name or name in ("-", "해당사항 없음", "해당없음") or re.search(r"성\s*명", name):
                continue
            out[kind].append({k: at(k)[:400 if k == "career" else 60] for k in ix if ix[k] is not None})
    return out


def parse_ceo_change(text):
    """대표이사 변경 → {before, after, reason, date, people[{name, rel, career}]}
    두 양식(11-05 탐침 176c): ① '변경 전ㆍ후' 칸 + 성명·최대주주 관계·주요경력 표, ② '변경전 대표이사'·'변경후 대표이사' 칸 + 성명·생년월일·
    최대주주 관계 표 + 성명·회사명·직위·입사일 경력 표."""
    out = {"before": "", "after": "", "reason": "", "date": "", "people": []}
    people = {}
    for part in kx.TABLE_SPLIT.split(text):
        if part[:6].upper() != "<TABLE":
            continue
        rows = _rows(part)
        for r in rows:
            for i, c in enumerate(r[:-1]):
                cc = c.replace(" ", "")
                if re.fullmatch(r"변경전(대표이사)?(\(대표집행임원\))?", cc) and not out["before"]:
                    out["before"] = r[i + 1][:80]
                if re.fullmatch(r"변경후(대표이사)?(\(대표집행임원\))?", cc) and not out["after"]:
                    out["after"] = r[i + 1][:80]
            j = " ".join(r[:1])
            if re.search(r"변경\s*사유", j) and len(r) >= 2:
                out["reason"] = out["reason"] or r[-1][:200]
            if re.search(r"변경\s*일(자)?\s*$", j) and len(r) >= 2:
                out["date"] = out["date"] or r[-1][:20]
        hi = next((i for i, r in enumerate(rows[:2]) if any(re.fullmatch(r"성\s*명", c) for c in r)), None)
        if hi is None:
            continue
        head = rows[hi]
        ix = _ix(head, {"name": r"성\s*명", "rel": r"최대\s*주주", "career": r"경력", "corp": r"회사명|상\s*호", "title": r"^직\s*위$", "since": r"입사|취임|시작"})
        if ix["rel"] is None and ix["career"] is None and ix["corp"] is None:
            continue
        for r in rows[hi + 1:]:
            def at(k):
                i = ix.get(k)
                return r[i] if i is not None and i < len(r) else ""
            name = at("name")
            if not name or re.search(r"성\s*명", name):
                continue
            p = people.setdefault(kx.name_key(name), {"name": name, "rel": "", "career": ""})
            if at("rel"):
                p["rel"] = p["rel"] or at("rel")[:60]
            bit = at("career") or " ".join(x for x in (at("corp"), at("title"), at("since") and f"({at('since')}~)") if x and x != "-")
            if bit:
                p["career"] = (p["career"] + " / " + bit).strip(" /")[:400]
    out["people"] = list(people.values())
    return out


AGENDA = re.compile(r"^\s*(제?\s*\d+(-\d+)*\s*호|\d+(-\d+)+)")
PERIOD = re.compile(r"\d{4}|~|현재|^기간$|^내용$")


def parse_agm_candidates(text):
    """주주총회 소집공고 이사 후보 → [{name, birth, kind, rel, rec, job, career, tax, insolvent, disq}]
    11-05 탐침 174: 후보 표는 위 줄과 합친 칸(rowspan)이 있고, 경력 표는 '기간·내용' 두 칸이 이어지는 줄로 나온다."""
    cands, order = {}, []

    def slot(name):
        k = kx.name_key(name)
        hit = next((x for x in order if x == k), None) or next((x for x in order if x[:3] == k[:3]), None)
        if not hit:
            hit = k
            order.append(k)
            cands[k] = {"name": name}
        return cands[hit]

    for part in kx.TABLE_SPLIT.split(text):
        if part[:6].upper() != "<TABLE":
            continue
        rows = _rows(part)
        hi = next((i for i, r in enumerate(rows[:2]) if any(re.search(r"후보자\s*성명", c) for c in r)), None)
        if hi is None:
            continue
        head = rows[hi]
        hj = " ".join(head)
        ix = _ix(head, {"name": r"후보자\s*성명", "birth": r"생년|출생", "kind": r"사외이사\s*후보자\s*여부|후보자\s*여부", "rel": r"최대\s*주주",
                        "rec": r"추\s*천", "job": r"주된\s*직업", "tax": r"체납", "insolvent": r"부실\s*기업", "disq": r"결격"})
        ni = ix["name"]
        if ni is None:
            continue
        if re.search(r"세부\s*경력|주된\s*직업", hj):
            cur = None
            for r in rows[hi + 1:]:
                if not r or set(r) <= {"기간", "내용"}:
                    continue
                if len(r) >= len(head) and not PERIOD.search(r[ni]):
                    cur = slot(r[ni])
                    cur["job"] = (r[ix["job"]] if ix["job"] is not None and ix["job"] < len(r) else "")[:120]
                    rest = r[(ix["job"] if ix["job"] is not None else ni) + 1:]
                    cur["career"] = " ".join(rest)[:600]
                elif cur is not None:
                    cur["career"] = (cur.get("career", "") + " / " + " ".join(r)).strip(" /")[:600]
            continue
        prev = None
        for r in rows[hi + 1:]:
            if re.search(r"총\s*\(\s*\d+\s*\)\s*명", " ".join(r)):
                continue
            if prev is not None and 0 < len(r) < len(head):
                if ni > 0 and not AGENDA.match(r[0]):
                    r = [prev[0]] + r                      # 의안 칸이 위 줄과 합쳐짐
                r = r + prev[len(r):]                      # 뒤 칸(후보 구분·관계·추천인)이 위 줄과 합쳐짐
            prev = r
            name = r[ni] if ni < len(r) else ""
            if not name or re.search(r"후보자|성명", name):
                continue
            c = slot(name)
            for f in ("birth", "kind", "rel", "rec", "tax", "insolvent", "disq"):
                i = ix.get(f)
                if i is not None and i < len(r) and r[i]:
                    c[f] = r[i][:80]
    return [cands[k] for k in order]


# ---------- DART calls ----------

def dart(key, endpoint, params, *, get, sleep):
    st, body = ec.call(endpoint, params, get=lambda u, params, **kw: get(u, params={"crtfc_key": key, **params}, **kw), sleep=sleep)
    sleep(PAUSE)
    return st, body


def list_filings(key, ty, start, end, *, get, sleep):
    """(행, 상태 설명). 쪽 한도를 넘으면 partial."""
    rows, note = [], None
    for page in range(1, LIST_PAGES + 1):
        st, body = dart(key, "list.json", {"bgn_de": start, "end_de": end, "pblntf_ty": ty, "page_no": page, "page_count": 100}, get=get, sleep=sleep)
        if st != "ok":
            break
        rows += body.get("list") or []
        total = int(body.get("total_page") or 1)
        if page >= total:
            break
        if page == LIST_PAGES:
            note = f"{total}쪽 중 {LIST_PAGES}쪽만"
    return rows, note


def industry(key, code, cache, budget, *, get, sleep):
    if code in cache:
        return cache[code]
    if budget[0] <= 0:
        return None
    budget[0] -= 1
    try:
        st, body = dart(key, "company.json", {"corp_code": code}, get=get, sleep=sleep)
    except (ec.TransientError, RuntimeError):
        return None
    cache[code] = (body or {}).get("induty_code") if st == "ok" else ""
    return cache[code]


# ---------- run ----------

def _ev(kind, tier, company, text, url, *, person=None, flags=(), source, key, beat=None, extra=None):
    return {"kind": kind, "tier": tier, "company": company, "text": text, "url": url, "person": person or {}, "flags": list(flags),
            "source": source, "key": key, **({"beat": beat} if beat else {}), **(extra or {})}


def filings_part(key, now, beat_codes, watch, state, *, get, sleep, doc_budget, ind_budget):
    start = (now - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d")
    end = now.strftime("%Y%m%d")
    seen = state.setdefault("seen", {})
    ind = state.setdefault("industry", {})
    checks, events = [], []
    rows = []
    for ty, label in (("E", "기타공시(독립이사 신고·소집공고)"), ("I", "거래소공시(대표이사 변경)")):
        try:
            got, note = list_filings(key, ty, start, end, get=get, sleep=sleep)
            rows += got
            checks.append({"source": f"공시 목록 {label}", "status": "partial" if note else "ok", "returned": len(got), **({"error": note} if note else {})})
        except (ec.TransientError, RuntimeError) as e:
            checks.append({"source": f"공시 목록 {label}", "status": "failed", "error": str(e)[:80]})
    beat_by_code = {c: n for n, c in beat_codes.items()}
    if AGM_DAYS > LOOKBACK_DAYS:
        have, back, failed_back = {x.get("rcept_no") for x in rows}, 0, 0
        bstart = (now - dt.timedelta(days=AGM_DAYS)).strftime("%Y%m%d")
        for n_, code_ in beat_codes.items():
            try:
                st_, body_ = dart(key, "list.json", {"corp_code": code_, "bgn_de": bstart, "end_de": end, "pblntf_ty": "E", "page_count": 100},
                                  get=get, sleep=sleep)
            except (ec.TransientError, RuntimeError):
                failed_back += 1
                continue
            for x in (body_ or {}).get("list") or [] if st_ == "ok" else []:
                if AGM_FILING.search(x.get("report_nm") or "") and x.get("rcept_no") not in have:
                    x["_backfill"] = (x.get("rcept_dt") or "") < start
                    rows.append(x)
                    have.add(x.get("rcept_no"))
                    back += 1
        checks.append({"source": f"출입처 소집공고 되짚기({AGM_DAYS}일)", "status": "partial" if failed_back else "ok", "returned": back,
                       **({"error": f"목록 실패 {failed_back}곳"} if failed_back else {})})
    picked = []
    for x in rows:
        rc, nm, code = x.get("rcept_no"), x.get("report_nm") or "", x.get("corp_code")
        if not rc or rc in seen:
            continue
        beat = beat_by_code.get(code)
        if DIRECTOR_FILING.search(nm):
            picked.append(("director", x, beat))
        elif CEO_FILING.search(nm):
            picked.append(("ceo", x, beat))
        elif AGM_FILING.search(nm) and beat:
            picked.append(("agm", x, beat))
    opened = failed = waiting = 0
    for kind, x, beat in picked:
        rc, corp, code = x["rcept_no"], x.get("corp_name") or "", x.get("corp_code")
        if doc_budget[0] <= 0:
            waiting += 1
            continue
        doc_budget[0] -= 1
        texts, err = kx.fetch_document(key, rc, get=get, sleep=sleep, want=None)
        sleep(PAUSE)
        if not texts:
            failed += 1
            continue
        opened += 1
        seen[rc] = now.date().isoformat()
        text = max(texts, key=len)
        url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rc}"
        short = kx.SHORT.get(beat, beat) if beat else corp
        filed = f"{x.get('rcept_dt', '')[:4]}-{x.get('rcept_dt', '')[4:6]}-{x.get('rcept_dt', '')[6:8]}"
        if kind == "director":
            d = parse_director_filing(text)
            if PROGRESS:
                print(f"[kr-exec-market] 독립이사 신고 {corp} 선임 {len(d['appointed'])} 퇴임 {len(d['left'])} 변경일 {d['date']}"
                      f" 경력칸 {sum(1 for p in d['appointed'] if p.get('career'))}", file=sys.stderr, flush=True)
            for side, verb in (("appointed", "선임"), ("left", "해임·중도퇴임")):
                for p in d[side]:
                    career = p.get("career", "")
                    ic = None if beat else industry(key, code, ind, ind_budget, get=get, sleep=sleep)
                    flags, origins = person_flags(corp, career, watch, industry=ic)
                    if beat:
                        flags = [f for f in [kx.owner_flag(p)] if f] + kx.career_flags(beat, career, watch)
                    kinds = {f["kind"] for f in flags}
                    if not beat and not flags:
                        continue
                    # 11-05 기자: 출입처 회사 출신(전 대표·고위 임원)이 다른 회사 이사로 오르는 것이 목적 — 고위 출신 A, 그 밖 임원 출신 B
                    if "주의 회사 출신" in kinds or any(o["senior"] for o in origins) \
                            or (beat and side == "left" and re.search(r"중도|사임|해임|사퇴", p.get("reason", "") + p.get("kind", "") + verb)):
                        tier = "A"
                    elif beat or origins:
                        tier = "B"
                    else:
                        tier = "C"
                    who = f"{p.get('name', '')}{' ' + kx.birth_key(p.get('birth'))[:4] + '년생' if kx.birth_key(p.get('birth')) else ''}"
                    events.append(_ev(f"독립이사 {verb}", tier, short,
                                      f"{short} 독립이사 {verb} 신고({filed} 접수{', 변경일 ' + d['date'] if d['date'] else ''}) — {who}"
                                      f"{' · ' + p.get('kind') if p.get('kind') else ''}{' · 사유 「' + p['reason'] + '」' if p.get('reason') else ''}"
                                      f"{' · 경력 「' + career[:160] + '」' if career else ''}",
                                      url, person={"name": p.get("name"), "birth": p.get("birth"), "career": career[:300]}, flags=flags,
                                      source="독립이사 신고", key=f"{rc}|{side}|{kx.name_key(p.get('name'))}", beat=(origins[0]["beat"] if origins else None)))
        elif kind == "ceo":
            c = parse_ceo_change(text)
            if PROGRESS:
                print(f"[kr-exec-market] 대표이사 변경 {corp} 전 {bool(c['before'])} 후 {bool(c['after'])} 사유 {bool(c['reason'])} 경력표 {len(c['people'])}",
                      file=sys.stderr, flush=True)
            people = c["people"] or [{"name": c["after"], "career": "", "rel": ""}]
            for p in people:
                career = p.get("career", "")
                if beat:
                    flags = [f for f in [kx.owner_flag(p)] if f] + kx.career_flags(beat, career, watch)
                    origins = []
                else:
                    ic = industry(key, code, ind, ind_budget, get=get, sleep=sleep)
                    flags, origins = person_flags(corp, career, watch, industry=ic)
                    if not flags:
                        continue
                kinds = {f["kind"] for f in flags}
                tier = "A" if "주의 회사 출신" in kinds or any(o["senior"] for o in origins) else "B" if beat or origins else "C"
                events.append(_ev("대표이사 변경", tier, short,
                                  f"{short} 대표이사 변경 공시({filed}) — 변경 전 「{c['before'] or '?'}」 → 변경 후 「{c['after'] or '?'}」"
                                  f"{' · 사유 「' + c['reason'][:120] + '」' if c['reason'] else ''}{' · 변경일 ' + c['date'] if c['date'] else ''}"
                                  f"{' · ' + p.get('name', '') + ' 경력 「' + career[:160] + '」' if career else ''}",
                                  url, person={"name": p.get("name"), "career": career[:300], "rel": p.get("rel")}, flags=flags,
                                  source="대표이사 변경", key=f"{rc}|{kx.name_key(p.get('name'))}", beat=(origins[0]["beat"] if origins else None)))
        elif kind == "agm":
            if PROGRESS:
                cs = parse_agm_candidates(text)
                print(f"[kr-exec-market] 소집공고 {corp} 후보 {len(cs)} 경력 {sum(1 for p in cs if p.get('career'))} 부실칸 {sum(1 for p in cs if p.get('insolvent'))}",
                      file=sys.stderr, flush=True)
            for p in parse_agm_candidates(text):
                bad = [(lab, p.get(f)) for f, lab in (("insolvent", "부실기업 경영진 여부"), ("tax", "체납사실 여부"), ("disq", "법령상 결격 사유"))
                       if p.get(f) and not none_value(p.get(f))]
                flags = [{"kind": "결격·부실 칸", "text": f"{lab} 칸 「{v}」(회사 기재 그대로)"} for lab, v in bad]
                flags += [f for f in [kx.owner_flag(p)] if f] + kx.career_flags(beat, p.get("career", "") + " " + p.get("job", ""), watch)
                kinds = {f["kind"] for f in flags}
                tier = "A" if kinds & {"결격·부실 칸", "주의 회사 출신"} else "B" if kinds else "C"
                events.append(_ev("이사 후보", tier, short,
                                  f"{short} 주총 소집공고({filed}) 이사 후보 — {p.get('name')} {kx.birth_key(p.get('birth'))[:4] + '년생 ' if kx.birth_key(p.get('birth')) else ''}"
                                  f"{p.get('kind', '')} · 주된 직업 「{p.get('job', '')[:60]}」 · 추천 {p.get('rec', '-')}"
                                  f"{' · 경력 「' + p.get('career', '')[:160] + '」' if p.get('career') else ''}",
                                  url, person={"name": p.get("name"), "birth": p.get("birth"), "career": p.get("career", "")[:600], "rel": p.get("rel"),
                                               "kind": (p.get("kind") or "")[:20], "job": (p.get("job") or "")[:80]},   # 문제 임원 점검이 후보 경력으로 다시 본다
                                  flags=flags, source="주총 소집공고", key=f"{rc}|{kx.name_key(p.get('name'))}",
                                  extra={"filed": filed, **({"baseline": True} if x.get("_backfill") else {})}))
    checks.append({"source": "수시 임원 공시 원문", "status": "ok" if not failed else "partial", "returned": opened,
                   **({"error": f"원문 못 읽음 {failed}건"} if failed else {}), **({"pending": waiting} if waiting else {})})
    cut = (now - dt.timedelta(days=SEEN_DAYS)).date().isoformat()
    state["seen"] = {k: v for k, v in seen.items() if v >= cut}
    return checks, events, {"listed": len(rows), "picked": len(picked), "opened": opened}


def roster_part(key, now, universe, watch, state, *, get, sleep, budget, ind_budget):
    """상장사 등기임원 명단 순환 조회 — 처음 본 회사는 앞 기간 보고서로 기준선, 그다음부터 새로 보인 표시 있는 사람만 항목."""
    comps = state.setdefault("companies", {})
    ind = state.setdefault("industry", {})
    year, report = ec.target_period(now)
    dy, base_report = kx.BASE[report]
    order = sorted(universe)
    cursor = int(state.get("cursor") or 0) % max(len(order), 1)
    today = now.date().isoformat()
    events, done, failed = [], 0, 0
    i = cursor
    for _ in range(len(order)):
        if done >= budget:
            break
        code = order[i]
        i = (i + 1) % len(order)
        name = universe[code]
        rec = comps.get(code)
        if rec and rec.get("nd") and rec["nd"] > (now - dt.timedelta(days=NOT_FILED_RETRY_DAYS)).date().isoformat():
            continue
        done += 1
        try:
            first = rec is None or not rec.get("p")
            y, r = (year + dy, base_report) if first else (year, report)
            st, body = dart(key, "exctvSttus.json", {"corp_code": code, "bsns_year": str(y), "reprt_code": r}, get=get, sleep=sleep)
            if st != "ok" and not first:
                comps[code] = {**rec, "t": today}
                continue
            if st != "ok":
                st, body = dart(key, "exctvSttus.json", {"corp_code": code, "bsns_year": str(year), "reprt_code": report}, get=get, sleep=sleep)
                y, r = year, report
                if st != "ok":
                    comps[code] = {"nd": today}
                    continue
        except (ec.TransientError, RuntimeError):
            failed += 1
            continue
        people = [p for p in kx.api_people(body) if p["reg"] != "미등기"]
        rcept = kx.latest_rcept(body)
        flagged = {}
        for p in people:
            hits, origins = person_flags(name, p["career"], watch)
            if hits:
                flagged[kx.person_key(p)] = (p, hits, origins)
        period = f"{y}{r}"
        if rec and rec.get("p") and (rec.get("r") != rcept):
            old = set(rec.get("k") or [])
            for k, (p, hits, origins) in flagged.items():
                if k in old:
                    continue
                ic = industry(key, code, ind, ind_budget, get=get, sleep=sleep)
                hits, origins = person_flags(name, p["career"], watch, industry=ic)
                if not hits:
                    continue
                kinds = {f["kind"] for f in hits}
                same = any("같은 업종" in f["text"] for f in hits)
                top = bool(re.search(r"대표", p["ofcps"] + p["job"]))
                senior = any(o["senior"] for o in origins)
                tier = "A" if "주의 회사 출신" in kinds or senior else "B" if origins else "C"
                beats = sorted({o["beat"] for o in origins})
                events.append(_ev("타사 등기임원", tier, name,
                                  f"{name} {kx.period_label(y, r)} 등기임원 명단에 새로 보임 — {p['name']}"
                                  f"{' ' + kx.birth_key(p['birth'])[:4] + '년생' if kx.birth_key(p['birth']) else ''} {kx.norm_ofcps(p['ofcps'])}({p['reg']})"
                                  f"{' · 출입처 ' + '·'.join(beats) + ' 출신' if beats else ''} · 경력 「{p['career'][:160]}」"
                                  f"{' · 업종코드 ' + ic if ic else ''} · 앞 조사({kx.period_label(*divmod_period(rec['p']))})에는 없음",
                                  f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}",
                                  person={k2: p.get(k2) for k2 in ("name", "birth", "ofcps", "reg", "career")}, flags=hits,
                                  source="임원 현황", key=f"{code}|{period}|{k}", beat=beats[0] if beats else None))
        # 등기임원 전원 키(해시 8자리) — 문제 임원 점검이 '같은 사람이 다른 상장사 등기임원에도 있나'(시행령 34조⑤3호 겸직)를 본다
        dk = sorted({hashlib.sha256(kx.person_key(p).encode()).hexdigest()[:8] for p in people})
        comps[code] = {"r": rcept, "p": period, "k": sorted(flagged), "t": today, "n": name[:20], "dk": dk}
        # 출입처 출신 타사 등기임원 현황(기준선 포함 — 지금 어디 이사로 가 있나)
        alumni = state.setdefault("alumni", {})
        rows_ = [{"company": name, "name": re.sub(r"\s+", " ", p["name"]).strip(), "birth": kx.birth_key(p["birth"])[:4], "ofcps": kx.norm_ofcps(p["ofcps"]), "reg": p["reg"],
                  "beats": sorted({o["beat"] for o in origins}), "senior": any(o["senior"] for o in origins),
                  "text": " / ".join(o["text"] for o in origins[:2])[:160], "period": period, "rcept": rcept}
                 for p, hits, origins in flagged.values() if origins]
        if rows_:
            alumni[code] = rows_
        else:
            alumni.pop(code, None)
    state["cursor"] = i
    covered = sum(1 for c in comps.values() if c.get("p"))
    check = {"source": "상장사 등기임원 명단 순환", "status": "ok" if not failed else "partial", "returned": done,
             **({"error": f"조회 실패 {failed}곳(다음 순환에서 다시)"} if failed else {}), "covered": covered, "universe": len(order)}
    return [check], events


def divmod_period(p):
    p = str(p or "")
    return (int(p[:4]), p[4:]) if len(p) == 9 and p[4:] in kx.AS_OF else (0, "11011")


def run(key, *, now=None, previous=None, get=None, sleep=time.sleep, registry=None, table=None, watch=None, roster_budget=None, skip_roster=False):
    if get is None:
        import requests
        get = requests.get
    now = now or dt.datetime.now(KST)
    stamp = now.isoformat(timespec="seconds")
    watch = kx.load_watch() if watch is None else watch
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    state = {"seen": dict(prev.get("seen") or {}), "industry": dict(prev.get("industry") or {}),
             "companies": dict(prev.get("companies") or {}), "cursor": prev.get("cursor") or 0, "alumni": dict(prev.get("alumni") or {})}
    names = [n for n, _, _ in kx.BEATS]
    codes, missing = gw.resolve_codes(names, registry, table)
    codes.pop("_spellings", None)
    beat_codes = {n: c for n, c in codes.items()}
    old = {e["id"]: e for e in prev.get("events") or [] if isinstance(e, dict) and e.get("id")}
    doc_budget, ind_budget = [DOC_BUDGET], [INDUSTRY_BUDGET]
    checks, fresh = [], []
    fc, fe, fcount = filings_part(key, now, beat_codes, watch, state, get=get, sleep=sleep, doc_budget=doc_budget, ind_budget=ind_budget)
    checks += fc
    fresh += fe
    if not skip_roster:
        beat_set = set(beat_codes.values())
        universe = {}
        for nm, rows in (table or {}).items():
            for r in rows:
                if len(r) > 1 and r[1] and r[0] not in beat_set:
                    universe[r[0]] = nm
        if universe:
            rc, re_ = roster_part(key, now, universe, watch, state, get=get, sleep=sleep, budget=roster_budget or ROSTER_BUDGET, ind_budget=ind_budget)
            checks += rc
            fresh += re_
        else:
            checks.append({"source": "상장사 등기임원 명단 순환", "status": "failed", "error": "DART 고유번호 표 없음"})
    new = []
    for e in fresh:
        e["id"] = f"execm:{e['key']}"
        if e["id"] in old:
            continue
        e["detectedAt"] = stamp
        new.append(e)
    fixed = sum(refresh_agm_flags(e) for e in old.values())
    if fixed:
        checks.append({"source": "이사 후보 결격 칸 다시 판정", "status": "ok", "returned": fixed})
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    events = [e for e in list(old.values()) + new if str(e.get("detectedAt", "")) >= keep]
    events.sort(key=lambda e: (e.get("detectedAt", ""), {"A": 0, "B": 1, "C": 2}.get(e.get("tier"), 3)), reverse=True)
    ok = sum(1 for c in checks if c["status"] == "ok")
    status = "complete" if ok == len(checks) else "failed" if not any(c["status"] in ("ok", "partial") for c in checks) else "partial"
    return {
        "schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "events": events,
        "seen": state["seen"], "industry": state["industry"], "companies": state["companies"], "cursor": state["cursor"], "alumni": state["alumni"],
        "counts": {**fcount, "newEvents": len(new), **{t: sum(1 for e in new if e["tier"] == t) for t in ("A", "B", "C")},
                   "rosterCovered": sum(1 for c in state["companies"].values() if c.get("p")), "rosterUniverse": None},
        "unresolvedCompanies": missing, "watchCompanies": [w["name"] for w in watch],
        "rules": [
            "독립이사 선임·해임·중도퇴임 신고·대표이사 변경 공시는 시장 전체 최근 3일 목록에서, 주총 소집공고는 출입처만 읽는다. 출입처의 독립이사 중도퇴임·해임은 A.",
            "다른 회사는 경력 칸에 출입처 이름과 임원 직함(30자 안)이 같이 있거나 주의 회사가 나온 사람만 남긴다. 같은 그룹 계열사 사이 이동은 뺀다(회사 이름 규칙 — 틀릴 수 있음).",
            "출입처 회사 고위 임원(대표·사장·부사장·전무·C레벨·사내이사) 출신이 다른 회사 등기임원·대표·독립이사로 새로 오르면 A, 그 밖 임원 출신 B(11-05 기자). 이사 후보의 부실기업 경영진 여부·체납·결격 칸이 '없음'이 아니면 A.",
            "출입처 출신 타사 등기임원 현황은 명단 순환에서 본 그대로다(기준선 포함) — kr_signals section=exec에 company 낱말(출입처·회사·사람)로 본다.",
            "상장사 등기임원 명단은 실행마다 일부씩 돌아가며 본다. 회사마다 처음 본 명단은 앞 기간 보고서로 깐 기준선이라 항목을 만들지 않는다.",
            "경력 칸 낱말 일치일 뿐 — 같은 이름의 다른 회사·직책일 수 있다. 결격·부실 칸은 회사 기재 그대로, 내용은 원문 확인. 선임·영입 경위는 회사 확인.",
            "조회 실패·한도로 못 본 공시·회사는 0건이 아니라 미확인.",
        ],
    }


def annotate(doc):
    def mask(s):
        s = str(s or "")
        return s[:1] + "*" * max(0, len(s) - 1)
    c = doc["counts"]
    print(f"::notice title=kr-exec-market-summary::{json.dumps(c, ensure_ascii=False)} · " + " ; ".join(
        f"{k['source']} {k['status']}({k.get('returned', '')}{', ' + k['error'] if k.get('error') else ''})" for k in doc["checks"]))
    shown = [e for e in doc["events"] if e.get("detectedAt") == doc["generatedAt"]][:40]
    for i, e in enumerate(shown):
        p = e.get("person") or {}
        text = e["text"]
        for n in {p.get("name")} - {None, ""}:
            text = text.replace(n, mask(n))
        print(f"::notice title=kr-exec-market-{e['tier']}-{i + 1}::{e['kind']} · {text[:260]} · 표시: {'; '.join(f['text'][:80] for f in e.get('flags') or [])}")


def main():
    global ROSTER_BUDGET, DOC_BUDGET
    ap = argparse.ArgumentParser(description="타사 임원 명단 속 출입처 출신 + 출입처 수시 임원 공시")
    ap.add_argument("--annotate-only", action="store_true")
    ap.add_argument("--roster-budget", type=int)
    ap.add_argument("--doc-budget", type=int)
    ap.add_argument("--skip-roster", action="store_true")
    a = ap.parse_args()
    ROSTER_BUDGET = a.roster_budget if a.roster_budget is not None else ROSTER_BUDGET
    DOC_BUDGET = a.doc_budget or DOC_BUDGET
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        sys.exit("DART_API_KEY 없음 — 이전 결과 유지")
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("kr-exec-market", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-exec-market-state::이전 결과 조회 실패({e}) — 처음부터")
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    try:
        import dart_watch
        table = dart_watch.load_corp_codes(key)
    except SystemExit:
        table = None
    doc = run(key, previous=previous, registry=registry, table=table, roster_budget=ROSTER_BUDGET, skip_roster=a.skip_roster)
    doc["counts"]["rosterUniverse"] = sum(1 for rows in (table or {}).values() for r in rows if len(r) > 1 and r[1])
    if a.annotate_only:
        annotate(doc)
        return
    c = doc["counts"]
    print(f"::notice title=kr-exec-market::수시 공시 목록 {c['listed']} · 고른 {c['picked']} · 원문 {c['opened']} · 명단 순환 {c['rosterCovered']}/{c['rosterUniverse']}"
          f" · 새 항목 {c['newEvents']}(A {c['A']}·B {c['B']}·C {c['C']})")
    if not token:
        print("::warning title=kr-exec-market-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("수시 공시·명단 조회 전체 실패 — 이전 결과 유지(0건 아님)")
    print(f"::notice title=kr-exec-market-push::기자 전용 저장소 전송 HTTP {private_store.put('kr-exec-market', doc, token)}")


if __name__ == "__main__":
    main()
