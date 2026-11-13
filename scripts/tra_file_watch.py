"""영국 무역구제청(TRA) 공개기록(public file) — 한국산 조사에 당사자들이 낸 문서를 올라온 다음 날 아침에 잡는다.

근거(11-13): 기자의 단독 세 건 중 하나(11-10 英 S-PVC '한국 특별시장상황' 의견서)가 이 공개기록의 문서였다. 레이더는
조사 목록의 '갱신일'만 보고 있었고, 문서는 기자가 직접 내려받아 읽었다. 공개기록은 로그인 없이 열린다(탐침 11-13):
- 목록 https://public-file.trade-remedies.service.gov.uk/ — 진행·종료 조사 표(No.·Case·Commodity·Country·Type·Initiated·Updated)
- 사건 /case/ad0092 — 공개기록 표(Submission·Party·Type·Published·No. of files), 줄마다 /submission/<id>
- 제출 /case/ad0092/submission/<id> — 파일 링크(…azurefd.net/content/<이름>.pdf)
  AD0071(한국산 후판) 75줄: POSCO·Hyundai Steel·Dongkuk Steel Mill·Government of the Republic of Korea·KOSA 등
  AD0092(S-PVC) 29줄: LG Chem, Ltd.·Hanwha Solutions Corporation·Government of Korea, MOTIR 등

잡는 것: 나라 칸에 Korea가 든 진행 조사의 새 문서. 등급은
  A  출입처·한국 정부·한국 업계 단체가 낸 문서(질문서 답변·등록 같은 정해진 절차 문서는 B), 조사기관의 판단·쟁점 문서
     (필수사실 고지·잠정/최종 판정·권고·종결·특별시장상황·대표 제3국·가격약속)
  B  조사기관의 절차 문서(개시·표본·공개기록 메모·청문), 다른 당사자 문서 중 본문에 출입처 이름이 나온 것
  C  그 밖(다른 나라 수출자·영국 수입자의 질문서 답변 등)
문서는 당사자 주장이다 — 조사기관 판단이 아니다. 결과는 기자 전용 저장소(trade-remedy의 tra 구역)로만.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import re
import time
from urllib.parse import unquote

BASE = "https://public-file.trade-remedies.service.gov.uk"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en-GB,en;q=0.9"}
FIRST_DAYS = 3          # 첫 실행: 최근 사흘에 올라온 문서만 새 문서로 알린다(그 앞은 기준선)
KEEP_DAYS = 200         # 화면에 남기는 문서(게시일 기준)
MAX_DOCS = 150          # 저장 문서 한도(무역구제 저장 문서 전체가 2MB를 넘으면 저장이 거부된다)
PAGE_BUDGET = 20        # 한 번 실행에 여는 제출 페이지 수
PDF_BUDGET = 8          # 한 번 실행에 읽는 PDF 수
MAX_PDF_BYTES = 15_000_000
PDF_PAGES = 40
MAX_CASES = 8
KOREA = re.compile(r"\bKorea\b", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
TRA_PARTY = re.compile(r"Trade Remedies Authority", re.I)
GOV = re.compile(r"Government of (?:the Republic of )?Korea|\bMOTIR\b|\bMOTIE\b|Ministry of Trade,? Industry", re.I)
KR_GROUP = re.compile(r"Korea Iron (?:and|&) Steel Association|\bKOSA\b|Korea Petrochemical Industry Association|Korea International Trade Association", re.I)
# 정해진 절차 문서(누구나 내는 것): 질문서 답변·등록·기한 연장
ROUTINE = re.compile(r"Pre-?Sampling|Questionnaire|Registration|Deficienc|Extension", re.I)
TRA_A = re.compile(r"Statement of Essential Facts|\bSEF\b|Provisional|Determination|Recommendation|Terminat|Particular Market|\bPMS\b|"
                   r"third country|Undertaking|Reconsideration|Definitive", re.I)
TRA_B = re.compile(r"Initiation|Sampling|Note to (?:the )?public file|Registration of imports|Hearing|Supplementary|Verification", re.I)
# 본문에서 먼저 고르는 문장: 요청·쟁점 낱말
KEY = re.compile(r"de minimis|negligible|terminat|particular market situation|normal value|dumping margin|injury|undertaking|"
                 r"respectfully|request(?:s|ed)?\b|subsid|price reduction|government support", re.I)


def beat_names():
    from trade_remedy_watch import BEAT_NAMES
    return BEAT_NAMES


def companies_in(text):
    return [name for name, rx in beat_names() if re.search(rx, text or "", re.I)]


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))).strip()


def iso_date(text):
    """'2026-09-10 10 Sep 2026' · '09 Nov 2026' → '2026-09-10' (못 읽으면 '')."""
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", text or "")
    if m:
        return m.group(0)
    m = re.search(r"\b(\d{1,2}) ([A-Z][a-z]{2})[a-z]* (20\d{2})\b", text or "")
    if m and m.group(2) in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    return ""


def cells(row):
    """표 한 줄 → {칸 이름: (값 글, 칸 원문)}. 칸 이름은 좁은 화면용 숨김 글자('Party: ')에서 읽는다."""
    out = {}
    for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", row, re.I):
        m = re.search(r"<span[^>]*visually-hidden[^>]*>([^<]*)</span>", c)
        if not m:
            continue
        label = plain(m.group(1)).rstrip(":. ").lower()
        out[label] = (plain(c.replace(m.group(0), " ")), c)
    return out


def parse_cases(page):
    """목록 페이지 → [{id, title, commodity, country, type, initiated, updated, closed, active, url}]."""
    out = []
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", page or "", re.I):
        c = cells(row)
        no = c.get("no", ("", ""))[0]
        m = re.search(r"\b([A-Z]{2}\d{4})\b", no)
        if not m:
            continue
        cid = m.group(1)
        out.append({"id": cid, "title": c.get("case", ("", ""))[0][:160], "commodity": c.get("commodity", ("", ""))[0][:120],
                    "country": c.get("country", ("", ""))[0][:120], "type": c.get("type", ("", ""))[0][:60],
                    "initiated": iso_date(c.get("initiated", ("", ""))[0]), "updated": iso_date(c.get("updated", ("", ""))[0]),
                    "closed": iso_date(c.get("closed", ("", ""))[0]), "active": "closed" not in c, "url": f"{BASE}/case/{cid.lower()}"})
    return out


def parse_case_page(page, cid):
    """사건 페이지의 공개기록 표 → [{sid, title, party, ptype, published, files, url}]."""
    out, seen = [], set()
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", page or "", re.I):
        c = cells(row)
        if "submission" not in c or "party" not in c:
            continue
        m = re.search(r'href\s*=\s*"([^"]*/submission/([^"/?#]+))"', c["submission"][1])
        if not m or m.group(2) in seen:
            continue
        seen.add(m.group(2))
        n = re.search(r"\d+", c.get("no. of files", ("", ""))[0])
        out.append({"sid": m.group(2), "title": c["submission"][0][:200], "party": c["party"][0][:160], "ptype": c.get("type", ("", ""))[0][:60],
                    "published": iso_date(c.get("published", ("", ""))[0]), "files": int(n.group(0)) if n else 0,
                    "url": m.group(1) if m.group(1).startswith("http") else f"{BASE}/case/{cid.lower()}/submission/{m.group(2)}"})
    return out


def parse_submission(page):
    """제출 페이지 → [{name, url}] (파일 저장소 주소만 — 같은 누리집 안 링크는 파일이 아니다)."""
    out, seen = [], set()
    for href in re.findall(r'href\s*=\s*"(https?://[^"]+)"', page or ""):
        if "/content/" not in href and not re.search(r"\.(?:pdf|docx?|xlsx?|zip)(?:$|\?)", href, re.I):
            continue
        if "trade-remedies.service.gov.uk" in href or href in seen:
            continue
        seen.add(href)
        out.append({"name": unquote(href.split("?")[0].rsplit("/", 1)[-1])[:140], "url": html.unescape(href)})
    return out


def classify(row):
    """(등급, 이유, 출입처 이름들). 본문을 읽기 전 판단 — 제목과 낸 곳만 본다."""
    who = companies_in(row["party"])
    title = row["title"]
    if TRA_PARTY.search(row["party"]):
        if TRA_A.search(title):
            return "A", "조사기관의 판단·쟁점 문서", who
        return ("B", "조사기관의 절차 문서", who) if TRA_B.search(title) else ("C", "조사기관의 일상 문서", who)
    for hit, label in ((bool(who), "출입처"), (bool(GOV.search(row["party"])), "한국 정부"), (bool(KR_GROUP.search(row["party"])), "한국 업계 단체")):
        if hit:
            return ("B", f"{label}가 낸 절차 문서(질문서 답변·등록)", who) if ROUTINE.search(title) else ("A", f"{label}가 낸 문서", who)
    return "C", "다른 당사자 문서", who


def snippets(text, names, limit=3):
    """출입처 이름이나 쟁점 낱말이 든 문장 — 이름이 든 문장 먼저, 3개까지(280자)."""
    sents = re.split(r"(?<=[.;])\s+(?=[A-Z(\"“])", re.sub(r"\s+", " ", text or ""))
    want = [rx for n, rx in beat_names() if n in names]
    good = [s for s in sents if 40 <= len(s) <= 900 and "....." not in s and "_____" not in s]
    named = [s for s in good if any(re.search(rx, s, re.I) for rx in want) or GOV.search(s)]
    pick = [s for s in named if KEY.search(s)][:limit]
    pick += [s for s in named if s not in pick][:limit - len(pick)]
    pick += [s for s in good if s not in pick and KEY.search(s)][:limit - len(pick)]
    order = {s: i for i, s in enumerate(good)}
    return [s[:280] + (" …" if len(s) > 280 else "") for s in sorted(pick, key=order.get)]


def pdf_text(data, limit=PDF_PAGES):
    import pypdf
    pdf = pypdf.PdfReader(io.BytesIO(data))
    return len(pdf.pages), " ".join((p.extract_text() or "") for p in pdf.pages[:limit])


def _get(get, url, timeout=45):
    r = get(url, headers=HEADERS, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        r.encoding = "utf-8"   # 헤더에 문자셋이 없어 Latin-1로 풀리면 따옴표가 깨진다(탐침 11-13)
    except Exception:  # noqa: BLE001 — 테스트용 응답
        pass
    return r


def read_detail(rec, *, get, budget, sleep):
    """제출 페이지의 파일 목록을 읽고, 읽을 만한 문서면 첫 PDF 본문에서 출입처 이름·쟁점 문장을 뽑는다. budget: {'pages', 'pdfs'}."""
    if budget["pages"] <= 0:
        rec["detail"] = "pending"
        return
    budget["pages"] -= 1
    try:
        files = parse_submission(_get(get, rec["url"]).text)
    except Exception as e:  # noqa: BLE001
        rec["detailError"] = f"제출 페이지 {str(e)[:50] or type(e).__name__}"
        return
    rec["fileList"] = files[:12]
    rec["detail"] = "ok"
    want_text = rec["tier"] in ("A", "B") or not ROUTINE.search(rec["title"])
    pdfs = [f for f in files if f["name"].lower().endswith(".pdf")]
    if not want_text or not pdfs or budget["pdfs"] <= 0:
        return
    budget["pdfs"] -= 1
    sleep(0.5)
    try:
        r = get(pdfs[0]["url"], headers={"User-Agent": UA}, timeout=120)
        if r.status_code != 200 or r.content[:5] != b"%PDF-":
            raise RuntimeError(f"HTTP {r.status_code}")
        if len(r.content) > MAX_PDF_BYTES:
            raise RuntimeError(f"파일이 큼({len(r.content) // 1_000_000}MB)")
        pages, text = pdf_text(r.content)
    except Exception as e:  # noqa: BLE001
        rec["pdfError"] = f"{pdfs[0]['name'][:40]}: {str(e)[:50] or type(e).__name__}"
        return
    rec["pdfPages"], rec["pdfFile"] = pages, pdfs[0]["name"]
    if len(re.sub(r"\s+", "", text)) < 200:
        rec["pdfError"] = "글자 없음(스캔 이미지일 수 있음)"
        return
    names = list(dict.fromkeys(rec.get("companies", []) + companies_in(text)))
    rec["mentions"] = [n for n in names if n not in rec.get("companies", [])]
    rec["govMention"] = bool(GOV.search(text))
    rec["snippets"] = snippets(text, names)
    # 다른 당사자 문서라도 본문에 출입처 이름이 나오면 B(11-10 단독의 근거 문서는 신청인 쪽 제출이었다)
    if rec["tier"] == "C" and rec["mentions"]:
        rec["tier"], rec["why"] = "B", "다른 당사자 문서에 출입처 이름"
    rec["companies"] = names


def event_of(rec, case, stamp):
    files = [f["name"] for f in rec.get("fileList") or []]
    text = f"{rec['party']} 제출 「{rec['title']}」(게시 {rec['published'] or '날짜 없음'})"
    if files:
        text += f" · 파일 {len(files)}개: {', '.join(files[:3])}{' 외' if len(files) > 3 else ''}"
    if rec.get("snippets"):
        text += " · 본문 대목 " + " / ".join(f"「{s}」" for s in rec["snippets"][:2])
    elif rec.get("pdfError"):
        text += f" · 본문 못 읽음({rec['pdfError']})"
    return {"id": f"trafile:{case['id']}:{rec['sid']}", "pageId": "trafile", "country": "영국", "caseId": case["id"],
            "label": f"영국 TRA 공개기록 · {case['id']} {case['commodity'] or case['title']}", "text": text, "url": rec["url"],
            "detectedAt": stamp, "tier": rec["tier"], "why": rec["why"], "companies": rec.get("companies", []), "party": rec["party"],
            "published": rec["published"]}


def collect(prev, now, *, get, sleep=time.sleep, extra_cases=()):
    """prev: 지난 doc['tra'] 또는 None. 돌려줌: (tra 구역, 새 이벤트, 점검 한 줄)."""
    stamp = now.isoformat(timespec="seconds")
    baseline = not prev
    prev = prev or {}
    check = {"source": "영국 TRA 공개기록", "status": "ok", "returned": 0}
    try:
        cases = parse_cases(_get(get, BASE + "/").text)
        if not cases:
            raise RuntimeError("목록 표 없음(형식 변경 의심)")
    except Exception as e:  # noqa: BLE001
        check.update(status="failed", error=f"목록 {str(e)[:60] or type(e).__name__}")
        return (dict(prev, stale=True) if prev else None), [], check
    watch = [c for c in cases if c["active"] and (KOREA.search(c["country"]) or KOREA.search(c["title"]) or c["id"] in extra_cases)][:MAX_CASES]
    seen = {k: set(v) for k, v in (prev.get("seen") or {}).items()}
    known = {d["id"]: d for d in prev.get("docs") or [] if isinstance(d, dict) and d.get("id")}
    floor = (now - dt.timedelta(days=FIRST_DAYS)).date().isoformat()
    budget = {"pages": PAGE_BUDGET, "pdfs": PDF_BUDGET}
    events, errors, out_cases, docs = [], [], [], dict(known)
    for case in watch:
        sleep(0.5)
        try:
            rows = parse_case_page(_get(get, case["url"]).text, case["id"])
        except Exception as e:  # noqa: BLE001
            errors.append(f"{case['id']} {str(e)[:40] or type(e).__name__}")
            old = next((c for c in prev.get("cases") or [] if c.get("id") == case["id"]), None)
            out_cases.append(dict(old or case, stale=True))
            continue
        first_case = case["id"] not in seen      # 새로 지켜보게 된 사건도 그 사건만 기준선
        had = seen.setdefault(case["id"], set())
        parties = sorted({r["party"] for r in rows})
        out_cases.append({**case, "rows": len(rows), "beatParties": sorted({n for p in parties for n in companies_in(p)}),
                          "govParty": any(GOV.search(p) for p in parties), "parties": len(parties)})
        fresh = [r for r in rows if r["sid"] not in had]
        # 못 읽고 넘긴 제출 페이지(pending)는 다음 실행이 이어 읽는다
        pending = [docs[f"tra:{case['id']}:{r['sid']}"] for r in rows if docs.get(f"tra:{case['id']}:{r['sid']}", {}).get("detail") == "pending"]
        for r in sorted(fresh, key=lambda x: x["published"], reverse=True):
            tier, why, who = classify(r)
            rec = {"id": f"tra:{case['id']}:{r['sid']}", "case": case["id"], **r, "tier": tier, "why": why, "companies": who, "firstSeen": stamp}
            announce = not (baseline or first_case) or (r["published"] and r["published"] >= floor)
            rec["isNew"] = bool(announce)
            if announce:
                read_detail(rec, get=get, budget=budget, sleep=sleep)
                if rec["tier"] in ("A", "B"):
                    events.append(event_of(rec, case, stamp))
            docs[rec["id"]] = rec
            had.add(r["sid"])
        for rec in pending:
            read_detail(rec, get=get, budget=budget, sleep=sleep)
            if rec.get("detail") == "ok" and rec["tier"] in ("A", "B"):
                events.append(event_of(rec, case, stamp))
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    kept = sorted((d for d in docs.values() if (d.get("published") or d.get("firstSeen", "")[:10]) >= keep_from),
                  key=lambda d: (d.get("published") or "", d.get("firstSeen") or ""), reverse=True)[:MAX_DOCS]
    for d in kept:
        if d.get("firstSeen") != stamp:
            d["isNew"] = False
    if errors:
        check.update(status="partial", error="; ".join(errors[:3]))
    check.update(returned=sum(c.get("rows", 0) for c in out_cases), cases=len(out_cases), newDocs=sum(1 for d in kept if d.get("firstSeen") == stamp and d.get("isNew")),
                 pagesRead=PAGE_BUDGET - budget["pages"], pdfsRead=PDF_BUDGET - budget["pdfs"])
    section = {"checkedAt": stamp, "baselineAt": prev.get("baselineAt") or stamp, "cases": out_cases, "docs": kept,
               "seen": {k: sorted(v)[-600:] for k, v in seen.items()},
               "rules": ["공개기록 문서는 당사자 주장이다 — 조사기관(TRA)의 판단이 아니다. 판정·세율은 조사기관 문서로 확인한다.",
                         "본문 대목은 첫 PDF 앞 40쪽에서 자동으로 뽑았다. 인용 전 원문을 연다. 비공개본은 올라오지 않는다.",
                         "나라 칸에 Korea가 든 진행 조사만 본다. 첫 실행은 기준선(최근 사흘 문서만 새 문서)."]}
    return section, events, check
