"""인도 DGTR 사건 페이지 일정표 — 목록의 '새 줄'이 새 조사인지, 진행 중인 조사의 절차 공지인지(11-14).

배경: 11-14 01:51 레이더가 '목록 새 줄'로 잡은 페놀 조사는 2026-03-19 개시였다. 사건 페이지에 11-13 'Updation of E-mail ID' 공지가 붙어
목록에 다시 뜬 것이다(아세톤 줄도 같은 꼴 — 탐침 231).
탐침 231(GitHub에서 로그인 없이): robots.txt는 'User-agent: * / Allow: /'(요청 간격 요구 없음). 사건 페이지에 표 하나 —
  <tr><td>1</td><td id="8740">Initiation Notification</td><td><a href="https://dgtr.gov.in/sites/default/files/2026-03/….pdf">Download (2.87 MB)</a></td><td>19/03/2026</td></tr>
  머리 줄: S.no | Timeline for completion of investigation | Details | Publish Date. 'File No.'는 검색 칸 이름일 뿐 사건 번호는 페이지에 없다.

하는 일
- 최근 WINDOW_DAYS일 인도 DGTR 목록 줄 가운데 사건 주소가 있는 것만, 한 실행 PAGE_BUDGET건·GAP초 간격으로 사건 페이지를 읽는다.
  같은 사건이 목록에 다시 뜨면(페이지에 새 문서가 붙었다는 뜻) 다시 읽는다. 못 읽으면 미확인으로 두고 다음 실행에서 다시.
- 개시 고시 날짜, 가장 최근 문서(제목·날짜), 문서 수, 갈래를 붙인다:
  new(개시 NEW_DAYS일 안) / procedural(개시가 그보다 오래됐고 가장 최근 문서가 절차 공지) / progress(그 밖 — 잠정·최종 판정 등 진행 문서).
  **등급은 바꾸지 않는다** — 화면에 무엇인지 적기만 한다(절차 공지뿐인 줄을 내릴지는 기자가 정한다).
- 'Interested parties list' PDF(가장 최근 것)를 한 실행 PDF_BUDGET개까지 읽어 'Korea'가 든 줄을 원문 그대로 남기고, 출입처 영문 이름이 있으면 따로 적는다.
  줄은 PDF에서 뽑은 글이라 표 칸이 섞일 수 있다. 계열사 이름은 원문 줄에 그대로 보일 뿐 출입처로 바꿔 적지 않는다.
- 결과는 기자 전용 저장소(trade-remedy)의 dgtrCases에만. 공개 로그엔 건수만.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from urllib.parse import urljoin

HOST = "https://www.dgtr.gov.in"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/pdf,*/*;q=0.8", "Accept-Language": "en,ko;q=0.8"}
PAGES = ("in-dgtr", "in-dgtr-cvd")
CASE_URL = re.compile(r"^https://(?:www\.)?dgtr\.gov\.in/en/[a-z-]+-cases/[^/?#]+$")
WINDOW_DAYS = 45
KEEP_DAYS = 200
PAGE_BUDGET = 6
PDF_BUDGET = 3
MAX_PDF_BYTES = 6_000_000
PDF_PAGES = 12
GAP = 1.5
NEW_DAYS = 30
MAX_LINES = 8
# 절차 공지: 조사 내용이 아니라 일정·연락처·명단·질문서 기한 같은 것
PROCEDURAL = re.compile(r"e-?\s?mail|extension|corrigendum|\bPUC\b|\bPCN\b|interested\s+part|address|contact|clarification|schedule|questionnaire", re.I)
# 조사 진행 문서: 절차 낱말이 같이 있어도 이쪽이 이긴다('Corrigendum to Final Findings')
SUBSTANTIVE = re.compile(r"preliminary|provisional|disclosure|final\s+finding|findings|recommend|terminat|withdraw|essential\s+facts|oral\s+hearing|public\s+hearing|"
                         r"customs\s+notification|sunset|review\s+initiat", re.I)
INITIATION = re.compile(r"initiation", re.I)
PARTIES = re.compile(r"interested\s+part", re.I)
KOREA = re.compile(r"\bKorea\b|\bROK\b", re.I)


def plain(raw):
    import html
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()


def iso(text):
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", text or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def parse_case(page):
    """사건 페이지 일정표 → [{title, date(YYYY-MM-DD), url}] (페이지 순서 그대로). 날짜가 없는 줄은 뺀다."""
    out = []
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", page or "", re.I):
        cells = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row, re.I)
        if len(cells) < 3:
            continue
        day = iso(plain(cells[-1]))
        title = plain(cells[1])
        if not day or not title:
            continue
        href = re.search(r'href="([^"]+)"', row)
        out.append({"title": title[:160], "date": day, **({"url": urljoin(HOST, href.group(1))} if href else {})})
    return out


def kind_of(initiated, latest, today):
    if initiated and (today - dt.date.fromisoformat(initiated)).days <= NEW_DAYS:
        return "new"
    title = (latest or {}).get("title") or ""
    if initiated and PROCEDURAL.search(title) and not SUBSTANTIVE.search(title):
        return "procedural"
    return "progress"


def summarize(rows, today):
    """일정표 줄 → {initiated, latest{title,date}, steps, kind, partiesUrl?}. 줄이 없으면 None."""
    if not rows:
        return None
    inits = sorted(r["date"] for r in rows if INITIATION.search(r["title"]))
    latest = max(enumerate(rows), key=lambda x: (x[1]["date"], x[0]))[1]
    parties = [r for r in rows if PARTIES.search(r["title"]) and r.get("url")]
    initiated = inits[0] if inits else None
    return {"initiated": initiated, "latest": {"title": latest["title"], "date": latest["date"]}, "steps": len(rows),
            "kind": kind_of(initiated, latest, today),
            **({"partiesUrl": max(parties, key=lambda r: r["date"])["url"], "partiesDate": max(parties, key=lambda r: r["date"])["date"]} if parties else {})}


def korea_lines(text):
    """PDF에서 뽑은 글 → 'Korea'가 든 줄(원문 그대로, 최대 MAX_LINES줄·줄마다 180자). 짧게 끊긴 줄은 앞 줄과 잇는다."""
    lines = [re.sub(r"\s+", " ", x).strip() for x in str(text or "").splitlines()]
    lines = [x for x in lines if x]
    out = []
    for i, x in enumerate(lines):
        if not KOREA.search(x):
            continue
        y = f"{lines[i - 1]} {x}" if len(x) < 40 and i and not KOREA.search(lines[i - 1]) else x      # 칸이 다음 줄로 끊긴 것만 앞 줄과 잇는다
        y = y[:180]
        if y not in out:
            out.append(y)
        if len(out) >= MAX_LINES:
            break
    return out


def read_parties(url, *, get):
    import tra_file_watch as tra
    r = get(url, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    data = r.content
    if len(data) > MAX_PDF_BYTES:
        raise RuntimeError("PDF가 큼")
    pages, text = tra.pdf_text(data, limit=PDF_PAGES)
    return {"pages": pages, "chars": len(text), "koreaLines": korea_lines(text), "beat": tra.companies_in(text)}


def attach(doc, previous, now, *, get, sleep=time.sleep):
    """doc['dgtrCases'][사건 주소] = {status, checkedAt, initiated, latest, steps, kind, parties?}. 반환: 공개 로그용 건수 dict."""
    old = (previous or {}).get("dgtrCases") or {}
    stamp, today = now.isoformat(timespec="seconds"), now.date()
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    store = {u: dict(v) for u, v in old.items() if isinstance(v, dict) and str(v.get("checkedAt") or "") >= keep_from}
    since = (now - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    newest = {}
    for e in doc.get("events") or []:
        u = str(e.get("url") or "")
        if e.get("pageId") in PAGES and CASE_URL.match(u) and str(e.get("detectedAt") or "") >= since:
            newest[u] = max(newest.get(u, ""), str(e.get("detectedAt")))
    # 다시 읽을 것: 처음 보는 사건, 못 읽었던 사건, 읽은 뒤 목록에 다시 뜬 사건(새 문서가 붙었다는 뜻). 새로 뜬 것부터
    todo = [u for u, seen in sorted(newest.items(), key=lambda x: x[1], reverse=True)
            if u not in store or store[u].get("status") != "ok" or seen > str(store[u].get("checkedAt") or "")]
    read = failed = pdfs = 0
    for u in todo[:PAGE_BUDGET]:
        sleep(GAP)
        prev = store.get(u) or {}
        try:
            r = get(u, headers=HEADERS, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            summary = summarize(parse_case(r.text), today)
            if not summary:
                raise RuntimeError("일정표 줄 없음(형식 변경 의심)")
            keep_parties = {"parties": prev["parties"]} if prev.get("parties") and prev["parties"].get("url") == summary.get("partiesUrl") else {}
            store[u] = {"status": "ok", "checkedAt": stamp, **summary, **keep_parties}
            read += 1
        except Exception as e:  # noqa: BLE001 — 한 사건 실패가 다른 사건을 막지 않는다
            store[u] = {**{k: v for k, v in prev.items() if k not in ("status", "error")}, "status": "failed", "error": str(e)[:60] or type(e).__name__,
                        "checkedAt": prev.get("checkedAt") or "", "triedAt": stamp}
            failed += 1
    # 이해관계자 명단 PDF: 아직 안 읽은 것만(새로 뜬 사건부터)
    def wants_pdf(u):
        c = store.get(u) or {}
        p = c.get("parties") or {}
        return c.get("status") == "ok" and c.get("partiesUrl") and (not p or (p.get("status") == "failed" and (p.get("tries") or 1) < 3))

    for u in sorted((u for u in newest if wants_pdf(u)), key=lambda u: newest[u], reverse=True)[:PDF_BUDGET]:
        sleep(GAP)
        c = store[u]
        tries = ((c.get("parties") or {}).get("tries") or 0) + 1
        try:
            c["parties"] = {"url": c["partiesUrl"], "date": c.get("partiesDate"), "status": "ok", **read_parties(c["partiesUrl"], get=get)}
        except Exception as e:  # noqa: BLE001
            c["parties"] = {"url": c["partiesUrl"], "date": c.get("partiesDate"), "status": "failed", "error": str(e)[:60] or type(e).__name__, "tries": tries}
        pdfs += 1
    doc["dgtrCases"] = store
    kinds = {}
    for u in newest:
        k = store.get(u, {}).get("kind") if store.get(u, {}).get("status") == "ok" else "미확인"
        kinds[k] = kinds.get(k, 0) + 1
    return {"cases": len(newest), "read": read, "failed": failed, "waiting": max(0, len(todo) - PAGE_BUDGET), "pdfs": pdfs, "kinds": kinds,
            "korea": sum(1 for u in newest if (store.get(u, {}).get("parties") or {}).get("koreaLines")),
            "beat": sum(1 for u in newest if (store.get(u, {}).get("parties") or {}).get("beat"))}
