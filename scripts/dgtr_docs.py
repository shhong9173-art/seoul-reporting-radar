"""인도 DGTR 판정문(Final·Preliminary Findings)과 개시 고시 PDF에서 기자가 먼저 볼 대목을 뽑는다(11-14).

배경: 11-06(금) 흄드실리카 일몰재심 'Final Findings'가 사건 페이지에 붙었는데 레이더는 "목록에 새 줄"이라고만 했다. 판정문을 열어야 알 수 있던 것 —
목록 줄은 'China PR & Korea RP'인데 이번 재심은 중국만 대상이고 한국은 재심을 개시하지 않았다(판정문 7항).

탐침 234·235(GitHub에서 공개 PDF):
- 판정문(흄드실리카, 52쪽·773KB·글 14.7만 자, 글자 PDF): 1쪽에 'FINAL FINDINGS / Case No. AD (SSR)-05/2026 / Sunset review investigation concerning …'.
  본문은 번호 문단('7. Anti-dumping duties are in force …'), 대문자 소제목('N. RECOMMENDATION'), 끝에 'Duty Table'.
  세율 표는 칸이 줄마다 끊긴다: '1 2811220 ⏎ 0 ⏎ Untreated ⏎ Fumed ⏎ Silica ⏎ China ⏎ PR ⏎ … ⏎ Material Co., ⏎ Ltd. ⏎ 1,296 MT USD' — 줄 끝의 '금액 단위 통화'로 한 줄을 닫는다.
  쪽마다 머리·꼬리 줄('F. No. 7/09/2026-DGTR – Final Findings Non-confidential', '… 51 | P a g e', '7/09/2026-DGTR I/145225/2026')이 끼어 있다.
- 개시 고시(IPA·TDI 2차 일몰재심, 8쪽·3.4MB): **스캔 그림이라 글자가 0자**. tesseract(영문) 200dpi로 8쪽 21초, 쪽당 2,500~3,000자.
  소제목 'A. Product under consideration … C. Domestic industry & standing … E. Period of investigation … K. Time limit'.
  신청인은 1항 '… (hereinafter referred to as the ‘applicant’) has filed an application …'. 한국 수출자 이름은 고시에 없다
  ('The known producers/exporters … are being informed separately').

원칙
- 뽑은 대목은 원문 그대로다(줄만 이어 붙임). 판정 결과를 해석해 적지 않는다 — 세율·대상국은 기자가 원문 PDF로 확인한다.
- 글자 인식본은 숫자·날짜가 틀리게 읽힐 수 있다('Ist April') — 화면에 '글자 인식'이라고 적는다.
- 글자 인식 도구가 없거나 시간이 모자라면 못 읽은 것으로 남긴다(0건이 아니라 미확인).
"""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import time

DOC_VERSION = 2         # 2: 사건 설명 줄 끊는 자리, 권고의 절차 문장 빼기
MAX_DOC_BYTES = 20_000_000
MAX_PAGES = 220
SCAN_CHARS = 400        # 글자가 이보다 적으면 스캔본으로 본다
OCR_DPI = 200
OCR_BUDGET = 120        # 초(문서당)
OCR_HEAD, OCR_TAIL = 3, 10   # 스캔 판정문: 앞 3쪽(사건·대상)과 끝 10쪽(권고·세율 표)만 읽는다
OCR_INIT_PAGES = 12
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "application/pdf,*/*;q=0.8", "Accept-Language": "en,ko;q=0.8"}

KOREA = re.compile(r"\bKorea\b|\bROK\b", re.I)
# 쪽 머리·꼬리 줄
PAGE_NOISE = re.compile(r"^(?:F\.\s*No\.?\s*[\d/ ]+-\s*DGTR\s*[–-].{0,60}$|DGTR, Department of Commerce.{0,60}P\s*a\s*g\s*e\s*$|\d+/\d+/\d{4}-DGTR\s+I/\d+/\d{4}$|"
                        r"Page \d+ of \d+$|\d+\s*\|\s*P\s*a\s*g\s*e$)", re.I)
PARA = re.compile(r"^(\d{1,3})\.\s+\S")
SECTION = re.compile(r"^([A-Z]{1,2})\.\s+([A-Za-z][A-Za-z ,&/()'’-]{3,80})$")
TITLE = re.compile(r"^(?:Subject\s*:|(?:FINAL|PRELIMINARY|PROVISIONAL)\s+FINDINGS?\b|INITIATION NOTIFICATION\b|NOTIFICATION$)", re.I)
HEAD_SKIP = re.compile(r"^(?:Case No|SETU|F\.\s*No|Dated?\b|\(.*\)$|To be published|Government of India|Ministry of|Department of|Directorate General|\d+(?:st|nd|rd|th)? Floor|New Delhi)", re.I)
CASE_NO = re.compile(r"Case No\.?\s*[:\-–]?\s*([A-Z]{2,4}\s*\(?[A-Z-]{0,6}\)?\s*[-–]\s*\d{1,3}\s*/\s*\d{4})")
DECISIVE = re.compile(r"not initiated|terminat|de ?minimis|negligible|continu|recommend|\bduty\b|\bduties\b|margin|undertaking|exclu|revok|withdraw", re.I)
ROW_END = re.compile(r"(?:^|\s)(?:\d[\d,]*(?:\.\d+)?|NIL)\s+[A-Za-z.]{1,8}\s+(?:USD|US\$|US Dollars?|INR|Rs\.?)\s*$|\d+(?:\.\d+)?\s*%\s*$", re.I)
RECO = re.compile(r"recommend|arrived at the conclusion|conclud|terminat|revok|withdraw|impos|is required|not required", re.I)
RECO_BOILER = re.compile(r"duly notified|adequate opportunity|conducted in accordance|proceedings were conducted", re.I)
COLUMN_NUMBERS = re.compile(r"^1\s+2\s+3\s+4\s+5(?:\s+\d+)*$")
APPLICANT = re.compile(r"referred to as\s+(?:the\s+)?[‘’'“”\"`]*\s*(?:applicants?|petitioners?)", re.I)


def lines_of(text):
    out = []
    for x in str(text or "").splitlines():
        y = re.sub(r"\s+", " ", x).strip()
        if y and not PAGE_NOISE.match(y):
            out.append(y)
    return out


def clip(text, n):
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    return t if len(t) <= n else t[:n].rstrip() + "…"


def numeric_heavy(text):
    t = re.sub(r"\s", "", text)
    return len(t) >= 8 and sum(c.isdigit() for c in t) / len(t) > 0.3


def blocks(lines):
    """줄 → [{kind: head|para|text|table, no?, title?, text}] — 번호 문단과 대문자 소제목으로 나눈다. 'Duty Table' 뒤 줄은 table로 따로 둔다."""
    out, last, in_table = [], 0, False
    for x in lines:
        s, p = SECTION.match(x), PARA.match(x)
        n = int(p.group(1)) if p else 0
        if re.match(r"^duty table\b", x, re.I):
            out.append({"kind": "head", "title": "Duty Table", "text": x})
            out.append({"kind": "table", "text": ""})
            in_table = True
        elif s and len(x) < 90:
            out.append({"kind": "head", "title": s.group(2).strip(), "text": x})
            in_table = False
        elif p and (n <= 3 if not last else last < n <= last + 200):    # 번호가 커질 때만(문단 속 '1. 2. 3.' 목록에 끊기지 않게). 스캔본은 앞·끝 쪽만 읽어 번호가 건너뛴다
            out.append({"kind": "para", "no": n, "text": x})
            last, in_table = n, False
        elif in_table:
            out[-1]["text"] += " " + x
        elif numeric_heavy(x):                                          # 본문 사이 통계 표의 숫자 줄('Korea RP MT 56 71 104 82')은 문단에 섞지 않는다
            continue
        elif out and out[-1]["kind"] != "head":
            out[-1]["text"] += " " + x
        else:
            out.append({"kind": "text", "text": x})
    return out


def subject_of(lines):
    """문서 머리의 사건 설명 줄('Sunset review investigation concerning … from China PR').
    11-14 운영: 판정문 1항이 번호 없이 'F. No. 7/09/2026-DGTR: Having regard to …'로 시작해 설명 줄 뒤에 본문이 딸려 왔다 — 설명 줄이 시작된 뒤 머리 꼴 줄이 다시 나오면 거기서 끊는다."""
    first = next((i for i, x in enumerate(lines[:80]) if (PARA.match(x) and int(PARA.match(x).group(1)) == 1) or SECTION.match(x)), min(len(lines), 40))
    start = max((i for i, x in enumerate(lines[:first]) if TITLE.match(x)), default=None)
    if start is None:
        return ""
    out = [re.sub(r"^Subject\s*:\s*", "", lines[start], flags=re.I)] if re.match(r"^Subject\s*:", lines[start], re.I) else []
    for x in lines[start + 1:first]:
        if TITLE.match(x):
            continue
        if HEAD_SKIP.match(x) or re.search(r"Having regards? to", x):
            if out:
                break
            continue
        out.append(x)
        if len(out) >= 8:
            break
    return clip(" ".join(out), 420)


def sentences_with(text, rx, limit, prefer=None):
    """rx가 든 문장만 이어 붙인다(원문). 넘치면 prefer가 든 문장부터, 한 문장이 너무 길면 rx 둘레만."""
    parts = [x for x in re.split(r"(?<=[.;])\s+(?=[A-Z(“\"])", text) if x]
    hit = [x for x in parts if rx.search(x)]
    if not hit:
        return ""
    if sum(len(x) + 1 for x in hit) > limit and prefer:
        hit.sort(key=lambda x: 0 if prefer.search(x) else 1)
    out, left = [], limit
    for x in hit:
        if len(x) <= left:
            out.append(x)
            left -= len(x) + 1
        elif not out:
            m = list(rx.finditer(x))[-1]
            a = max(0, m.end() + 40 - limit)
            out.append(("…" if a else "") + x[a:a + limit].strip() + ("…" if a + limit < len(x) else ""))
            break
        else:
            break
    return " ".join(out)


def korea_paras(blks, subject, limit=4):
    """'Korea'가 든 문단에서 그 문장만(원문). 결정에 닿는 낱말이 있는 문단 먼저."""
    found = []
    for b in blks:
        if b["kind"] in ("head", "table") or not KOREA.search(b["text"]):
            continue
        s = sentences_with(b["text"], KOREA, 420, DECISIVE)
        if not s or numeric_heavy(s) or (subject and s[:80] in subject):
            continue
        s = re.sub(r"^\d{1,3}\.\s+", "", s)
        s = f"({b['no']}항) {s}" if b["kind"] == "para" else s
        if s not in [x for _, x in found]:
            found.append((0 if DECISIVE.search(s) else 1, s))
    found.sort(key=lambda x: x[0])
    return [s for _, s in found[:limit]], len(found)


def recommendation(blks):
    """마지막 'RECOMMENDATION' 소제목 아래 문단(세율 표 앞까지)."""
    idx = max((i for i, b in enumerate(blks) if b["kind"] == "head" and re.match(r"recommendation", b["title"], re.I)), default=None)
    if idx is None:
        return ""
    out = []
    for b in blks[idx + 1:]:
        if b["kind"] != "para":
            break
        out.append(re.sub(r"^\d{1,3}\.\s+", "", b["text"]))
        if len(" ".join(out)) > 1600:
            break
    # 절차 설명 문단(모든 당사자에게 기회를 줬다)보다 결론 문장을 앞에
    # 절차 설명 문장(모든 당사자에게 기회를 줬다 — 11-14 운영에서 이 문장이 권고 맨 앞에 나왔다)은 빼고 결론 문장만
    parts = [x for x in re.split(r"(?<=[.;])\s+(?=[A-Z(“\"])", " ".join(out)) if x and not RECO_BOILER.search(x)]
    text = " ".join(parts)
    return sentences_with(text, RECO, 900) or clip(text, 900)


def duty_rows(lines):
    """끝의 'Duty Table' 줄들을 '금액 단위 통화'로 닫아 한 줄씩 묶는다. 표가 없으면 []."""
    idx = max((i for i, x in enumerate(lines) if re.match(r"^duty table\b", x, re.I)), default=None)
    if idx is None:
        return []
    body = lines[idx + 1:idx + 500]
    col = next((i for i, x in enumerate(body[:40]) if COLUMN_NUMBERS.match(x)), None)
    body = body[col + 1:] if col is not None else body
    rows, cur = [], []
    for x in body:
        p = PARA.match(x)
        if p and int(p.group(1)) >= 10 and not cur:      # 표 뒤 본문 문단('165. An exporter …')
            break
        cur.append(x)
        if ROW_END.search(x):
            rows.append(clip(" ".join(cur), 220))
            cur = []
        elif len(cur) > 40:                               # 표가 아닌 글로 넘어갔다
            break
    return rows


def beat_lines(blks, beat_rx, limit=3):
    names, out = [], []
    for name, rx in beat_rx:
        r = re.compile(rx, re.I)
        for b in blks:
            if b["kind"] not in ("head", "table") and r.search(b["text"]):
                if name not in names:
                    names.append(name)
                s = sentences_with(b["text"], r, 300)
                if s and s not in out and len(out) < limit:
                    out.append(s)
                break
    return names, out


def findings_from_pages(texts, beat_rx, *, ocr=False, pages=None):
    lines = lines_of("\n".join(texts))
    blks = blocks(lines)
    subject = subject_of(lines)
    m = CASE_NO.search(" ".join(lines[:40]))
    korea, total = korea_paras(blks, subject)
    rows = duty_rows(lines)
    names, blines = beat_lines(blks, beat_rx)
    return {"v": DOC_VERSION, "pages": pages or len(texts), "chars": sum(len(t) for t in texts), "ocr": bool(ocr),
            "subject": subject, **({"caseNo": re.sub(r"\s+", " ", m.group(1))} if m else {}),
            "korea": korea, "koreaTotal": total, "recommendation": recommendation(blks),
            "duty": {"rows": len(rows), "korea": [r for r in rows if KOREA.search(r)][:6], "sample": rows[:3]},
            "beat": names, "beatLines": blines}


def first_para_under(blks, title_rx):
    for i, b in enumerate(blks):
        if b["kind"] == "head" and title_rx.search(b["title"]):
            for c in blks[i + 1:i + 4]:
                if c["kind"] == "head":
                    break
                return c["text"]
    return ""


def initiation_from_pages(texts, beat_rx, *, ocr=False, pages=None):
    lines = lines_of("\n".join(texts))
    blks = blocks(lines)
    whole = " ".join(b["text"] for b in blks if b["kind"] not in ("head", "table"))
    applicant = ""
    for blk in blks:                                                   # 신청인 이름은 '(hereinafter referred to as the ‘applicant’)' 바로 앞에 있다
        m = APPLICANT.search(blk["text"]) if blk["kind"] != "head" else None
        if m:
            a = max(0, m.start() - 200)
            seg = blk["text"][a:m.end() + 200]
            applicant = clip(("…" + seg[seg.find(" ") + 1:]) if a else seg, 460)
            break
    poi = first_para_under(blks, re.compile(r"period of investigation", re.I)) or sentences_with(whole, re.compile(r"period of investigation.{0,90}\d{4}", re.I), 360)
    c = CASE_NO.search(" ".join(lines[:40]))
    d = re.search(r"Dated?\s*:?\s*([0-3]?\d[./-][01]?\d[./-]20\d{2}|[0-3]?\d(?:st|nd|rd|th)?\s+[A-Z][a-z]+,?\s+20\d{2})", " ".join(lines[:30]))
    names, blines = beat_lines(blks, beat_rx)
    return {"v": DOC_VERSION, "pages": pages or len(texts), "chars": sum(len(t) for t in texts), "ocr": bool(ocr),
            "subject": subject_of(lines), **({"caseNo": re.sub(r"\s+", " ", c.group(1))} if c else {}), **({"dated": d.group(1)} if d else {}),
            "applicant": applicant, "poi": clip(poi, 360),
            "industry": clip(first_para_under(blks, re.compile(r"domestic industry", re.I)), 420),
            "timeLimit": clip(first_para_under(blks, re.compile(r"time limit", re.I)), 300),
            "beat": names, "beatLines": blines}


# ----------------------------------------------------------------------------- PDF 읽기
def pdf_pages(data, limit=MAX_PAGES):
    import pypdf
    pdf = pypdf.PdfReader(io.BytesIO(data))
    return len(pdf.pages), [(p.extract_text() or "") for p in pdf.pages[:limit]]


def ocr_pages(data, ranges, *, run=subprocess.run, which=shutil.which, budget=OCR_BUDGET, clock=time.monotonic):
    """(쪽 글 목록, 오류). ranges: [(첫 쪽, 끝 쪽)] — pdftoppm으로 쪽 그림을 만들고 tesseract로 읽는다."""
    if not (which("pdftoppm") and which("tesseract")):
        return [], "글자 인식 도구 없음"
    started, texts = clock(), []
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "r.pdf")
        with open(pdf, "wb") as f:
            f.write(data)
        for k, (first, last) in enumerate(ranges):
            left = budget - (clock() - started)
            if left <= 5:
                return texts, f"글자 인식 시간 상한({len(texts)}쪽까지)"
            r = run(["pdftoppm", "-r", str(OCR_DPI), "-gray", "-png", "-f", str(first), "-l", str(last), pdf, os.path.join(d, f"pg{k}")], capture_output=True, timeout=left)
            if r.returncode != 0:
                return texts, "쪽 그림 변환 실패"
            for f in sorted(x for x in os.listdir(d) if x.startswith(f"pg{k}")):
                left = budget - (clock() - started)
                if left <= 5:
                    return texts, f"글자 인식 시간 상한({len(texts)}쪽까지)"
                out = run(["tesseract", os.path.join(d, f), "-", "--psm", "6"], capture_output=True, text=True, timeout=left)
                texts.append(out.stdout or "")
    return texts, None


def fetch(url, *, get):
    r = get(url, headers=HEADERS, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    if len(r.content) > MAX_DOC_BYTES:
        raise RuntimeError("PDF가 큼")
    return r.content


def page_texts(data, kind, *, ocr=ocr_pages):
    """(쪽 수, 쪽 글 목록, 글자 인식 여부). 글자 PDF면 그대로, 스캔이면 글자 인식(판정문은 앞·끝 쪽만)."""
    n, texts = pdf_pages(data)
    if sum(len(t) for t in texts) >= SCAN_CHARS:
        return n, texts, False
    ranges = [(1, min(n, OCR_INIT_PAGES))] if kind == "initiation" or n <= OCR_HEAD + OCR_TAIL else [(1, OCR_HEAD), (n - OCR_TAIL + 1, n)]
    got, err = ocr(data, ranges)
    if sum(len(t) for t in got) < SCAN_CHARS:
        raise RuntimeError(f"스캔 PDF — {err or '글자 인식 결과 없음'}")
    return n, got, True


def read_findings(url, *, get, beat_rx, ocr=ocr_pages):
    n, texts, scanned = page_texts(fetch(url, get=get), "findings", ocr=ocr)
    return findings_from_pages(texts, beat_rx, ocr=scanned, pages=n)


def read_initiation(url, *, get, beat_rx, ocr=ocr_pages):
    n, texts, scanned = page_texts(fetch(url, get=get), "initiation", ocr=ocr)
    return initiation_from_pages(texts, beat_rx, ocr=scanned, pages=n)
