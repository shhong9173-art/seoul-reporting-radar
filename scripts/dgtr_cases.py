"""인도 DGTR 사건 페이지 일정표 — 목록의 '새 줄'이 새 조사인지, 진행 중인 조사의 절차 공지인지(11-14).

배경: 11-14 01:51 레이더가 '목록 새 줄'로 잡은 페놀 조사는 2026-03-19 개시였다. 사건 페이지에 11-13 'Updation of E-mail ID' 공지가 붙어
목록에 다시 뜬 것이다(아세톤 줄도 같은 꼴 — 탐침 231).
탐침 231(GitHub에서 로그인 없이): robots.txt는 'User-agent: * / Allow: /'(요청 간격 요구 없음). 사건 페이지에 표 하나 —
  <tr><td>1</td><td id="8740">Initiation Notification</td><td><a href="https://dgtr.gov.in/sites/default/files/2026-03/….pdf">Download (2.87 MB)</a></td><td>19/03/2026</td></tr>
  머리 줄: S.no | Timeline for completion of investigation | Details | Publish Date. 'File No.'는 검색 칸 이름일 뿐 사건 번호는 페이지에 없다.

하는 일
- 최근 WINDOW_DAYS일 인도 DGTR 목록 줄 가운데 사건 주소가 있는 것만, 한 실행 PAGE_BUDGET건·GAP초 간격으로 사건 페이지를 읽는다.
  같은 사건이 목록에 다시 뜨면(페이지에 새 문서가 붙었다는 뜻) 다시 읽는다. 못 읽으면 미확인으로 두고 다음 실행에서 다시.
- 이번 절차의 개시 고시(날짜·제목), 가장 최근 문서(제목·날짜), 문서 수, 갈래를 붙인다:
  new(개시 NEW_DAYS일 안) / procedural(개시가 그보다 오래됐고 가장 최근 문서가 절차 공지) / progress(그 밖 — 잠정·최종 판정 등 진행 문서).
  **등급은 바꾸지 않는다** — 화면에 무엇인지 적기만 한다(절차 공지뿐인 줄을 내릴지는 기자가 정한다).
- 탐침 232: 사건 페이지 하나에 원조사·일몰재심·우회조사가 차례로 쌓인다(TDI: Initiation 2016-10-05 → … → 'Initiation Notification-2nd SSR' 2026-09-30).
  그래서 '개시'는 **가장 최근 개시 고시**(이번 절차)이고, 첫 조사 개시일은 따로 남긴다. 명단도 이번 절차 개시 뒤에 나온 것만 읽는다.
- 'Interested parties list' PDF(이번 절차의 가장 최근 것)를 한 실행 PDF_BUDGET개까지 읽는다. 탐침 232: 표 칸이 줄마다 끊겨 나온다
  ('8. LG Chem Ltd ⏎ Exporter/ ⏎ Producer', '9. ⏎ Korea Chemical ⏎ Industry ⏎ Association Association'). 번호로 줄을 다시 묶어 한 곳을 한 줄로 만들고,
  'Korea'·한국 기업 이름 낱말·출입처 영문 이름이 든 줄만 원문 그대로 남긴다(이메일 주소는 뺀다). 명단에 나라 칸이 없어 이름 낱말로 고른 것이라
  빠진 한국 업체가 있을 수 있다. 계열사 이름은 원문 줄에 그대로 보일 뿐 출입처로 바꿔 적지 않는다.
- 판정문·개시 고시(dgtr_docs.py, 11-14): 이번 절차의 가장 최근 판정문(Final·Preliminary Findings)과 개시 고시 PDF를 한 실행 DOC_BUDGET개씩 읽어
  사건 설명 줄·한국 문장·권고·세율 표 줄(판정문), 신청인·조사 대상 기간·기한(개시 고시)을 원문 그대로 붙인다. 개시 고시는 스캔본이라 글자 인식으로 읽는다.
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
PAGE_BUDGET = 8
PDF_BUDGET = 3
MAX_PDF_BYTES = 6_000_000
PDF_PAGES = 12
GAP = 1.5
NEW_DAYS = 30
MAX_LINES = 10
VERSION = 3            # 일정표 읽는 규칙이 바뀌면 올린다 — 저장된 사건을 다시 읽는다(3: 판정문·개시 고시 주소)
DOC_BUDGET = 3         # 한 실행에 읽는 판정문 수, 개시 고시 수(각각). 개시 고시 글자 인식은 한 건 20초쯤(탐침 235)
INIT_WINDOW_DAYS = 400 # 이번 절차 개시가 이 안일 때만 개시 고시를 읽는다(진행 중인 조사)
PARTIES_VERSION = 3    # 명단 읽는 규칙(3: 꼬리말로 보고 멈추지 않는다)
# 절차 공지: 조사 내용이 아니라 일정·연락처·명단·질문서 기한 같은 것
PROCEDURAL = re.compile(r"e-?\s?mail|extension|corrigendum|\bPUC\b|\bPCN\b|interested\s+part|address|contact|clarification|schedule|questionnaire", re.I)
# 조사 진행 문서: 절차 낱말이 같이 있어도 이쪽이 이긴다('Corrigendum to Final Findings')
SUBSTANTIVE = re.compile(r"preliminary|provisional|disclosure|final\s+finding|findings|recommend|terminat|withdraw|essential\s+facts|oral\s+hearing|public\s+hearing|"
                         r"customs\s+notification|sunset|review\s+initiat", re.I)
INITIATION = re.compile(r"initiation", re.I)
# 개시 고시를 고친 문서는 개시가 아니다
NOT_INITIATION = re.compile(r"corrigend|amend|addend|errat|extension|clarif", re.I)
PARTIES = re.compile(r"interested\s+part", re.I)
# 판정문: 'Final Findings'·'FINAL FINDING'·'Preliminary Findings'. 고친 문서(Corrigendum)는 읽을 대상이 아니다
FINDINGS = re.compile(r"\bfindings?\b", re.I)
KOREA = re.compile(r"\bKorea\b|\bROK\b", re.I)
# 한국 기업 이름 낱말(명단에 나라 칸이 없다) — 이름 낱말로 고르는 것일 뿐 한국 업체라는 확인이 아니다
KR_NAME = re.compile(r"\b(?:LG|SK|GS|LS|DL|OCI|KCC|KPX|KG|HD)\b|\b(?:Kumho|Lotte|Hanwha|Hyundai|Kia|POSCO|Samsung|Kolon|Hyosung|Daelim|Taekwang|Aekyung|Dongkuk|"
                     r"SeAH|Doosan|Songwon|Kukdo|Huvis|Hankook|Nexen|Taihan|Iljin|S-?Oil)\b")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+")
TABLE_HEAD = re.compile(r"^(?:S\.?\s*N(?:o|\.)|Sl\.?\s*No|Sr\.?\s*No|Name of (?:the )?(?:Interested|Part|Compan|Entit))", re.I)
ENTRY = re.compile(r"^(\d{1,3})[.)](?:\s|$)")
# 표 뒤 꼬리말(글머리표·Note:). 탐침 233: 괄호 줄·줄표 줄은 표 칸 안에도 나온다 — 꼬리말로 보고 읽기를 멈췄더니 페놀 명단 34곳 중 27곳에서 끊겼다
FOOTER = re.compile(r"^(?:[•]\s?|Note\s*:)", re.I)
ENTRY_LINES = 20       # 한 곳이 차지하는 줄(탐침 233: 가장 긴 곳 17줄 — 이메일이 줄마다 끊긴다)
SUBJECT = re.compile(r"imports? of|concerning|F\.\s*No|Subject:|originating in|exported from|Case No", re.I)


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
    """일정표 줄 → {initiated(이번 절차 개시), initTitle, firstInitiated?, latest{title,date}, steps, kind, partiesUrl?}. 줄이 없으면 None."""
    if not rows:
        return None
    inits = sorted((r for r in rows if INITIATION.search(r["title"]) and not NOT_INITIATION.search(r["title"])), key=lambda r: r["date"])
    latest = max(enumerate(rows), key=lambda x: (x[1]["date"], x[0]))[1]
    initiated = inits[-1]["date"] if inits else None
    # 명단은 이번 절차 개시 뒤에 나온 것만(지난 재심의 명단을 지금 명단처럼 보이지 않게)
    parties = [r for r in rows if PARTIES.search(r["title"]) and r.get("url") and (not initiated or r["date"] >= initiated)]
    last_party = max(parties, key=lambda r: r["date"]) if parties else None
    findings = [r for r in rows if FINDINGS.search(r["title"]) and not NOT_INITIATION.search(r["title"]) and r.get("url") and (not initiated or r["date"] >= initiated)]
    last_findings = max(findings, key=lambda r: r["date"]) if findings else None
    return {"initiated": initiated, **({"initTitle": inits[-1]["title"]} if inits else {}),
            **({"initUrl": inits[-1]["url"]} if inits and inits[-1].get("url") else {}),
            **({"firstInitiated": inits[0]["date"]} if inits and inits[0]["date"] != initiated else {}),
            "latest": {"title": latest["title"], "date": latest["date"]}, "steps": len(rows),
            "kind": kind_of(initiated, latest, today),
            **({"partiesUrl": last_party["url"], "partiesDate": last_party["date"]} if last_party else {}),
            **({"findingsUrl": last_findings["url"], "findingsDate": last_findings["date"], "findingsTitle": last_findings["title"]} if last_findings else {})}


def clean(x):
    return re.sub(r"\s+", " ", EMAIL.sub(" ", x)).strip(" ,;")


def party_entries(text):
    """명단 PDF 글 → (표의 한 곳을 한 줄로 묶은 목록('8. LG Chem Ltd Exporter/ Producer'), 마지막 번호). 표 머리·번호 줄을 못 찾으면 ([], 0)."""
    raw = re.sub(r"(" + EMAIL.pattern + r")[ \t]+(?=\d{1,3}[.)]\s)", r"\1\n", str(text or ""))     # '…@x.in 9. 이름'처럼 앞 칸 이메일에 붙은 번호를 떼어 낸다
    lines = [re.sub(r"\s+", " ", x).strip() for x in raw.splitlines()]
    lines = [x for x in lines if x]
    head = next((i for i, x in enumerate(lines) if TABLE_HEAD.match(x)), None)
    if head is None:
        return [], 0
    out, cur, last = [], None, 0
    for x in lines[head + 1:]:
        m = ENTRY.match(x)
        n = int(m.group(1)) if m else 0
        # 번호가 이어질 때만 새 줄(본문 속 숫자에 끊기지 않게). 묶던 줄을 놓쳤으면 더 큰 번호에서 다시 시작
        if m and (n == 1 if not last else (last < n <= last + 3 or (cur is None and n > last))):
            if cur:
                out.append(cur)
            cur, last = [x], n
        elif cur is not None:
            if FOOTER.match(x) or len(cur) >= ENTRY_LINES:      # 꼬리말이거나 너무 길면 이 곳은 여기까지 — 읽기는 멈추지 않고 다음 번호에서 다시 묶는다
                out.append(cur)
                cur = None
            else:
                cur.append(x)
    if cur:
        out.append(cur)
    return [clean(" ".join(e))[:160] for e in out], last


def korea_lines(text):
    """표로 묶지 못한 명단: 'Korea'가 든 줄(원문, 사건 제목 줄은 뺀다). 짧게 끊긴 줄은 앞 줄과 잇는다."""
    lines = [re.sub(r"\s+", " ", x).strip() for x in str(text or "").splitlines()]
    lines = [x for x in lines if x]
    out = []
    for i, x in enumerate(lines):
        prev = lines[i - 1] if i else ""
        if not KOREA.search(x) or SUBJECT.search(x) or (SUBJECT.search(prev) and not re.match(r"^\d", x) and len(x) > 40):   # 사건 제목 줄과 그 이어진 줄
            continue
        y = f"{prev} {x}" if len(x) < 40 and prev and not KOREA.search(prev) and not SUBJECT.search(prev) and not prev.endswith(".") else x
        y = clean(y)[:180]
        if y and y not in out:
            out.append(y)
        if len(out) >= MAX_LINES:
            break
    return out


def pick_korea(entries, beat_rx):
    """묶은 줄 가운데 Korea·한국 기업 이름 낱말·출입처 영문 이름이 든 것(원문 그대로, 출입처 이름이 든 줄 먼저)."""
    hit = [e for e in entries if KOREA.search(e) or KR_NAME.search(e) or any(re.search(rx, e, re.I) for _, rx in beat_rx)]
    hit.sort(key=lambda e: 0 if any(re.search(rx, e, re.I) for _, rx in beat_rx) else 1)
    return hit[:MAX_LINES], len(hit)


def read_parties(url, *, get):
    import io

    import pypdf
    import tra_file_watch as tra
    r = get(url, headers=HEADERS, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    data = r.content
    if len(data) > MAX_PDF_BYTES:
        raise RuntimeError("PDF가 큼")
    pdf = pypdf.PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in pdf.pages[:PDF_PAGES])      # 쪽 사이도 줄바꿈 — 쪽 첫 줄 번호가 앞 줄에 붙지 않게
    return parties_from_text(text, len(pdf.pages), tra.beat_names())


def parties_from_text(text, pages, beat_rx):
    entries, last_no = party_entries(text)
    if entries:
        lines, total = pick_korea(entries, beat_rx)
        scope = " ".join(entries)
        return {"v": PARTIES_VERSION, "pages": pages, "chars": len(text), "shape": "table", "entries": len(entries), "lastNo": last_no, "koreaLines": lines, "koreaTotal": total,
                "beat": [name for name, rx in beat_rx if re.search(rx, scope, re.I)]}
    lines = korea_lines(text)                                                         # 표 꼴이 아니면 줄 단위로(덜 정확)
    return {"v": PARTIES_VERSION, "pages": pages, "chars": len(text), "shape": "lines", "entries": 0, "koreaLines": lines, "koreaTotal": len(lines),
            "beat": [name for name, rx in beat_rx if re.search(rx, text or "", re.I)]}


def read_findings(url, *, get, beat_rx):
    import dgtr_docs
    return dgtr_docs.read_findings(url, get=get, beat_rx=beat_rx)


def read_initiation(url, *, get, beat_rx):
    import dgtr_docs
    return dgtr_docs.read_initiation(url, get=get, beat_rx=beat_rx)


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
            if u not in store or store[u].get("status") != "ok" or store[u].get("v") != VERSION or seen > str(store[u].get("checkedAt") or "")]
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
            # 이미 읽은 PDF는 주소가 같으면 그대로 둔다(사건 페이지만 다시 읽은 것)
            keep = {k: prev[k] for k, link in (("parties", "partiesUrl"), ("findings", "findingsUrl"), ("initiation", "initUrl"))
                    if prev.get(k) and prev[k].get("url") == summary.get(link)}
            store[u] = {"status": "ok", "v": VERSION, "checkedAt": stamp, **summary, **keep}
            read += 1
        except Exception as e:  # noqa: BLE001 — 한 사건 실패가 다른 사건을 막지 않는다
            store[u] = {**{k: v for k, v in prev.items() if k not in ("status", "error")}, "status": "failed", "error": str(e)[:60] or type(e).__name__,
                        "checkedAt": prev.get("checkedAt") or "", "triedAt": stamp}
            failed += 1
    # 이해관계자 명단 PDF: 아직 안 읽은 것만(새로 뜬 사건부터)
    def wants_pdf(u):
        c = store.get(u) or {}
        p = c.get("parties") or {}
        if c.get("status") != "ok" or not c.get("partiesUrl"):
            return False
        return not p or (p.get("status") == "ok" and p.get("v") != PARTIES_VERSION) or (p.get("status") == "failed" and (p.get("tries") or 1) < 3)

    for u in sorted((u for u in newest if wants_pdf(u)), key=lambda u: newest[u], reverse=True)[:PDF_BUDGET]:
        sleep(GAP)
        c = store[u]
        tries = ((c.get("parties") or {}).get("tries") or 0) + 1
        try:
            c["parties"] = {"url": c["partiesUrl"], "date": c.get("partiesDate"), "status": "ok", **read_parties(c["partiesUrl"], get=get)}
        except Exception as e:  # noqa: BLE001
            c["parties"] = {"url": c["partiesUrl"], "date": c.get("partiesDate"), "status": "failed", "error": str(e)[:60] or type(e).__name__, "tries": tries}
        pdfs += 1
    # 판정문·개시 고시 PDF(dgtr_docs): 아직 안 읽었거나 읽는 규칙이 바뀐 것만, 새로 뜬 사건부터
    import dgtr_docs
    import tra_file_watch as tra
    beat_rx = tra.beat_names()
    docs = {"findings": 0, "initiations": 0, "ocr": 0, "docFailed": 0}
    since_init = (now - dt.timedelta(days=INIT_WINDOW_DAYS)).date().isoformat()

    def wants(c, key, link):
        d = c.get(key) or {}
        if c.get("status") != "ok" or not c.get(link):
            return False
        if key == "initiation" and str(c.get("initiated") or "") < since_init:
            return False
        return not d or d.get("url") != c[link] or (d.get("status") == "ok" and d.get("v") != dgtr_docs.DOC_VERSION) or (d.get("status") == "failed" and (d.get("tries") or 1) < 3)

    for key, link, date_key, title_key, reader, counter in (("findings", "findingsUrl", "findingsDate", "findingsTitle", read_findings, "findings"),
                                                            ("initiation", "initUrl", "initiated", "initTitle", read_initiation, "initiations")):
        for u in sorted((u for u in newest if wants(store.get(u) or {}, key, link)), key=lambda u: newest[u], reverse=True)[:DOC_BUDGET]:
            sleep(GAP)
            c = store[u]
            base = {"url": c[link], "date": c.get(date_key), "title": c.get(title_key)}
            tries = ((c.get(key) or {}).get("tries") or 0) + 1 if (c.get(key) or {}).get("url") == c[link] else 1
            try:
                c[key] = {**base, "status": "ok", **reader(c[link], get=get, beat_rx=beat_rx)}
                docs[counter] += 1
                docs["ocr"] += 1 if c[key].get("ocr") else 0
            except Exception as e:  # noqa: BLE001
                c[key] = {**base, "status": "failed", "error": str(e)[:60] or type(e).__name__, "tries": tries}
                docs["docFailed"] += 1
    doc["dgtrCases"] = store
    kinds = {}
    for u in newest:
        k = store.get(u, {}).get("kind") if store.get(u, {}).get("status") == "ok" else "미확인"
        kinds[k] = kinds.get(k, 0) + 1
    return {"cases": len(newest), "read": read, "failed": failed, "waiting": max(0, len(todo) - PAGE_BUDGET), "pdfs": pdfs, "kinds": kinds,
            "korea": sum(1 for u in newest if (store.get(u, {}).get("parties") or {}).get("koreaLines")),
            "beat": sum(1 for u in newest if (store.get(u, {}).get("parties") or {}).get("beat")), **docs,
            "docWaiting": sum(1 for u in newest for key, link in (("findings", "findingsUrl"), ("initiation", "initUrl")) if wants(store.get(u) or {}, key, link))}
