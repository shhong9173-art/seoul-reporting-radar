"""호주 무역구제위원회(ATRC) 진행 사건 공개기록(EPR) — 기자 컴퓨터 브라우저 수집(local_notice_submit pages, id au-epr)을 읽는다.

레이더는 호주에서 공지(TRN) 목록의 한국 줄만 봤다. TRN은 개시·연장·판정 같은 공지뿐이고, 당사자 의견서·검증 보고서·면담 기록·
종결 보고서는 사건마다의 공개기록(EPR) 표에만 올라온다. 11-14 기자 컴퓨터 브라우저 확인(진행 28건 중 한국 3건):
- 698 알루미늄아연도금강판 종료재심: KG Dongbu Steel 의견서(06-29·10-15), BlueScope의 '한국 열연 시장 PMS' 의견서(06-19·09-15)
- 706 아연도금강판 조사: POSCO·Dongkuk Coated Metal 질문서 답변(08-31), 'Meeting with POSCO'(09-28), 'Termination report - Dongkuk Steel Mill'(09-18)
- 710 중공형강 종료재심: 한국 업체 이름이 든 문서는 아직 없음
industry.gov.au는 GitHub·Cloudflare에서 막혀(응답 없음·HTTP 520) 기자 컴퓨터 Aside 수집(평일 09:00·16:00, scripts/aside/kr_browser_collect.js
토막 5)이 올린 줄만 읽는다. 기자 11-14 22:36 승인.

수집 줄(첫 칸 = 종류, 둘째 칸 = 사건 번호. 빈 칸은 '-'):
  list  | 진행 사건 수 | 한국 줄 수
  case  | 번호 | 품목 | 번호 | 사건 종류 | 나라 | 다음 단계 | 마지막 갱신(dd/mm/yyyy) | 상태          (+ 사건 페이지 링크)
  title | 번호 | 사건 제목 | 문서 수
  info·date | 번호 | 이름 | 값
  doc   | 번호 | EPR 번호 | 문서 종류 | 제목 | 날짜(dd/mm/yyyy)                                        (+ 첫 PDF 링크)
  error | 번호 | 이유
  acase | 번호 | 품목 | 가장 최근 공지 제목 | 나라 | 가장 최근 공지일(dd/mm/yyyy)   — 보관(종결) 사건(+ 보관 사건 페이지 링크). 뒤에 title·info·date·doc 줄

보관 사건(기자 11-15 02:54): 수집 코드가 TRN 목록의 한국 줄 가운데 보관 사건 링크가 달리고 공지일이 150일 안인 사건(4건까지)의 사건 페이지도 읽는다.
진행 목록에 있던 사건이 보관 사건으로 올라오면 바로 '보관 목록으로 옮겨짐'을 알리고(두 번 기다리지 않는다), 보관 사건에 새로 붙는 문서(최종 보고서·
장관 결정 공지 등)도 같은 규칙으로 알린다. 처음 보는 보관 사건은 기준선. 보관 사건이 수집에서 빠지면(공지일이 150일을 넘김) 조용히 내려놓는다.

본문 읽기(기자 11-15 02:54): industry.gov.au는 PDF도 서버에서 막힌다(탐침 241). 직접 출입처 이름이 든 문서 가운데 아직 본문을 못 읽은 것을
`want`에 적어 두면(4건까지, 의견서·보고서 먼저·최근 순) 기자 컴퓨터 수집이 그 PDF를 받아 레이더로 올리고, au_epr_docs.py가 글자를 풀어 `pdf`에 한국·출입처 대목을 남긴다.

이벤트 — 처음 읽은 사건은 기준선이다(캐나다 CBSA에서 옛 문서를 새 문서로 알린 11-14 실수를 되풀이하지 않게):
- 이미 아는 사건에 새 EPR 번호 줄: 문서 날짜가 FRESH_DAYS 안일 때만. 날짜를 못 읽은 줄은 알리지 않는다. 한 사건에서 한 번에 BURST건
  넘게 새로 보이면 한 줄로 묶는다(수집 꼴이 바뀌어 한꺼번에 쏟아지는 것을 막는다).
- 기준선 뒤 진행 목록에 새로 들어온 한국 사건: 개시일(Initiation Date)이 FRESH_DAYS 안일 때만.
- 진행 목록의 다음 단계가 바뀜 / 주요 일정 날짜가 바뀜 / 진행 목록에서 두 번 연속 빠짐(종결돼 보관 목록으로 옮겨졌을 수 있음).
등급(기자 11-15 02:21 — 캐나다 CBSA와 같은 규칙, 첫 수집이 맞게 도는 것을 본 뒤 올림): 직접 출입처 이름이 든 문서는 A(연장·일정·
현황 보고 같은 절차 문서는 이름이 있어도 B). 출입처 이름이 없으면 Report(SEF·종결 보고서·최종 보고서 등)만 B, 그 밖은 C —
Notice(ADN·TRN)는 TRN 목록 감시가 따로 알린다. 새 사건·진행 목록에서 빠짐은 문서 제목에 직접 출입처 이름이 있으면 A, 없으면 B.
단계·일정 바뀜은 C. 문서 제목·날짜만 읽는다(PDF 본문은 읽지 않음).
"""
from __future__ import annotations

import datetime as dt
import re
import zlib

PAGE_ID = "au-epr"
SOURCE = "호주 ATRC 사건 공개기록(EPR)"
HOST = "https://www.industry.gov.au"
INDEX = HOST + "/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr"
ARCHIVE = HOST + "/australian-trade-remedies-commission/archive-cases-and-electronic-public-record-epr"
WANT_MAX = 4             # 한 번에 기자 컴퓨터에 받아 달라고 하는 PDF
WANT_DAYS = 400          # 이보다 오래된 문서의 본문은 받지 않는다
PDF_VERSION = 1
PDF_TRIES = 3
PDF_KEEP = 80
PDF_PATH = re.compile(r"^/sites/default/files/[A-Za-z0-9_./%-]+\.pdf$", re.I)
WANT_FIRST = re.compile(r"submission|report|notice", re.I)
KINDS = ("list", "case", "title", "info", "date", "doc", "error", "acase")
FRESH_HOURS = 30          # 수집이 이보다 오래되면 미확인(무역구제 목록의 브라우저 수집과 같은 기준)
FRESH_MONDAY = 78         # 토·일과 월요일 오전에는 금요일 수집까지
FRESH_DAYS = 45           # 새 문서·새 사건으로 알리는 것은 문서일·개시일이 이 안일 때만
BURST = 6                 # 한 사건에서 한 번에 이보다 많이 새로 보이면 한 줄로 묶는다
MAX_DOCS = 60
CASE_NO = re.compile(r"^[A-Za-z0-9-]{1,20}$")
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
PDF_SIZE = re.compile(r"\s*\[pdf[^\]]*\]", re.I)
# 절차 문서: 기한 연장·일정·현황 보고(Day 60 Status Report 등) — 출입처 이름이 있어도 B
PROCEDURAL = re.compile(r"extension of time|status report|timetable|schedule", re.I)
KIND_KO = {"investigation": "조사", "continuation": "종료재심", "review": "재심", "accelerated review": "신속 재심",
           "anti-circumvention": "우회 조사", "exemption": "면제 조사", "duty assessment": "관세 정산"}


def iso_date(text):
    """'15/10/2026' · '19 June 2026' · '03 August 2026' → '2026-10-15' (못 읽으면 '')."""
    t = str(text or "")
    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", t)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"\b(\d{1,2}) ([A-Za-z]+) (20\d{2})\b", t)
        if not m or m.group(2).lower() not in MONTHS:
            return ""
        d, mo, y = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return ""


def beat_in(text):
    import cbsa_cases
    return cbsa_cases.beat_in(text)


def direct(companies):
    return [x for x in companies or [] if not x.endswith("(관련)")]


def tier_of(doc_type, title, companies):
    """직접 출입처 이름이 든 문서는 A(절차 문서는 B). 이름이 없으면 Report만 B, 그 밖은 C."""
    if direct(companies):
        return "B" if PROCEDURAL.search(str(title or "")) else "A"
    if PROCEDURAL.search(str(title or "")):
        return "C"
    return "B" if re.fullmatch(r"report", str(doc_type or "").strip(), re.I) else "C"


def named_tier(companies):
    return "A" if direct(companies) else "B"


def kind_ko(kind):
    return KIND_KO.get(str(kind or "").strip().lower(), str(kind or "").strip())


def clean(v, n=300):
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    return "" if v == "-" else v[:n]


def link_of(row):
    for x in row.get("links") or []:
        if isinstance(x, str) and x.startswith("/") and not x.startswith("//"):
            return HOST + x
    return None


def parse_rows(rows):
    """수집 줄 → (목록 사건 수 또는 None, {번호: 사건}). 사건: commodity·kind·countries·milestone·updated·url·title·n·info·dates·docs·error."""
    total, cases = None, {}

    def slot(no):
        return cases.setdefault(no, {"info": {}, "dates": {}, "docs": []})

    for r in rows or []:
        cells = [str(c) for c in (r.get("cells") if isinstance(r, dict) else None) or []]
        if len(cells) < 2 or cells[0] not in KINDS:
            continue
        kind, no = cells[0], cells[1].strip()
        if kind == "list":
            total = int(no) if no.isdigit() else None
            continue
        if not CASE_NO.match(no):
            continue
        if kind == "case":
            c = slot(no)
            v = [clean(x, 200) for x in cells[2:9]] + [""] * 7
            c.pop("archived", None)
            c.pop("subject", None)
            c.update(listed=True, commodity=v[0], kind=v[2], countries=v[3], milestone=v[4], updated=iso_date(v[5]), state=v[6],
                     url=link_of(r) or f"{INDEX}/{no}")
        elif kind == "acase":
            if cases.get(no, {}).get("listed"):
                continue   # 진행 목록에도 있는 번호면 진행 사건으로 둔다
            c = slot(no)
            v = [clean(x, 200) for x in cells[2:6]] + [""] * 4
            c.update(listed=True, archived=True, commodity=v[0], subject=v[1], countries=v[2], updated=iso_date(v[3]), url=link_of(r) or f"{ARCHIVE}/{no}")
        elif no not in cases:
            continue  # 목록에 없는 사건 번호의 줄은 받지 않는다
        elif kind == "title" and len(cells) >= 3:
            cases[no]["title"] = clean(cells[2], 200)
            cases[no]["n"] = int(cells[3]) if len(cells) > 3 and cells[3].isdigit() else None
        elif kind in ("info", "date") and len(cells) >= 4:
            key, val = clean(cells[2], 120), clean(cells[3], 280)
            if key and val:
                cases[no]["dates" if kind == "date" else "info"].setdefault(key, val)
        elif kind == "doc" and len(cells) >= 6:
            num = clean(cells[2], 12)
            # 제목 칸에는 첫 문서 제목 뒤에 첨부 이름이 이어 붙는다('… [pdf 288 KB] Non-Confidential Attachment - Appendix A [pdf 224 KB]').
            # 보여 주는 제목은 첫 문서 제목만(운영 11-15: 첨부 이름까지 붙어 한 줄이 너무 길었다), 출입처 이름은 첨부 이름까지 본다
            whole = PDF_SIZE.sub("", clean(cells[4], 280)).strip()
            title = re.split(r"\s*\[pdf", clean(cells[4], 280), maxsplit=1, flags=re.I)[0].strip() or whole
            if num and title and len(cases[no]["docs"]) < MAX_DOCS and not any(d["no"] == num for d in cases[no]["docs"]):
                firms = beat_in(whole)
                cases[no]["docs"].append({"no": num, "type": clean(cells[3], 40), "title": title, "date": iso_date(cells[5]), "url": link_of(r),
                                          **({"companies": firms} if firms else {})})
        elif kind == "error":
            cases[no]["error"] = clean(cells[2], 100) or "못 읽음"
    return total, {no: c for no, c in cases.items() if c.get("listed")}


def entry_of(browser, now):
    """(수집 항목, None) 또는 (None, 이유)."""
    entry = next((x for x in (browser or {}).get("pages") or [] if isinstance(x, dict) and x.get("id") == PAGE_ID), None)
    if not entry:
        return None, "브라우저 수집 없음(예약 작업이 사건 공개기록을 아직 올리지 않았거나 컴퓨터·앱이 꺼짐)"
    try:
        age = (now - dt.datetime.fromisoformat(str(entry.get("fetchedAt")))).total_seconds() / 3600
    except (TypeError, ValueError):
        return None, "브라우저 수집 시각 미상"
    limit = FRESH_MONDAY if now.weekday() >= 5 or (now.weekday() == 0 and now.hour < 12) else FRESH_HOURS
    if age > limit:
        return None, f"브라우저 수집이 {age:.0f}시간 전 — 컴퓨터·앱이 꺼졌을 수 있음"
    if entry.get("error"):
        return None, f"브라우저 수집 실패({str(entry['error'])[:60]})"
    return entry, None


def label_of(no, c):
    return f"호주 ATRC 사건 {no} {c.get('commodity') or c.get('title') or ''}({'종결·보관' if c.get('archived') else kind_ko(c.get('kind')) or '사건'})".replace("  ", " ")


def doc_key(no, d):
    return f"{no}-{d.get('no')}"


def pdf_path(url):
    """같은 사이트의 공개기록 PDF 주소만 → '/sites/default/files/….pdf' (아니면 '')."""
    path = str(url or "")
    path = path[len(HOST):] if path.startswith(HOST + "/") else path
    return path if PDF_PATH.match(path) and ".." not in path else ""


def want_list(cases, pdf, now):
    """본문을 아직 못 읽은, 직접 출입처 이름이 든 문서 → [{key, url}] (의견서·보고서·공지 먼저, 최근 순, WANT_MAX건)."""
    cutoff = (now.date() - dt.timedelta(days=WANT_DAYS)).isoformat()
    out = []
    for no, c in cases.items():
        if c.get("missing") or c.get("gone"):
            continue
        for d in c.get("docs") or []:
            path, done = pdf_path(d.get("url")), (pdf or {}).get(doc_key(no, d)) or {}
            if not direct(d.get("companies")) or not path or (d.get("date") or "") < cutoff:
                continue
            if done.get("v") == PDF_VERSION and ("excerpts" in done or int(done.get("tries") or 0) >= PDF_TRIES):
                continue
            out.append((0 if WANT_FIRST.search(d.get("type") or "") else 1, d.get("date") or "", doc_key(no, d), path))
    out.sort(key=lambda x: x[1], reverse=True)
    out.sort(key=lambda x: x[0])
    return [{"key": k, "url": u} for _, _, k, u in out[:WANT_MAX]]


def doc_num(d):
    return int(d["no"]) if str(d.get("no", "")).isdigit() else -1


def collect(browser, previous, now):
    """(구역, 이벤트, 점검). 수집이 없거나 오래됐으면 직전 구역을 그대로 두고 실패로 표시한다(0건 아님)."""
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    prev_cases = prev.get("cases") if isinstance(prev.get("cases"), dict) else {}

    pdf = prev.get("pdf") if isinstance(prev.get("pdf"), dict) else {}

    def failed(why):
        section = {**prev, "status": "failed", "error": why, "checkedAt": stamp} if prev else None
        return section, [], {"source": SOURCE, "status": "failed", "returned": sum(len(c.get("docs") or []) for c in prev_cases.values()),
                             "cases": len(prev_cases), "events": 0, "error": why}

    entry, err = entry_of(browser, now)
    if err:
        return failed(err)
    total, got = parse_rows(entry.get("rows"))
    if total is None:
        return failed("수집 줄에 진행 사건 목록 줄(list)이 없음 — 형식 변경 가능")
    fetched = str(entry.get("fetchedAt"))
    had = bool(prev.get("baselineAt"))
    same_upload = had and prev.get("fetchedAt") == fetched   # 같은 수집을 다시 읽는 실행: 비교할 새 것이 없다
    cutoff = (now.date() - dt.timedelta(days=FRESH_DAYS)).isoformat()
    cases, events, counts = {}, [], {"newDocs": 0, "newCases": 0, "changes": 0, "gone": 0, "unread": 0}

    def push(no, c, key, text, tier, url=None, firms=None):
        events.append({"id": f"{PAGE_ID}:{no}:{key}", "pageId": PAGE_ID, "country": "호주", "label": label_of(no, c), "text": text,
                       "url": url or c.get("url") or INDEX, "detectedAt": stamp, "tier": tier, **({"companies": firms} if firms else {})})

    for no, c in got.items():
        old = prev_cases.get(no) if isinstance(prev_cases.get(no), dict) else None
        if c.get("error"):   # 목록에는 있는데 사건 페이지를 못 읽음: 직전 문서 줄을 그대로 두고 알리지 않는다
            counts["unread"] += 1
            keep = {k: old[k] for k in ("title", "n", "info", "dates", "docs", "companies", "firstSeen") if old and k in old}
            cases[no] = {**keep, **{k: c[k] for k in ("commodity", "kind", "countries", "milestone", "updated", "state", "url", "subject", "archived") if c.get(k)},
                         "firstSeen": (old or {}).get("firstSeen") or stamp, "error": c["error"]}
            continue
        docs = sorted(c["docs"], key=doc_num, reverse=True)
        firms = sorted({f for d in docs for f in d.get("companies") or []})
        rec = {k: c[k] for k in ("commodity", "kind", "countries", "milestone", "updated", "state", "url", "title", "n", "subject", "archived") if c.get(k) not in (None, "")}
        rec.update(info=c["info"], dates=c["dates"], docs=docs, firstSeen=(old or {}).get("firstSeen") or stamp, **({"companies": firms} if firms else {}))
        cases[no] = rec
        if not had or same_upload:
            continue
        if c.get("archived") and old is None:
            continue   # 처음 보는 보관 사건: 기준선
        if c.get("archived") and old is not None and not old.get("archived"):
            # 진행 목록에 있던 사건이 보관 사건으로 올라옴: 바로 알린다(문서 줄은 아래에서 같은 규칙으로)
            counts["gone"] += 1
            push(no, rec, "archived", f"보관(종결) 목록으로 옮겨짐: 「{rec.get('title') or no}」"
                 f"{' · 가장 최근 공지 「' + rec['subject'] + '」(' + (rec.get('updated') or '?') + ')' if rec.get('subject') else ''} — 최종 판정·조치 내용은 공지·최종 보고서에서 확인",
                 named_tier(firms or old.get("companies")), firms=firms or old.get("companies"))
        if (old is None or old.get("gone")) and not c.get("archived"):
            started = iso_date(c["dates"].get("Initiation Date"))
            if started and started >= cutoff:
                counts["newCases"] += 1
                push(no, rec, "new", f"진행 사건 목록에 새로 들어옴: 「{rec.get('title') or no}」 · {kind_ko(rec.get('kind'))} · 개시 {started} · 나라 {rec.get('countries') or '?'}"
                     f"{' · 문서에 나온 출입처 이름 ' + '·'.join(firms) if firms else ''}", named_tier(firms), firms=firms)
            continue
        if old is None:
            continue
        if not old.get("docs") and old.get("error"):
            continue   # 직전에 사건 페이지를 한 번도 못 읽었다: 이번이 기준선
        known = {str(d.get("no")) for d in old.get("docs") or []}
        fresh = [d for d in docs if d["no"] not in known and d["date"] and d["date"] >= cutoff]
        if len(fresh) > BURST:
            names = sorted({f for d in fresh for f in d.get("companies") or []})
            top = fresh[0]
            tier = min(tier_of(d["type"], d["title"], d.get("companies")) for d in fresh)   # 'A' < 'B' < 'C"
            counts["newDocs"] += len(fresh)
            push(no, rec, f"docs:{stamp[:10]}", f"새 문서 {len(fresh)}건(EPR {fresh[-1]['no']}~{fresh[0]['no']}번) — 가장 최근: {top['type']} 「{top['title'][:160]}」({top['date']})"
                 f"{' · 출입처 이름 ' + '·'.join(names) if names else ''}", tier, url=rec.get("url"), firms=names)
        else:
            for d in fresh:
                counts["newDocs"] += 1
                push(no, rec, f"doc:{d['no']}", f"새 문서 EPR {d['no']}번 {d['type']} 「{d['title'][:200]}」({d['date']})",
                     tier_of(d["type"], d["title"], d.get("companies")), url=d.get("url"), firms=d.get("companies"))
        if old.get("milestone") and rec.get("milestone") and old["milestone"] != rec["milestone"]:
            counts["changes"] += 1
            push(no, rec, f"milestone:{rec['milestone'][:30]}", f"진행 목록의 다음 단계 바뀜: {old['milestone']} → {rec['milestone']}", "C")
        moved = [(k, (old.get("dates") or {})[k], v) for k, v in rec["dates"].items()
                 if k in (old.get("dates") or {}) and (old.get("dates") or {})[k] != v and (iso_date(v) or iso_date((old.get("dates") or {})[k]))]
        if moved:
            counts["changes"] += 1
            sig = zlib.crc32("|".join(f"{k}={v}" for k, _, v in moved).encode("utf-8"))
            push(no, rec, f"dates:{sig:08x}", "주요 일정 바뀜: " + " / ".join(f"{k} {a} → {b}" for k, a, b in moved[:4]), "C")
    # 직전에 있던 사건이 이번 목록에 없다: 두 번 연속 빠지면 알린다(한 번은 수집이 줄을 놓쳤을 수 있다)
    for no, old in prev_cases.items():
        if no in cases or not isinstance(old, dict):
            continue
        if old.get("archived"):
            continue   # 보관 사건이 수집에서 빠짐(공지일이 150일을 넘김): 조용히 내려놓는다
        miss = old.get("missing", 0) if same_upload else old.get("missing", 0) + 1
        rec = {**old, "missing": miss}
        if miss >= 2 and not old.get("gone"):
            rec["gone"] = stamp
            counts["gone"] += 1
            push(no, old, "gone", f"진행 사건 목록에서 빠짐: 「{old.get('title') or no}」 — 종결돼 보관 목록으로 옮겨졌을 수 있음(최종 공지·판정은 TRN 목록에서 확인)",
                 named_tier(old.get("companies")), firms=old.get("companies"))
        cases[no] = rec
    for no in got:
        cases[no].pop("missing", None)
        cases[no].pop("gone", None)
    live = [c for c in cases.values() if not c.get("missing") and not c.get("archived")]
    keys = {doc_key(no, d) for no, c in cases.items() for d in c.get("docs") or []}
    pdf = dict(sorted(((k, v) for k, v in pdf.items() if k in keys and isinstance(v, dict)), key=lambda kv: str(kv[1].get("date") or ""), reverse=True)[:PDF_KEEP])
    section = {"status": "ok", "checkedAt": stamp, "fetchedAt": fetched, "baselineAt": prev.get("baselineAt") or stamp, "listTotal": total, "cases": cases,
               "pdf": pdf, "want": want_list(cases, pdf, now)}
    counts["archived"] = sum(1 for c in cases.values() if c.get("archived"))
    check = {"source": SOURCE, "status": "partial" if counts["unread"] else "ok", "returned": sum(len(c.get("docs") or []) for c in live), "cases": len(live),
             "listTotal": total, "events": len(events), "baseline": not had, **counts,
             **({"error": f"사건 페이지 {counts['unread']}건 못 읽음"} if counts["unread"] else {})}
    return section, events, check
