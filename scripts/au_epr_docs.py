"""호주 ATRC 사건 공개기록(EPR) 문서의 본문 대목 — 기자 컴퓨터가 올린 PDF를 받아 글자를 풀고 한국·출입처 대목을 남긴다(기자 11-15 02:54).

industry.gov.au는 PDF도 GitHub에서 막힌다(탐침 241: 읽기 시간 초과). 그래서:
1. au_epr_cases.py가 직접 출입처 이름이 든 문서 가운데 본문을 못 읽은 것을 구역의 `want`에 적는다(4건까지).
2. 기자 컴퓨터 수집(scripts/aside/kr_browser_collect.js 토막 6·7)이 올리기 응답의 `want`를 받아 그 PDF를 내려받고 레이더의 /upload/browser-file로
   나눠 올린다(파일 2MB까지, 칸 넷).
3. 이 모듈이 무역구제 감시 끝에 레이더에서 파일을 받아(/ingest/browser-files) pdftotext로 글자를 풀고, 한국·출입처 이름이 든 문장 가운데
   쟁점 낱말(특별시장상황·덤핑 마진·종결 등)이 든 것을 먼저 골라 구역의 `pdf`에 남긴 뒤 칸을 비운다.

공개기록 문서는 당사자 의견서가 대부분이다 — 대목은 낸 쪽의 주장이지 조사기관 판단이 아니다. 문장을 그대로 옮기고 해석하지 않는다.
기준선(처음 읽을 때 이미 있던) 문서의 본문은 화면에만 붙이고 알리지 않는다. 기준선 뒤에 새로 잡힌 문서의 본문을 읽으면 B로 한 번 알린다.
공개 로그에는 건수만.
"""
from __future__ import annotations

import base64
import datetime as dt
import re
import subprocess
import tempfile

import au_epr_cases

WORKER = "https://seoul-reporting-radar.shhong9173.workers.dev"
MAX_BYTES = 2_200_000
EXCERPTS = 6
EXCERPT_CHARS = 320
SCAN_CHARS = 200          # 글자가 이보다 적으면 스캔본으로 본다(글자 인식은 하지 않는다)
KOREA = re.compile(r"\bKorean?\b|\bROK\b", re.I)
ISSUE = re.compile(r"particular market situation|\bPMS\b|dumping margin|margin of dumping|subsid|negligible|terminat|undersell|undercut|injur|normal value|"
                   r"constructed|benchmark|hot[- ]rolled coil|\bHRC\b|export price|not dumped|\d(?:\.\d+)?\s?(?:%|per cent)", re.I)
MARGIN = re.compile(r"(?:dumping margins?|margins? of dumping|subsidy margins?|margins? of subsid\w+)[^.;]{0,90}?(?:-|negative )?\d{1,3}(?:\.\d+)?\s?(?:%|per cent)"
                    r"|(?:-|negative )?\d{1,3}(?:\.\d+)?\s?(?:%|per cent)[^.;]{0,40}?(?:dumping margins?|subsidy margins?)", re.I)


def pdf_text(data):
    """(쪽 수, 글자). pdftotext가 없거나 실패하면 예외."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        r = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"pdftotext {r.returncode}")
    text = r.stdout.decode("utf-8", "replace")
    return text.count("\f") + (0 if text.endswith("\f") or not text else 1), text


def firm_rx():
    import trade_remedy_watch
    return re.compile("|".join(f"(?:{pat})" for _, pat in trade_remedy_watch.BEAT_NAMES), re.I)


def sentences(text):
    flat = re.sub(r"\s+", " ", re.sub(r"-\n\s*", "", text.replace("\f", "\n")))
    return [x.strip() for x in re.split(r"(?<=[.;:?!])\s+(?=[A-Z(“\"‘'\d])", flat) if len(x.strip()) >= 25]


def excerpts(text, rx=None):
    """한국·출입처 이름이 든 문장 → {'excerpts': [...], 'margins': [...], 'hits': n}. 쟁점 낱말이 든 문장을 먼저, 그다음 글 순서."""
    rx = rx or firm_rx()
    scored = []
    for i, snt in enumerate(sentences(text)):
        if len(snt) > 900 or snt.count(".....") or not (KOREA.search(snt) or rx.search(snt)):
            continue
        scored.append((-len(set(m.group(0).lower() for m in ISSUE.finditer(snt))) - (1 if rx.search(snt) else 0), i, snt))
    top = sorted(sorted(scored)[:EXCERPTS], key=lambda x: x[1])
    out, seen = [], set()
    for _, _, snt in top:
        key = snt[:80].lower()
        if key not in seen:
            seen.add(key)
            out.append(snt if len(snt) <= EXCERPT_CHARS else snt[:EXCERPT_CHARS - 1].rsplit(" ", 1)[0] + " …")
    margins = []
    for m in MARGIN.finditer(re.sub(r"\s+", " ", text)):
        snip = m.group(0).strip()[:160]
        if snip.lower() not in {x.lower() for x in margins}:
            margins.append(snip)
        if len(margins) >= 5:
            break
    return {"excerpts": out, "margins": margins, "hits": len(scored)}


def _headers(token):
    import private_store
    return private_store._headers(token)


def read_files(section, token, now, *, events=None, get=None, post=None, extract=pdf_text):
    """레이더에 올라온 PDF를 읽어 section['pdf']에 대목을 남기고 칸을 비운다. 돌려줌: 건수 {waiting, read, failed, scan, cleared, events}."""
    import requests
    get, post = get or requests.get, post or requests.post
    counts = {"waiting": 0, "read": 0, "failed": 0, "scan": 0, "cleared": 0, "events": 0}
    if not isinstance(section, dict) or not isinstance(section.get("cases"), dict):
        return counts
    stamp = now.isoformat(timespec="seconds")
    r = get(f"{WORKER}/ingest/browser-files", headers=_headers(token), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"파일 목록 HTTP {r.status_code}")
    files = [x for x in (r.json() or {}).get("files") or [] if isinstance(x, dict)]
    docs = {au_epr_cases.doc_key(no, d): (no, c, d) for no, c in section["cases"].items() for d in c.get("docs") or []}
    pdf = section.setdefault("pdf", {})
    rx, done = firm_rx(), []
    baseline = str(section.get("baselineAt") or "")[:10]
    for f in files:
        key, slot = str(f.get("key") or ""), str(f.get("slot") or "")
        if not f.get("complete"):
            counts["waiting"] += 1
            continue
        done.append(slot)
        if key not in docs:      # 문서 줄에 없는 파일: 읽지 않고 칸만 비운다
            continue
        no, case, d = docs[key]
        prev = pdf.get(key) or {}
        try:
            parts = []
            for i in range(int(f.get("parts") or 0)):
                p = get(f"{WORKER}/ingest/browser-files", params={"slot": slot, "part": i}, headers=_headers(token), timeout=60)
                if p.status_code != 200:
                    raise RuntimeError(f"조각 HTTP {p.status_code}")
                parts.append(str((p.json() or {}).get("b64") or ""))
            data = base64.b64decode("".join(parts), validate=True)
            if not data.startswith(b"%PDF-") or len(data) > MAX_BYTES:
                raise RuntimeError("PDF 아님" if not data.startswith(b"%PDF-") else "파일이 큼")
            pages, text = extract(data)
        except Exception as e:  # noqa: BLE001 — 다음에 다시 받아 달라고 한다(PDF_TRIES번까지)
            pdf[key] = {"v": au_epr_cases.PDF_VERSION, "date": d.get("date"), "tries": int(prev.get("tries") or 0) + 1, "error": str(e)[:60] or type(e).__name__}
            counts["failed"] += 1
            continue
        chars = len(re.sub(r"\s+", "", text))
        got = excerpts(text, rx) if chars >= SCAN_CHARS else {"excerpts": [], "margins": [], "hits": 0}
        pdf[key] = {"v": au_epr_cases.PDF_VERSION, "readAt": stamp, "date": d.get("date"), "pages": pages, "chars": chars, **got,
                    **({"scan": True} if chars < SCAN_CHARS else {})}
        counts["read"] += 1
        counts["scan"] += 1 if chars < SCAN_CHARS else 0
        # 기준선 뒤에 새로 잡힌 문서의 본문: B로 한 번(기준선 문서는 화면에만)
        if events is not None and got["excerpts"] and (d.get("date") or "") >= baseline and str(case.get("firstSeen") or "")[:10] <= (d.get("date") or ""):
            events.insert(0, {"id": f"{au_epr_cases.PAGE_ID}:{no}:text:{d['no']}", "pageId": au_epr_cases.PAGE_ID, "country": "호주", "label": au_epr_cases.label_of(no, case),
                              "text": (f"본문 읽음 — EPR {d['no']}번 {d.get('type')} 「{d.get('title')}」({d.get('date')}, {pages}쪽): 한국·출입처 이름이 든 문장 {got['hits']}개. "
                                       f"첫 대목: \"{got['excerpts'][0]}\"")[:700],
                              "url": d.get("url") or case.get("url"), "detectedAt": stamp, "tier": "B", **({"companies": d["companies"]} if d.get("companies") else {})})
            counts["events"] += 1
    if done:
        c = post(f"{WORKER}/ingest/browser-files", json={"done": done}, headers=_headers(token), timeout=30)
        counts["cleared"] = len(done) if getattr(c, "status_code", 0) == 200 else 0
    section["want"] = au_epr_cases.want_list(section["cases"], pdf, now)
    return counts
