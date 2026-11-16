#!/usr/bin/env python3
"""정기보고서 숨은 대목(11-15): 출입처가 낸 분기·반기·사업보고서에서 제재 현황, 중요한 소송, 연결 범위 변동을 앞 보고서와 비교해
새로 적힌 줄만 뽑는다.

왜: 11-15 기자 "다른 언론사가 받아쓸 만한 큰 단독". 회사가 보고서에 직접 적었는데 제출 당일 아무도 안 읽는 대목이 여기다 — 과징금·과태료·벌금,
새 피소, 판결·합의, 자회사 편입·제외. 레이더는 임원 명단(kr_exec_watch)·사업의 내용 표·업종 비교만 읽고 있었다.

읽는 곳(DART 서식 제목):
  · 재무제표 주석 '보고기간후사건'(연결·별도) — 기준일 뒤 제출일까지의 일(자회사 매각·인수·청산·사채 발행 등). 적힌 줄 전부가 새 줄이다
  · 재무제표 주석 '매각예정자산 및 중단영업' — 글로 적은 줄만(사업부·공장 매각·운영 중단 결정)
  · '제재 등과 관련된 사항'(XI-3) — 수사·사법기관, 행정기관(공정위·과세당국·고용부·환경 등)의 제재와 이행 현황
  · '우발부채 등에 관한 사항'(XI-2)의 '중요한 소송사건' 대목 — 견질어음·채무보증 표는 분기마다 숫자가 바뀌어 읽지 않는다
  · '연결대상회사의 변동내용' 표(회사의 개요) — 신규 연결·연결 제외와 사유
비교: 줄(표 한 줄·문단 하나)에서 숫자·기호를 뺀 글자가 앞 보고서에 없으면 새 줄이다(금액만 바뀐 줄은 안 잡는다 — 진행 상황 글이 바뀌면 잡힌다).
앞 보고서는 처음 한 번만 받고, 그 뒤에는 저장해 둔 줄 열쇠를 쓴다.

실제 원문(11-15 probe 249·250, 3분기보고서 10곳): 분기보고서는 제재 대목을 생략할 수 있다 — 6곳이 "작성기준에 따라 분기보고서에는 기재를 생략".
생략은 0줄(해당사항 없음)과 다르다: 비교하지 않고, 앞 보고서 열쇠를 이어 둔다. 연결 범위 표도 3분기보고서 대부분에 없다.
'항목 | 내용' 두 칸짜리 사건 표는 표 하나가 한 건이다 — 당사자가 처음이면 '처음 보는 건', 같은 당사자면 바뀐 줄만.

한계(화면에도 적는다): 자동 비교다 — 서식이 바뀌면 옛 줄이 새 줄로 보일 수 있다. 새 줄이라도 사건 자체는 앞서 보도됐을 수 있다.
보고서에 적힌 것은 회사의 기재이고 시점·금액·사유는 원문과 회사 확인이 필요하다.
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
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import earnings_compare as ec  # noqa: E402
import governance_watch as gw  # noqa: E402
import kr_exec_watch as kx  # noqa: E402  (BEATS·SHORT·SPELLINGS·fetch_document·BASE·AS_OF)

SCHEMA = "kr_report_notes/v1"
KST = ec.KST
SOURCE = "정기보고서 숨은 대목"
DOC_BUDGET = 60      # 원문 내려받기 한 실행 한도(원문 1개 20초 안팎) — 넘으면 다음 실행(대기, 0건 아님)
PAUSE = 0.3
KEEP_LINES = 8       # 대목마다 보여 줄 새 줄 수
LINE_MAX = 600
KEEP_KEYS = 2500     # 회사·대목마다 저장해 두는 줄 열쇠 수(열쇠는 10글자 해시)
SEP = " ▸ "          # '항목 | 내용' 두 칸짜리 표(사건 하나가 표 하나)를 한 줄로 이을 때
REPORT_NAME = {"11013": "분기보고서", "11012": "반기보고서", "11014": "분기보고서", "11011": "사업보고서"}
MONTH = {"11013": "03", "11012": "06", "11014": "09", "11011": "12"}
# after·held(11-15 probe 251): 11-13 이데일리 단독 「한화솔루션, 한화시마론 한화디펜스에 넘겼다」는 11-12 분기보고서 연결 주석 '31. 보고기간후사건'의 한 문장
# (10-30 Hanwha Cimarron LLC 지분 전부 매각, 58,962백만원)이었다. 같은 보고서 '15. 매각예정자산 및 중단영업'에는 오펠라이카 공장 운영 중단 결정이 적혀 있었다.
# 이 두 주석은 분기보고서에서도 생략되지 않는다.
SECTIONS = {"after": "보고기간 후 사건", "dated": "작성기준일 이후 주요사항", "held": "매각예정·중단영업", "sanction": "제재", "suit": "소송", "consol": "연결 범위",
            "guarantee": "이행보증·자금보충", "deal": "이해관계자 거래(출자·처분)", "order": "수주"}
# 앞 보고서와 견주지 않아도 새 줄인 대목(그 보고서 기준일 뒤의 일) — 앞 보고서에 대목이 없어도 비교한다
AFTER_LIKE = ("after", "dated")
MUST = ("sanction", "suit")   # 모든 정기보고서에 제목이 있는 대목 — 못 찾으면 미확인. 나머지(보고기간 후 사건·매각예정·연결 범위 표)는 없는 보고서가 흔하다
VERSION = 4          # 읽는 대목이 늘면 올린다 — 앞서 읽은 접수번호도 한 번 다시 읽는다(4: 작성기준일 이후·이행보증·이해관계자 거래·수주, 11-17)
AFTER_TITLE = re.compile(r"보고기간\s*후\s*사건|보고기간\s*종료\s*일?\s*(?:이후|후)|재무상태표일\s*(?:이후|후)")
HELD_TITLE = re.compile(r"매각예정|중단\s*영업")
DATED_TITLE = re.compile(r"작성\s*기준일\s*이후")
# 'Ⅺ-4. 작성기준일 이후 발생한 주요사항 등 기타사항'에서 '가.' 뒤에 오는 소제목(11-17 탐침: 녹색경영·인증·보호예수 줄이 새 줄로 섞임)
DATED_STOP = re.compile(r">\s*나\s*[.)]\s*[가-힣]|합병\s*등의?\s*사후\s*정보|녹색\s*(?:경영|기술|인증|성장)|온실\s*가스\s*(?:배출|에너지)|정부의?\s*인증|"
                        r"조건부\s*자본\s*증권|보호\s*예수|공모\s*자금|직접\s*금융\s*자금")
# 표로 고르는 대목(11-17 3분기보고서 전수 비교: 한화솔루션 RWE 이행보증·롯데케미칼 Kor-UZ 감자·포스코퓨처엠 HyREX 수주 줄이
# 이 감시의 다섯 대목 밖에 있었다). 표 머리 두 줄과 표 바로 앞 글로 가른다 — 수주 > 이해관계자 거래 > 보증 순.
ORDER_HEAD = re.compile(r"수주\s*(?:일자|일|총액|금액|잔고|잔액|내역)")
# 이해관계자 거래: '대주주와의 자산양수도 등' 표(거래유형·거래 대상물·거래 목적 칸) — 특수관계자 매출·매입 표는 아니다
DEAL_HEAD = re.compile(r"거래\s*유형|거래\s*대상물")   # '거래목적'만 있는 표는 파생상품 거래 내역(탐침: 고려아연 금·달러 선물 25줄)
# 보증: 이행보증·계약이행·자금보충만(고객 계약·사업 위험이 드러나는 것). 자회사 차입 지급보증·PF 신용보강·받은 보증은 분기마다 수십 줄이고
# 큰 것은 따로 공시된다(11-17 탐침: 보증 표 전체를 보니 LS 94줄·두산 67줄 — 대부분 차입보증·PF·주석 전치표)
GUAR = re.compile(r"(?:이행|채무|지급|연대)\s*보증|자금\s*보충|보증\s*(?:금액|한도|내역|기간|처|종류)")
GUAR_KEEP = re.compile(r"이행\s*보증|계약\s*이행|자금\s*보충|이행\s*의무|이행하지\s*않은")
NOT_GUAR_HEAD = re.compile(r"거래|우발\s*부채|의무의\s*성격|추정\s*재무\s*영향|금융\s*자산|차입|지급\s*보증|채무\s*보증")
# 주석 전치표의 항목 줄('의무의 성격에 대한 기술…', '우발부채의 추정재무영향…')과 '…내역은 없습니다' 줄(탐침 3: OCI홀딩스 10줄)
GUAR_ROW_SKIP = re.compile(r"의무의\s*성격|추정\s*재무\s*영향|지급\s*보증\s*기관|내역은\s*없습니다")
GUAR_SKIP = re.compile(r"제공\s*받은|PF|신용\s*보강|보고\s*기간\s*(?:후|종료)|위험\s*관리|시장\s*위험")
TABLE_MAX = 200000   # 이보다 큰 표(상세표 통째)는 보지 않는다
LABEL = re.compile(r"〔[^〔〕]{0,60}〕")   # 줄에 붙인 칸 이름(〔칸〕값)·위 줄에서 이어진 칸(〔칸=값〕) — 열쇠에서는 뺀다
CELLX = re.compile(r"<(TD|TE|TU|TH)\b([^>]*)>(.*?)</\1>", re.S | re.I)
DATE = re.compile(r"(?<![\d.,])(?:((?:19|20)\d\d)\s*(?:[.\-/]|년)\s*(\d{1,2})(?!\d)|['‘’]?(\d\d)\s*\.\s*(\d{1,2})\s*\.\s*\d{1,2}(?!\d))")
EMPTY = re.compile(r"해당\s*사항\s*(?:이\s*)?없|해당\s*없음|^[-–—\s]*$")
# 분기보고서는 일부 대목을 줄여 적을 수 있다(11-15 probe 249: 16곳 중 여러 곳의 제재 대목이 한 줄) — 그 안내 줄은 새 줄이 아니다
BOILER = re.compile(r"기재를?\s*생략|기재하지\s*(?:않|아니)|변동\s*(?:된\s*)?(?:사항|내용)\s*(?:이|은)?\s*없|참[조고]하(?:시기|여|십시오)")
KV_LABEL = re.compile(r"소송|당사자|원고|피고|사건|진행|제기|청구|내용|일자|처벌|조치|사유|근거|대상자|기관|영향|대응|일정|가액|금액")
IDENT = re.compile(r"당사자|원고|피고|신청인|사건\s*명|사건\s*번호")
# 분기마다 글자만 바뀌는 말('당반기말'→'당분기말') — 줄 열쇠에서 뺀다(probe 250: 포스코홀딩스 '당반기말 현재 … 소송사건 451건' 문단이 매번 새 줄로 보였다)
PERIOD_WORDS = re.compile(r"당\s*(?:분기|반기|기)\s*말?|(?:분기|반기|보고기간|사업연도|회계연도)\s*말|기준일")
# 줄이 아닌 것: 표 머리('일자 | 제재기관 | 대상자 …'), 단위·기준일 줄, 소제목
HEAD_ROW = re.compile(r"제재\s*기관|처벌\s*또는\s*조치|조치\s*내용")
MONEY_UNIT = re.compile(r"(?<=\d)\s*(?:십|백|천)?(?:조|억|만|천)?\s*원")
SUBJECT = re.compile(r"(?:연결\s*실체|연결\s*회사|지배\s*기업|지배\s*회사|당사|회사)(?:는|은|가|의)\s*")
LABEL_CELL = re.compile(r"에\s*대한\s*(?:기술|공시|설명)\s*$")
SENTENCE = re.compile(r"[가-힣]다(?:[.\s(,·]|$)")   # '…매각하였습니다(매각대금 58,962백만원).'처럼 괄호가 붙는 문장도
NOISE = re.compile(r"^[\[(（]?\s*(?:기준일|단위|원화\s*단위)|^\[[^\]]{1,70}\]$")
HEADING = re.compile(r"제재\s*현황|소송\s*사건|다음과\s*같습니다|기재하였습니다|지배\s*회사|종속\s*회사")
TITLE = re.compile(r"<TITLE\b[^>]*>(.*?)</TITLE>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")


def clean(s):
    return re.sub(r"\s+", " ", kx.html.unescape(TAG.sub(" ", s or ""))).strip()


def key_of(line):
    """숫자·기호·빈칸을 뺀 글자 — 금액·날짜 표기만 다른 줄은 같은 줄로 본다.
    금액 단위('각 100만원' ↔ '각 1,000,000 원' — 11-15 운영: 롯데케미칼 제재 표가 단위 표기만 바뀌어 옛 줄 23줄이 새 줄로 보였다)와
    주어('연결실체는' ↔ '당사는' — 연결·별도 주석이 같은 사건을 두 번 적는다)도 뺀다. 이 함수를 바꾸면 저장해 둔 열쇠와 어긋나므로 VERSION을 올린다."""
    line = MONEY_UNIT.sub("", PERIOD_WORDS.sub("", LABEL.sub(" ", line)))
    return re.sub(r"[\d\s.,·()\[\]\-–—~%:/|※*'\"“”‘’㈜]", "", SUBJECT.sub("", line))


def span_of(attrs, name):
    m = re.search(name + r"""\s*=\s*["']?(\d+)""", attrs or "", re.I)
    return max(1, min(int(m.group(1)), 40)) if m else 1


def table_grid(part):
    """표 → 줄마다 [(칸 번호, 글자, 위 줄에서 이어진 칸인지, 차지한 칸 수)]. ROWSPAN·COLSPAN을 펴서 칸 번호를 맞춘다(칸 이름 붙이기용).
    줄 수는 kx.ROW와 같다."""
    out, carry = [], {}   # carry: 칸 번호 → [남은 줄 수, 글자, 첫 칸인지, 차지한 칸 수]
    for tr in kx.ROW.findall(part):
        cells, c, started = [], 0, {}

        def pull(limit=None):
            nonlocal c
            while c in carry and (limit is None or c < limit):
                left, text, first, span = carry[c]
                if first:
                    cells.append((c, text, True, span))
                c += 1
        for _, attrs, body in CELLX.findall(tr):
            pull()
            text, cs, rs = clean(body), span_of(attrs, "COLSPAN"), span_of(attrs, "ROWSPAN")
            cells.append((c, text, False, cs))
            if rs > 1:
                for k in range(cs):
                    started[c + k] = [rs - 1, text, k == 0, cs]
            c += cs
        for col in sorted(k for k in carry if k >= c):
            left, text, first, span = carry[col]
            if first:
                cells.append((col, text, True, span))
        for col in list(carry):
            carry[col][0] -= 1
            if carry[col][0] <= 0:
                del carry[col]
        carry.update(started)
        out.append(cells)
    return out


def short_label(parts):
    text = "·".join(dict.fromkeys(p for p in parts if p))
    text = re.sub(r"[〔〕]", "", text)
    return text if len(text) <= 18 else text[:17] + "…"


def labelled(grid, labels, *, skip_first=False):
    """내용 줄 → '〔칸 이름〕값 | 〔칸 이름〕값'(칸 이름을 모르면 값만). 위 줄에서 합쳐 내려온(ROWSPAN) 칸 값도 제자리에 넣는다 —
    행이 끼어들면 합친 칸의 첫 줄이 바뀌어, 값을 첫 줄에만 두면 같은 줄이 다른 열쇠가 된다(11-17 탐침: 포스코홀딩스 수주 표 50줄이 새 줄로 보임).
    〔칸 이름〕은 열쇠(key_of)에서 빠진다 — 머리글 표기가 바뀌어도 같은 줄이다."""
    cells = sorted((g for g in grid if g[1]), key=lambda g: g[0])
    if skip_first:
        own = [g for g in cells if not g[2]]
        if own:
            cells = [g for g in cells if g is not own[0]]
    out = []
    for col, text, _, _ in cells:
        name = short_label(labels.get(col) or [])
        out.append((f"〔{name}〕" if name and name != text else "") + text)
    return " | ".join(out)


def dates_of(line):
    """줄에 적힌 (해, 달)들 — '2026-08-21'·'2026년 8월'·'26. 08. 21'."""
    out = []
    for m in DATE.finditer(line or ""):
        y, mo = (int(m.group(1)), int(m.group(2))) if m.group(1) else (2000 + int(m.group(3)), int(m.group(4)))
        if 1 <= mo <= 12 and 2000 <= y <= 2100:
            out.append((y, mo))
    return out


def latest_date(line):
    """줄에 적힌 가장 늦은 (해, 달). 없으면 None."""
    got = dates_of(line)
    return max(got) if got else None


def in_period(line, since, until):
    """앞 보고서 기준일 뒤 ~ 지금 사이 날짜가 적힌 줄인지 — 계약 종료일·보증 만기 같은 앞날 날짜는 세지 않는다
    (탐침: 포스코홀딩스 수주 표에서 2025년 시작·2030년 종료 계약이 2026년 8월 새 계약보다 앞에 섰다)."""
    return any(since < d <= until for d in dates_of(line))


def near_text(text, start, span=2500):
    """표 바로 앞 글(끝 240자). 앞 표가 끝난 뒤부터만 보되, '[기준일 : …] (단위 : …)' 같은 짧은 표는 글로 본다
    (11-17 탐침: 한화솔루션 '다. 이행보증, 자금보충 약정 등' 문단과 보증 표 사이에 단위 표가 끼어 있었다)."""
    seg = text[max(0, start - span):start]
    up = seg.upper()
    pos = len(seg)
    while True:
        close = up.rfind("</TABLE>", 0, pos)
        if close < 0:
            break
        opening = up.rfind("<TABLE", 0, close)
        if opening < 0 or len(clean(seg[opening:close])) > 160:
            seg = seg[close + 8:]
            break
        pos = opening
    return clean(seg)[-240:]


def units(block):
    """대목 글자 → 줄. 표 한 줄 또는 문단 하나가 한 줄이고, '항목 | 내용' 두 칸짜리 표(사건 하나가 표 하나)는 표 전체가 한 줄이다.
    머리 줄·빈 줄·'해당사항 없음'·'기재 생략' 안내 줄은 뺀다."""
    out = []
    for part in kx.TABLE_SPLIT.split(block or ""):
        if part[:6].upper() == "<TABLE":
            rows, cols = [], []
            for (head, cells), grid in zip(((bool(re.search(r"<TH\b", tr, re.I)), [c for c in (clean(c[1]) for c in kx.CELL.findall(tr)) if c])
                                            for tr in kx.ROW.findall(part)), table_grid(part)):
                if cells:
                    rows.append((head, cells))
                    cols.append(grid)
            pairs = [c for _, c in rows if len(c) == 2 and len(c[0]) <= 30 and not re.fullmatch(r"구\s*분|항\s*목", c[0])]
            # 두 칸 표로 보는 조건: 세 칸 넘는 줄이 하나도 없어야 한다(probe 252: 한화솔루션 '보고기간후사건' 표는 사건이 열로 나뉜 표였는데
            # 두 칸 줄이 많다는 이유로 두 칸 표로 읽혀, 사건을 글로 적은 세 칸짜리 줄 — 한화시마론 매각 문장 — 이 통째로 빠졌다)
            if len(pairs) >= 3 and all(len(c) <= 2 for _, c in rows) and any(KV_LABEL.search(c[0]) for c in pairs):
                line = SEP.join([c[0] for _, c in rows if len(c) == 1 and len(c[0]) >= 20] + [f"{k}: {v}" for k, v in pairs if not EMPTY.search(v)])
                if len(key_of(line)) >= 12:
                    out.append(line)
                continue
            labels, started = {}, False
            for (head, cells), grid in zip(rows, cols):
                # 주석 표의 칸 이름('…의 성격에 대한 기술', '…에 대한 공시')은 줄 글자에서 뺀다
                drop_first = len(cells) > 1 and LABEL_CELL.search(cells[0])
                if drop_first:
                    cells = cells[1:]
                elif len(cells) == 1 and LABEL_CELL.search(cells[0]) and len(cells[0]) < 60:
                    continue
                line = " | ".join(cells)
                # 머리 줄: <TH>거나, 숫자 없이 짧은 칸뿐이거나, 연도 없이 '제재기관·처벌 또는 조치' 같은 칸 이름만 있는 줄
                if head or (not re.search(r"\d", line) and all(len(c) <= 16 for c in cells)) or (HEAD_ROW.search(line) and not re.search(r"(?:19|20)\d\d", line)):
                    # 표 맨 위(첫 내용 줄 전)의 머리 줄만 칸 이름으로 쓴다 — 표 가운데 '국내'·'해외' 같은 구분 줄은 칸 이름이 아니다
                    if not started and (head or len(cells) >= 2) and not NOISE.search(line):
                        for col, text, _, span in grid:
                            if text and not NOISE.search(text):
                                for k in range(span):
                                    got = labels.setdefault(col + k, [])
                                    if not got or got[-1] != text:
                                        got.append(text)
                    continue
                if len(key_of(line)) >= 8 and not EMPTY.search(line) and not NOISE.search(line) and not (BOILER.search(line) and len(line) < 160):
                    started = True
                    out.append(labelled(grid, labels, skip_first=bool(drop_first)))
        else:
            for p in re.split(r"</P>|<BR\s*/?>", part, flags=re.I):
                line = clean(p)
                if NOISE.search(line) or (len(line) < 70 and (HEADING.search(line) or LABEL_CELL.search(line))):
                    continue
                if len(key_of(line)) >= 12 and not EMPTY.search(line) and not (BOILER.search(line) and len(line) < 160):
                    out.append(line)
    seen, uniq = set(), []
    for line in out:
        k = key_of(line)
        if k not in seen:
            seen.add(k)
            uniq.append(line)
    return uniq


def digest(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def ident_of(rows):
    """두 칸 표 한 건의 '누구 사건인지' 열쇠 — 당사자·원고·피고·사건명 줄(없으면 앞 두 줄)."""
    named = [r for r in rows if IDENT.search(r.split(":", 1)[0])]
    return key_of(" ".join(named or rows[:2]))


def keys_of(lines):
    """저장해 둘 줄 열쇠(해시). 두 칸 표는 표 전체·사건 열쇠(I)·줄마다(R) 열쇠를 함께 둔다 — 다음 보고서에서 '새 사건'과 '바뀐 줄'을 가른다."""
    out = []
    for x in lines:
        out.append(digest(key_of(x)))
        if SEP in x:
            rows = x.split(SEP)
            out.append(digest("I" + ident_of(rows)))
            out += [digest("R" + key_of(r)) for r in rows]
    return list(dict.fromkeys(out))[:KEEP_KEYS]


def tail(row, keep=240):
    """진행 상황 칸은 처음부터 지금까지를 다 적는다 — 긴 줄은 끝(가장 최근)만 보여 준다."""
    label, sep, value = row.partition(": ")
    return row if len(row) <= keep + 60 or not sep else f"{label}: … {value[-keep:]}"


def fresh_lines(lines, have):
    """앞 보고서 열쇠(have)에 없는 줄. 두 칸 표는 같은 사건이면 바뀐 줄만, 처음 보는 사건이면 표 전체."""
    out = []
    for x in lines:
        if digest(key_of(x)) in have:
            continue
        if SEP in x:
            rows = x.split(SEP)
            if digest("I" + ident_of(rows)) in have:
                changed = [r for r in rows if digest("R" + key_of(r)) not in have]
                if changed:
                    named = [r for r in rows if IDENT.search(r.split(":", 1)[0])] or rows[:1]
                    out.append(f"〔앞 보고서에도 있던 건 · 바뀐 줄〕 {' / '.join(named)[:160]} — {SEP.join(tail(r) for r in changed)}")
                continue
            out.append("〔처음 보는 건〕 " + x)
        else:
            out.append(x)
    return out


def prose(lines, *, keep_rows):
    """주석 표의 줄에서 글로 적은 문장 칸을 한 칸씩 줄로 가른다(사건이 열로 나뉜 표는 한 줄에 사건 두 개가 들어 있다).
    keep_rows=True면 문장이 없는 줄(사채 발행 표 같은 표 줄)도 그대로 둔다."""
    out = []
    for x in lines:
        cells = [c for c in x.split(" | ")] if SEP not in x else [x]
        said = [LABEL.sub("", c).strip() for c in cells if len(c) >= 30 and SENTENCE.search(c)]
        if said:
            out += said
        elif keep_rows:
            out.append(x)
    # 문장으로 적은 사건이 있으면, 그 숫자를 되풀이한 짧은 표 줄('현금출자, 출자금 납입 | 68,260')은 뺀다
    if any(SENTENCE.search(x) for x in out):
        out = [x for x in out if SENTENCE.search(x) or len(x) >= 60]
    return out


def same_lines(a, b):
    def ks(lines):
        return {key_of(x) for x in lines or [] if not str(x).startswith("…")}
    return ks(a) == ks(b)


def merged(old, new):
    out, seen = [], set()
    for x in list(old or []) + list(new or []):
        k = key_of(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def sections(text):
    """보고서 본문 → {'after': [줄], 'held': [줄], 'sanction': [줄], 'suit': [줄], 'consol': [줄]}. 못 찾은 대목은 키가 없다(0줄과 다르다).
    대목은 있는데 '분기보고서에는 기재를 생략' 안내만 있으면 값이 None이다(0줄 — 해당사항 없음 — 과 다르다. probe 249·250: 3분기보고서 10곳 중 6곳이 제재 대목 생략)."""
    marks = [(m.start(), m.end(), clean(m.group(1))) for m in TITLE.finditer(text)]
    body = {}
    for i, (_, end, title) in enumerate(marks):
        nxt = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        if re.search(r"제재\s*(?:등과|등에|현황)", title) and "sanction" not in body:
            got = units(text[end:nxt])
            body["sanction"] = None if not got and BOILER.search(clean(text[end:nxt])[:600]) else got
        elif AFTER_TITLE.search(title):
            body["after"] = merged(body.get("after"), prose(units(text[end:nxt]), keep_rows=True))   # 연결·별도 주석을 합친다
        elif DATED_TITLE.search(title) and "dated" not in body:
            # 'Ⅺ-4. 작성기준일 이후 발생한 주요사항 등 기타사항'의 '가.' 부분만(나. 합병 등의 사후정보·다. 녹색경영 앞까지).
            # 11-17: OCI홀딩스 3분기보고서 — 'OCI Alabama LLC가 매각됨에 따라 연결대상 종속회사에서 제외'가 여기 한 줄이었다.
            block = text[end:nxt]
            stop = DATED_STOP.search(block, 30)
            if stop:
                # 멈춤 낱말이 든 문단(표)의 처음에서 자른다 — 문장 가운데서 자르거나 태그를 반쯤 남기지 않게
                up = block.upper()
                block = block[:max(up.rfind("<P", 0, stop.start()), up.rfind("<TABLE", 0, stop.start()), 0)]
            body["dated"] = prose(units(block), keep_rows=True)
        elif HELD_TITLE.search(title):
            # 매각예정자산 주석은 숫자 표가 대부분 — 글로 적은 문장(결정·사유)만 본다
            body["held"] = merged(body.get("held"), prose(units(text[end:nxt]), keep_rows=False))
        elif re.search(r"우발\s*(?:부채|채무)\s*등", title) and "suit" not in body:
            block = text[end:nxt]
            m = re.search(r"중요한\s*소송|소송\s*사건", block)
            if m:
                rest = block[m.start():]
                stop = re.search(r"견질\s*또는\s*담보|담보용\s*어음|채무\s*보증\s*현황|채무\s*인수\s*약정", rest[20:])
                got = units(rest[:20 + stop.start()] if stop else rest)
                body["suit"] = None if not got and BOILER.search(clean(rest)[:400]) else got
    # 주석마다 제목 표시가 없는 보고서: 본문에서 '31. 보고기간후사건' 같은 소제목을 찾아 다음 제목 전까지
    if "after" not in body:
        for m in re.finditer(r">\s*\(?\d{1,2}\)?\.?\s*보고기간\s*후\s*사건[^<]{0,30}<", text):
            block = text[m.end() - 1:m.end() + 9000]
            stop = re.search(r"<TITLE\b|<P[^>]*>\s*\d{1,2}\.\s*[가-힣]", block[60:])
            body["after"] = merged(body.get("after"), prose(units(block[:60 + stop.start()] if stop else block), keep_rows=True))
    # 표로 고르는 대목: 이행보증·자금보충, 이해관계자와의 출자·처분·자산양수도, 수주 — 표 머리 두 줄과 표 바로 앞 글로 가른다
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", text, re.S | re.I):
        table = m.group(0)
        if len(table) > TABLE_MAX:
            continue
        head = clean(" ".join(kx.ROW.findall(table)[:2]))
        near = near_text(text, m.start())
        lines = None
        if ORDER_HEAD.search(head):
            sec = "order"
        elif DEAL_HEAD.search(head):
            sec = "deal"
        elif (GUAR.search(head) or GUAR.search(near[-160:])) and not GUAR_SKIP.search(head + " " + near[-160:]):
            sec = "guarantee"
            # 표 머리에 이행보증·자금보충이 있으면 표 전체, 아니면 그 낱말이 든 줄만 — 표 앞 글로 표 전체를 받으면
            # 특수관계자 거래·우발부채 전치표가 섞였다(탐침: OCI홀딩스 28줄)
            whole = bool(GUAR_KEEP.search(head) or (GUAR_KEEP.search(near[-160:]) and re.search(r"금액|보증", head) and not NOT_GUAR_HEAD.search(head)))
            lines = [x for x in units(table) if (whole or GUAR_KEEP.search(x)) and not GUAR_SKIP.search(x[:120]) and not GUAR_ROW_SKIP.search(x[:80])]
        else:
            continue
        lines = units(table) if lines is None else lines
        # 주석의 전치표(행이 항목, 열이 보증 건 — 같은 칸 이름이 한 줄에 세 번 넘게)는 열이 하나 늘면 모든 줄이 바뀐다 — 뺀다
        lines = [x for x in lines if max(Counter(LABEL.findall(x)).values() or [0]) < 3]
        body[sec] = merged(body.get(sec), lines)
    # 연결 범위: 신규 연결·연결 제외가 함께 든 표(회사의 개요)
    for table in re.findall(r"<TABLE\b.*?</TABLE>", text, re.S | re.I):
        flat = clean(table)
        if re.search(r"신규\s*연결", flat) and re.search(r"연결\s*제외", flat) and len(flat) < 6000:
            rows = []
            kind = ""
            for tr in kx.ROW.findall(table):
                cells = [clean(c[1]) for c in kx.CELL.findall(tr)]
                if re.search(r"<TH\b", tr, re.I) and not re.search(r"신규|제외", " ".join(cells)):
                    continue
                cells = [c for c in cells if c]
                if cells and re.fullmatch(r"(?:신규\s*연결|연결\s*제외)", cells[0]):
                    kind, cells = re.sub(r"\s+", " ", cells[0]), cells[1:]
                if kind and cells and not EMPTY.search(" ".join(cells)) and not all(c in ("-", "–") for c in cells):
                    rows.append(f"{kind}: " + " | ".join(cells))
            body["consol"] = rows
            break
    return body


def report_of(rows, year, report):
    """공시 목록에서 그 기간 정기보고서의 (접수번호, 접수일) — 정정이 있으면 가장 늦게 낸 것."""
    want = f"{REPORT_NAME[report]} ({year}.{MONTH[report]})"
    hit = [r for r in rows if want in str(r.get("report_nm") or "")]
    hit.sort(key=lambda r: (str(r.get("rcept_dt") or ""), str(r.get("rcept_no") or "")), reverse=True)
    return (hit[0]["rcept_no"], hit[0].get("rcept_dt")) if hit else (None, None)


def read_report(key, rcept, *, get, sleep, budget):
    """(상태, 대목들, 오류). 예산이 없으면 'waiting'."""
    if budget[0] <= 0:
        return "waiting", None, "원문 대기"
    budget[0] -= 1
    texts, err = kx.fetch_document(key, rcept, get=get, sleep=sleep, want="제재")
    sleep(PAUSE)
    if not texts:
        # OpenDART 014(파일이 존재하지 않습니다): 접수 뒤 몇 시간은 원문 파일이 아직 없다 — 실패가 아니라 대기다(다음 실행이 다시 읽는다).
        # 11-16 분기보고서 마감일: 18:10 실행 16곳·19:40 실행 10곳이 이 응답이었고, 20:27 실행에서 그중 8곳이 읽혔다.
        if "<status>014" in str(err or ""):
            return "waiting", None, "원문 파일 준비 전(OpenDART 014)"
        return "failed", None, err or "원문 없음"
    best = {}
    for text in texts[:3]:
        got = sections(text)
        if len(got) > len(best):
            best = got
    return ("ok", best, None) if best else ("failed", None, "원문에서 제재·소송·연결 범위 대목을 못 찾음")


def run(key, *, now=None, year=None, report=None, previous=None, get=None, sleep=time.sleep, registry=None, table=None, only=None):
    if get is None:
        import requests
        get = requests.get
    now = now or dt.datetime.now(KST)
    stamp = now.isoformat(timespec="seconds")
    if not year or not report:
        year, report = ec.target_period(now)
    dy, base_report = kx.BASE[report]
    base_year = year + dy
    period = f"{year}{report}"
    prev = previous if isinstance(previous, dict) else {}
    notes = {k: v for k, v in (prev.get("companies") or {}).items() if isinstance(v, dict)}
    old_events = [e for e in prev.get("events") or [] if isinstance(e, dict) and e.get("id")]
    old_by_id = {e["id"]: e for e in old_events}
    first_run = not prev.get("companies")
    names = [n for n, _, _ in kx.BEATS if not only or n in only or kx.SHORT.get(n, n) in only]
    codes, _ = gw.resolve_codes(names, registry, table)
    for name, alts in kx.SPELLINGS.items():
        if name in names and name not in codes:
            for alt in alts:
                c2, _ = gw.resolve_codes([alt], registry, table)
                if alt in c2:
                    codes[name] = c2[alt]
    budget, events, checks = [DOC_BUDGET], [], []
    since_month, now_month = (base_year, int(MONTH[base_report])), (now.year, now.month)
    since = (now - dt.timedelta(days=430)).strftime("%Y%m%d")
    for name in names:
        short = kx.SHORT.get(name, name)
        code = codes.get(name)
        if not code:
            checks.append({"source": short, "status": "failed", "error": "DART 고유번호 못 찾음"})
            continue
        try:
            st, body = ec.call("list.json", {"corp_code": code, "bgn_de": since, "end_de": now.strftime("%Y%m%d"), "pblntf_ty": "A", "page_count": "40"},
                               get=lambda u, params, **kw: get(u, params={"crtfc_key": key, **params}, **kw), sleep=sleep)
        except Exception as e:  # noqa: BLE001 — 조회 실패는 0건이 아니라 미확인
            checks.append({"source": short, "status": "failed", "error": f"{type(e).__name__}: {str(e)[:60]}"})
            continue
        sleep(PAUSE)
        rows = (body or {}).get("list") or [] if st == "ok" else []
        rcept, filed = report_of(rows, year, report)
        if not rcept:
            checks.append({"source": short, "status": "ok", "returned": 0, "note": "이 기간 보고서 미제출(또는 제출 대상 아님)"})
            continue
        kept = notes.get(short) or {}
        if kept.get("rcept") == rcept and kept.get("status") == "ok" and kept.get("v") == VERSION:
            checks.append({"source": short, "status": "ok", "returned": sum(len(v) for v in (kept.get("new") or {}).values()), "note": "앞서 읽음"})
            continue
        # 앞 보고서 줄 열쇠: 저장본(직전 기간에 읽어 둔 것)이 있으면 그것, 없으면 앞 보고서를 받는다
        # 대목이 늘기 전(v가 다른) 저장본의 앞 보고서 열쇠는 새 대목 열쇠가 없다 — 앞 보고서를 다시 받는다
        base_keys = kept.get("keys") if kept.get("period") == f"{base_year}{base_report}" and kept.get("v") == VERSION else None
        base_rcept = None
        if base_keys is None:
            base_rcept, _ = report_of(rows, base_year, base_report)
            if not base_rcept:
                checks.append({"source": short, "status": "partial", "error": "앞 보고서를 목록에서 못 찾음 — 비교 못 함"})
                continue
            bst, bsec, berr = read_report(key, base_rcept, get=get, sleep=sleep, budget=budget)
            if bst != "ok":
                checks.append({"source": short, "status": "waiting" if bst == "waiting" else "failed", "error": f"앞 보고서 {berr}"})
                continue
            base_keys = {k: (None if v is None else keys_of(v)) for k, v in bsec.items()}   # None = 앞 보고서가 그 대목을 생략
        cst, csec, cerr = read_report(key, rcept, get=get, sleep=sleep, budget=budget)
        if cst != "ok":
            # 앞 보고서 열쇠는 버리지 않는다 — 다음 실행에 이번 보고서만 다시 받는다
            notes[short] = {"v": VERSION, "period": f"{base_year}{base_report}", "keys": base_keys, "status": "pending", "rcept": None}
            checks.append({"source": short, "status": "waiting" if cst == "waiting" else "failed", "error": cerr})
            continue
        new, omitted, nobase = {}, [], []
        for sec, lines in csec.items():
            if lines is None:
                omitted.append(sec)   # 이번 보고서가 이 대목을 생략(분기보고서) — 0건이 아니라 비교 못 함
                continue
            if base_keys.get(sec) is None and sec not in AFTER_LIKE:
                nobase.append(sec)    # 앞 보고서에서 못 찾았거나 앞 보고서가 생략 — 비교하지 않는다(전부 새 줄로 보이는 것을 막는다). 이번 줄은 다음 비교의 기준이 된다
                continue
            # 보고기간 후 사건은 그 보고서 기준일 뒤의 일이라 앞 보고서에 없어도 전부 새 줄이다
            fresh = fresh_lines(lines, set(base_keys.get(sec) or []))
            # 이번 보고 기간(앞 보고서 기준일 뒤) 날짜가 적힌 줄을 앞으로 — 옛 사건이 서식만 바뀌어 새 줄로 보일 때 새 사건이 묻히지 않게
            # (11-17: 포스코홀딩스 소송 새 줄 26줄 중 포스코이앤씨→다원시스 4,859억 회생채권 줄이 '그 밖 18줄'에 묻혀 있었다)
            fresh.sort(key=lambda x: 0 if in_period(x, since_month, now_month) else 1)
            if fresh:
                new[sec] = [x[:LINE_MAX] for x in fresh[:KEEP_LINES]] + ([f"… 그 밖 {len(fresh) - KEEP_LINES}줄"] if len(fresh) > KEEP_LINES else [])
        # 다음 보고서와 견줄 열쇠: 이번 줄 + 앞 보고서 줄(이번에 생략했거나 못 찾은 대목이 다음에 통째로 새 줄로 보이지 않게).
        # 이번도 앞도 줄을 못 본 대목은 열쇠를 두지 않는다 — 처음 줄이 보이는 보고서가 기준이 된다.
        keys = {}
        for sec in set(csec) | set(base_keys):
            cur, old = csec.get(sec), base_keys.get(sec)
            if cur is None and old is None:
                continue
            keys[sec] = list(dict.fromkeys(keys_of(cur or []) + list(old or [])))[:KEEP_KEYS]
        url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}"
        notes[short] = {"v": VERSION, "period": period, "rcept": rcept, "filed": filed, "baseRcept": base_rcept or kept.get("rcept"), "status": "ok", "readAt": stamp, "url": url,
                        "found": sorted(k for k, v in csec.items() if v is not None), "missing": sorted(set(MUST) - set(csec)), "omitted": sorted(omitted),
                        "nobase": sorted(nobase), "lines": {k: len(v) for k, v in csec.items() if v is not None}, "new": new, "keys": keys}
        # 늦게 읽은 것(late): 감시를 처음 돌릴 때와 접수 이틀 뒤에야 읽은 보고서 — 화면에는 보이지만 즉시 알림은 걸지 않는다
        try:
            age = (now.date() - dt.datetime.strptime(str(filed), "%Y%m%d").date()).days
        except ValueError:
            age = 0
        late = first_run or age >= 2
        for sec, lines in new.items():
            ev = {"id": f"rptnote:{code}:{period}:{sec}", "kind": SECTIONS[sec], "company": short, "tier": "B", "url": url, "detectedAt": stamp,
                  "filed": filed, "period": kx.period_label(year, report), "lines": lines, **({"late": True} if late else {}),
                  "text": f"{short} {kx.period_label(year, report)} 보고서에 새로 적힌 {SECTIONS[sec]} {len([x for x in lines if not x.startswith('…')])}줄 — {lines[0][:220]}"}
            prior = old_by_id.get(ev["id"])
            if prior and same_lines(prior.get("lines"), lines):   # 정정 보고서를 다시 읽었는데 줄이 그대로면(칸 이름·순서만 달라도) 처음 본 때를 지킨다
                ev["detectedAt"] = prior.get("detectedAt") or stamp
                if prior.get("late"):
                    ev["late"] = True
            events.append(ev)
        checks.append({"source": short, "status": "ok", "returned": sum(len(v) for v in new.values()), "missing": sorted(set(MUST) - set(csec)), "omitted": sorted(omitted)})
    ids = {e["id"] for e in events}
    cutoff = (now - dt.timedelta(days=120)).isoformat()
    events += [e for e in old_events if e["id"] not in ids and str(e.get("detectedAt") or "") >= cutoff]
    bad = [c for c in checks if c["status"] in ("failed", "partial")]
    waiting = [c for c in checks if c["status"] == "waiting"]
    return {"schema": SCHEMA, "generatedAt": stamp, "period": {"year": year, "report": report, "label": kx.period_label(year, report)},
            "status": "partial" if bad or waiting else "complete", "checks": checks, "companies": notes, "events": events,
            "summary": {"companies": len(names), "read": sum(1 for v in notes.values() if v.get("status") == "ok" and v.get("period") == period),
                        "waiting": len(waiting), "failed": len(bad), "docsRead": DOC_BUDGET - budget[0],
                        "newLines": {sec: sum(len([x for x in (v.get("new") or {}).get(sec, []) if not x.startswith("…")]) for v in notes.values() if v.get("period") == period) for sec in SECTIONS}}}


def notice(title, text):
    print(f"::notice title={title}::{text}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    key, token = os.environ.get("DART_API_KEY"), os.environ.get("MCP_ACCESS_TOKEN")
    if not key:
        notice("kr-report-notes", "DART_API_KEY 없음 — 미확인")
        return 0
    import private_store as ps
    previous = None
    if token:
        try:
            previous = ps.get("kr-report-notes", token)
        except Exception as e:  # noqa: BLE001
            notice("kr-report-notes-store", f"저장본 읽기 실패 {type(e).__name__} — 이번에는 저장하지 않는다(앞 보고서 열쇠를 지우지 않으려고)")
            return 0
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    try:
        import dart_watch
        table = dart_watch.load_corp_codes(key)
    except SystemExit:
        table = None
    doc = run(key, previous=previous, registry=registry, table=table, only=a.only)
    s = doc["summary"]
    # 공개 로그에는 건수만(회사 이름·줄 글자는 찍지 않는다)
    notice("kr-report-notes", f"{doc['period']['label']} · 회사 {s['companies']}곳 중 읽음 {s['read']} · 대기 {s['waiting']} · 실패 {s['failed']} · 이번 원문 {s['docsRead']}개 · "
                              f"새 줄 {'·'.join(f'{SECTIONS[k]} {v}' for k, v in s['newLines'].items())} · 대목 못 찾은 회사 "
                              f"{sum(1 for v in doc['companies'].values() if v.get('missing'))}곳 · 보고서 미제출 {sum(1 for c in doc['checks'] if c.get('note', '').startswith('이 기간'))}곳")
    if a.dry_run or not token:
        return 0
    status = ps.put("kr-report-notes", doc, token)
    notice("kr-report-notes-push", f"기자 전용 저장소 전송 HTTP {status}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
