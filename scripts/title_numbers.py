"""기사 제목의 핵심 숫자(세율·금액·규모)가 레이더 글에도 있는지 — 역추적(reverse_prior_capture)과 보도 대조(scoop_screen)가 같이 쓴다.

품목·쟁점 낱말만 겹치면 '같은 분야'일 뿐이다. 숫자까지 같으면 같은 사실일 가능성이 높고(강관 '4.20%' ↔ 관보 표 4.20%),
레이더 글 숫자와 다르면 같은 분야 다른 사실일 수 있다(도금강판 '70%대'). 레이더 글에 같은 단위 숫자가 없으면 비교 못 함.
"""
import math
import re

NUM_RX = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(%|％|조\s*원|억\s*원|조|억|MW|GW|kV|만\s*대|만\s*톤|톤)(대)?")
NUM_UNIT = {"％": "%", "조원": "억", "조": "억", "억원": "억", "만대": "만대", "만톤": "만톤"}


def numbers_in(text):
    """[(값, 단위, 원문, '대' 여부)] — 조는 억으로 바꾼다('1조2000억'은 한 값). 0은 흔해서 뺀다(휴스틸 0%)."""
    both = re.compile(r"(\d[\d,]*)\s*조\s*(\d[\d,]*)\s*억\s*원?")
    out = [(int(m.group(1).replace(",", "")) * 10000 + int(m.group(2).replace(",", "")), "억", m.group(0).strip(), False)
           for m in both.finditer(text or "")]
    t = both.sub(" ", text or "")
    for m in NUM_RX.finditer(t):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = re.sub(r"\s+", "", m.group(2))
        if unit in ("조", "조원"):
            v *= 10000
        unit = NUM_UNIT.get(unit, unit)
        if v:
            out.append((v, unit, m.group(0).strip(), bool(m.group(3))))
    return out


def same_numbers(title, text):
    """기사 제목 숫자 중 레이더 원문에도 있는 것: (제목 숫자 원문 목록, 원문에도 있는 것 목록, 비교할 숫자가 원문에 있었는지).
    원문 글에 같은 단위 숫자가 하나도 없으면 '다름'이 아니라 비교 못 함이다(11-09: 세율 없는 단서 글 ↔ 강관 4.20%)."""
    art, item = numbers_in(title), numbers_in(text)
    comparable = any(u2 == unit for _, unit, _, _ in art for _, u2, _, _ in item)
    found = []
    for v, unit, raw, band in art:
        for w, u2, _, _ in item:
            if u2 != unit:
                continue
            if (band and v <= w < v + (10 if unit == "%" else 10 ** math.floor(math.log10(v)))) or (not band and (abs(v - w) < 0.005 if unit == "%" else abs(v - w) <= max(v, w) * 0.01)):
                found.append(raw)
                break
    return [raw for _, _, raw, _ in art], found, comparable
