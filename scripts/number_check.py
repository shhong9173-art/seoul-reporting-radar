"""AI 번역·요약의 숫자가 AI가 받은 영어 원문(제목·RSS 발췌)에 있는지 맞춰 본다.

11-01 기자 요청: AI 요약에 원문에 없는 숫자가 들어가면 표시. 한국어 숫자 표현('4억 5천만', '1조9천3백억', '92만 710')을
값으로 바꾸고, 영어 쪽('US$450m', 'KRW1.93trn', '920,710', 'three', 'Oct.')의 값과 비교한다(반올림 0.6%까지 같은 수로 본다).
못 찾은 숫자는 'AI가 받은 글에 없는 숫자' — 지어낸 숫자이거나, 환산·계산한 숫자이거나, 표기가 달라 못 맞춘 것이다.
표시는 '원문 확인'이지 오류 확정이 아니다.
"""
from __future__ import annotations

import re

KO_SPAN = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s*[조억만천백십]+\s*\d[\d,]*(?:\.\d+)?)*(?:\s*[조억만천백십]+)?")
KO_TOKEN = re.compile(r"(\d[\d,]*(?:\.\d+)?)|([조억만천백십])")
BIG = {"조": 1e12, "억": 1e8, "만": 1e4}
SMALL = {"천": 1e3, "백": 1e2, "십": 10.0}

EN_NUM = re.compile(r"(\d[\d,]*(?:\.\d+)?)(?:\s*(thousand|million|billion|trillion|mln|mn|bn|trn|tn|k|m|b|t)(?![a-z]))?", re.I)
MULT = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "mln": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9,
        "t": 1e12, "tn": 1e12, "trn": 1e12, "trillion": 1e12}
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
         "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90, "hundred": 100, "dozen": 12, "twice": 2, "double": 2, "triple": 3, "quadruple": 4,
         "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
         "half": 50, "quarter": 25}   # 'half' → 50%, 'quarter' → 25%·4분기는 '4'로 따로 잡힌다
_MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
MONTHS = {**{m: i + 1 for i, m in enumerate(_MONTH_NAMES)}, **{m[:3]: i + 1 for i, m in enumerate(_MONTH_NAMES)}, "sept": 9}
WORD_RE = re.compile(r"[a-z]+", re.I)
TOLERANCE = 0.006


def _num(text: str) -> float:
    return float(text.replace(",", ""))


def ko_value(span: str) -> float:
    total = section = 0.0
    num = None
    for digits, unit in KO_TOKEN.findall(span):
        if digits:
            if num is not None:
                section += num
            num = _num(digits)
        elif unit in SMALL:
            section += (num if num is not None else 1.0) * SMALL[unit]
            num = None
        else:
            section += num or 0.0
            total += (section or 1.0) * BIG[unit]
            section, num = 0.0, None
    return total + section + (num or 0.0)


KO_UNIT_AFTER = re.compile(r"\s*(?:원|달러|유로|파운드|엔|위안|%|대|명|개|곳|건|톤|배|년|월|일|기|GWh|MWh|GW|MW|kWh|kW)")


def ko_numbers(text: str) -> list[tuple[str, float]]:
    """(보여 줄 표기, 값) — 표기에는 바로 뒤 단위('원'·'달러'·'%' 등)를 붙인다."""
    text = text or ""
    out = []
    for m in KO_SPAN.finditer(text):
        span = m.group(0).strip()
        try:
            value = ko_value(span)
        except ValueError:
            continue
        unit = KO_UNIT_AFTER.match(text, m.end())
        out.append((span + (unit.group(0) if unit else ""), value))
    return out


def en_values(text: str) -> set[float]:
    values = set()
    for digits, unit in EN_NUM.findall(text or ""):
        try:
            v = _num(digits)
        except ValueError:
            continue
        values.add(v)
        if unit:
            values.add(v * MULT[unit.lower()])
    for w in WORD_RE.findall(text or ""):
        w = w.lower()
        if w in WORDS:
            values.add(float(WORDS[w]))
        if w in MONTHS:
            values.add(float(MONTHS[w]))
    return values


def _found(v: float, values: set[float]) -> bool:
    return any(abs(v - s) <= TOLERANCE * max(abs(v), abs(s)) for s in values)


def unmatched_numbers(korean: str, source: str, *, allow=()) -> list[str]:
    """한국어(AI 번역·요약)의 숫자 중 영어 원문에서 같은 값을 못 찾은 것(표기 그대로, 중복 없이)."""
    values = en_values(source) | {float(a) for a in allow}
    missing = []
    for span, v in ko_numbers(korean):
        if not _found(v, values) and span not in missing:
            missing.append(span)
    return missing
