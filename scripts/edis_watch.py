"""USITC EDIS(문서 정보 시스템) — 한국산 제소·출입처가 당사자인 문서·출입처 이름이 표지에 나오는 337 제소장을 접수 다음 날 아침에 잡는다.

데이터 웹서비스(EDIS Data Web Service Guide v1.1, 2024-06): https://edis.usitc.gov/data
- 문서·조사 기본 정보(제목·제출처·당사자 onBehalfOf·접수 시각)는 로그인 없이 받는다(탐침 10-31: XML results/documents/document).
- 첨부(PDF) 내려받기는 EDIS API 토큰이 있어야 한다(Authorization: Bearer, EDIS 로그인 → 이름 아래 'API Token Generator',
  14일 뒤 만료 — 탐침 10-31: 토큰 없이 401, 토큰으로 41쪽 재검토 청원서 200).
- 전체 최근 문서 목록은 접수 시각 역순(pageSize 100). 탐침 10-31: 300건이 10-28 08:45~10-30 17:02(하루 130건 안팎),
  절반이 비공개, 191건이 제출처 USITC(질문서·조사 자료 포함 — 제출처만으로 위원회 결정이라 보지 않는다).
운영 근거: 퍼스트솔라 337-TA-1494(TOPCon 특허) 종결 예비 결정에 한화솔루션·한화큐셀 등 피제소인이 10-07·10-21 재검토를 청원했고
10-29 위원회가 재검토 여부 결정 기한을 늘렸다 — 10-Q에는 청원자 이름이 없었고 국내 보도는 9월 '철회 수순'에서 멈췄다.
결과는 기자 전용 저장소(trade-remedy의 edis 구역)로만. 공개 로그는 건수만.
"""
from __future__ import annotations

import base64
import datetime as dt
import html
import io
import json
import re
import time
import xml.etree.ElementTree as ET

BASE = "https://edis.usitc.gov/data"
UA = "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"
PAGE_SIZE = 100
MAX_PAGES = 8         # 금요일 문서를 월요일 아침에 한꺼번에 읽어도 남게(하루 130건 안팎)
FIRST_DAYS = 2        # 첫 실행은 최근 이틀(+지켜보는 조사 최근 문서)을 기준선으로
KEEP_DAYS = 60
SEEN_MAX = 6000
PDF_BUDGET = 6
COMPLAINT_BUDGET = 4
MAX_PDF_BYTES = 25_000_000
WATCH_MAX = 15
WATCH_IDLE_DAYS = 180
TOKEN_WARN_DAYS = 3
SEED_WATCH = ("337-1494",)
KOREA = re.compile(r"\bKorea\b", re.I)
FIELDS = ("id", "documentType", "documentTitle", "securityLevel", "investigationNumber", "investigationPhase", "investigationStatus",
          "investigationTitle", "investigationType", "firmOrganization", "filedBy", "onBehalfOf", "documentDate", "officialReceivedDate")
ROUTINE = re.compile(r"PO Subscription|Protective Order|Appearance|Returned Mail|Certificate of Service|Withdrawal of Counsel|"
                     r"Exhibit|Errat|Corrections Request|Cover Letter|Service List|Proof of Service|Witness List|Questionnaire|"
                     r"Research Material|Work Sheet|Voting Sheet|Import Statistics|Verification Report|Telephone/Meeting|Transcript", re.I)
# 위원회·행정판사 결정 문서 종류(제출처 USITC라도 질문서·조사 자료·OUII 서면은 아님)
DECISION_TYPE = re.compile(r"^(?:Notice|Order|ID/RD|Opinion|Views|Consolidated Reports And Views|Determination)\b", re.I)
# 판사의 절차 명령(Order)은 337 사건 하나에 수십 건(탐침 10-31: 337-1494 최근 100건 중 21건) — 종결·배제·제재 같은 결론 명령만 B
WEIGHTY = re.compile(r"^(?:ID/RD|Opinion|Views|Consolidated|Determination|Order,\s*Commission)", re.I)
# 공고(Notice)는 위원회 결정·개시·종결 공고만 — 판사의 '대리 자문관 교체 안내' 같은 절차 공고는 C(운영 10-31 첫 실행: 2건 B)
WEIGHTY_NOTICE = re.compile(r"Commission|determin|terminat|institut|exclusion|review|target date|remand", re.I)
# 위원회 조사 스태프(OUII)의 서면은 제출처가 USITC여도 결정이 아니다(운영 10-31: 'Commission Investigative Staff's Notice of Prior Art'가 B)
STAFF = re.compile(r"Investigative Staff|\bOUII\b|Office of Unfair Import", re.I)
WEIGHTY_ORDER = re.compile(r"terminat|exclusion|cease and desist|sanction|summary determination|default|\bstay|dismiss|withdraw|settle|"
                           r"consent|remand|violation", re.I)
FINDING_TYPE = re.compile(r"Opinion|Views|Determination|ID/RD - Final", re.I)
STARTS = re.compile(r"^(?:Petition|Complaint)\b", re.I)
SUBSTANTIVE = re.compile(r"Complaint|Petition|Motion|Brief|Response|Reply|Comments|Submission|Request|Statement|Answer|Opposition|"
                         r"Correspondence", re.I)
SNIP = re.compile(r"with(?:out)? prejudice|relief|respectfully (?:request|submit|move)|should (?:be )?(?:deni|grant|revers|review)|"
                  r"refil|terminat|exclusion order|cease and desist|public interest|settle|(?:has|have) determined|determines? to|"
                  r"extend(?:s|ed|ing)? the (?:date|deadline|target)", re.I)


def beat_names():
    from trade_remedy_watch import BEAT_NAMES
    return BEAT_NAMES


def companies_in(text):
    return [name for name, rx in beat_names() if re.search(rx, text or "", re.I)]


def unesc(v):
    """EDIS 값은 HTML 이스케이프가 겹쳐 온다(탐침: XML 해석 뒤에도 &amp; 11건)."""
    return html.unescape(html.unescape(v or "")).strip()


def _local(tag):
    return tag.split("}")[-1]


def parse_docs(xml_text):
    out = []
    for d in ET.fromstring(xml_text).iter():
        if _local(d.tag) != "document":
            continue
        got = {_local(c.tag): c.text for c in d}
        rec = {k: unesc(got.get(k)) for k in FIELDS}
        if rec["id"]:
            out.append(rec)
    return out


def token_expiry(token):
    """JWT의 exp(서명 검증 없이 읽기만). 못 읽으면 None."""
    try:
        body = token.split(".")[1]
        exp = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))).get("exp")
        return dt.datetime.fromtimestamp(int(exp), dt.timezone.utc) if exp else None
    except (IndexError, ValueError, TypeError, AttributeError):
        return None


def caps(s):
    """사건 표제·문서 제목(대문자 덩어리)은 내용이 아니다(운영 10-31: 발췌 첫 줄이 표제)."""
    letters = [c for c in s if c.isalpha()]
    return len(letters) > 20 and sum(c.isupper() for c in letters) / len(letters) > 0.5


def snippets(text, names):
    """요청·종결·결정 낱말이 든 문장을 먼저, 모자라면 출입처 이름이 든 문장 — 3개까지(280자). 표지·목차 덩어리는 건너뜀."""
    sents = re.split(r"(?<=[.;])\s+(?=[A-Z(\"“])", re.sub(r"\s+", " ", text or ""))
    want = [rx for n, rx in beat_names() if n in names]
    good = [s for s in sents if 40 <= len(s) <= 900 and "....." not in s and "_____" not in s and "…" * 3 not in s and not caps(s)]
    pick = [s for s in good if SNIP.search(s)][:3]
    if len(pick) < 3:
        pick += [s for s in good if s not in pick and any(re.search(rx, s, re.I) for rx in want)][:3 - len(pick)]
    order = {s: i for i, s in enumerate(good)}
    return [s[:280] + (" …" if len(s) > 280 else "") for s in sorted(pick, key=order.get)]


def pdf_pages(data, limit=60):
    import pypdf
    pdf = pypdf.PdfReader(io.BytesIO(data))
    return len(pdf.pages), [(p.extract_text() or "") for p in pdf.pages[:limit]]


def is_decision(rec):
    return (rec["firmOrganization"].strip().upper() == "USITC" and bool(DECISION_TYPE.search(rec["documentType"]))
            and not STAFF.search(rec["documentTitle"] + " " + rec["documentType"]))


def is_weighty(rec):
    if re.match(r"Notice", rec["documentType"], re.I):
        return bool(WEIGHTY_NOTICE.search(rec["documentTitle"]))
    return bool(WEIGHTY.search(rec["documentType"]) or WEIGHTY_ORDER.search(rec["documentTitle"]))


def party_hits(on_behalf):
    """당사자 목록에서 출입처로 잡힌 법인 이름(공동 피제소인 20여 곳을 한 줄에 적어 출입처가 잘려 안 보였다 — 운영 10-31)."""
    hits = []
    for _, rx in beat_names():
        for m in re.finditer(rf"(?:{rx})[^,;&]{{0,40}}(?:,\s*(?:Inc|Ltd|LLC|Corp|Co|GmbH|S\.A)\.?)*", on_behalf or "", re.I):
            name = m.group(0).strip(" ,;")
            if name and name not in hits:
                hits.append(name)
    return hits[:6]


def is_sec337(rec):
    return rec["investigationType"].replace(" ", "").lower().startswith("sec337")


def is_new_complaint(rec):
    return is_sec337(rec) and rec["documentType"].strip().lower() == "complaint" and rec["securityLevel"].lower() == "public"


def classify(rec, watched):
    """(등급, 이유, 출입처 이름들). 등급 None이면 관련 없음.
    A: 제목에 Korea가 든 조사의 제소장·청원(조사 개시). B: 출입처가 당사자인 서면, 지켜보는 조사·출입처 이름이 든 위원회·판사 결정,
    한국 조사의 위원회 판정. C: 관련은 있으나 일상(출석 통지·보호명령·질문서·상대방 서면·한국 조사 일정 공고)."""
    who = companies_in(" ".join([rec["onBehalfOf"], rec["firmOrganization"], rec["documentTitle"]]))
    korea = bool(KOREA.search(rec["investigationTitle"]))
    watch = rec["investigationNumber"] in watched
    kind = rec["documentType"] + " " + rec["documentTitle"]
    routine = bool(ROUTINE.search(rec["documentType"]))
    decision = is_decision(rec)
    if korea and not decision and not routine and STARTS.search(rec["documentType"]):
        return "A", "한국산 조사 제소장·청원", who
    if who and not routine and not decision and SUBSTANTIVE.search(kind):
        return "B", "출입처가 당사자인 서면", who
    if decision and (watch or who) and not routine and is_weighty(rec):
        return "B", "지켜보는 조사의 위원회·판사 결정·공고", who
    if decision and korea and FINDING_TYPE.search(kind):
        return "B", "한국 조사 위원회 판정", who
    if who or korea or watch:
        return "C", "관련 일상 문서", who
    return None, None, who


def _received(docs):
    return [d["officialReceivedDate"] for d in docs if d["officialReceivedDate"]]


def fetch_pdf(doc_id, *, get, headers, auth, limit=60):
    """(쪽수, 쪽별 본문, 오류, 토큰 거부 여부)."""
    a = get(f"{BASE}/attachment/{doc_id}", headers=headers, timeout=60)
    if a.status_code != 200:
        return None, None, f"첨부 목록 HTTP {a.status_code}", False
    uri = re.search(r"<downloadUri>(.*?)</downloadUri>", a.text or "", re.S)
    if not uri:
        return None, None, "첨부 없음", False
    size = re.search(r"<fileSize>(\d+)</fileSize>", a.text or "")
    if size and int(size.group(1)) > MAX_PDF_BYTES:
        return None, None, f"첨부가 큼({int(size.group(1)) // 1_000_000}MB) — 원문 링크로 확인", False
    f = get(unesc(uri.group(1)), headers=auth, timeout=120)
    if f.status_code == 401:
        return None, None, "토큰 거부(HTTP 401)", True
    if f.status_code != 200 or f.content[:5] != b"%PDF-":
        return None, None, f"내려받기 HTTP {f.status_code}", False
    n, pages = pdf_pages(f.content, limit)
    return n, pages, None, False


def collect(prev, now, *, get, token="", watch=SEED_WATCH, sleep=time.sleep):
    """prev: 지난 doc['edis'] 또는 None. 돌려줌: (edis 구역, 새 이벤트, 점검 한 줄)."""
    stamp = now.isoformat(timespec="seconds")
    baseline = not prev
    prev = prev or {}
    headers = {"User-Agent": UA, "Accept": "application/xml"}
    seen = set(prev.get("seen") or [])
    known = {x["id"]: x for x in prev.get("docs") or [] if isinstance(x, dict) and x.get("id")}
    watched = dict(prev["watched"]) if isinstance(prev.get("watched"), dict) else {}
    for inv in watch:
        watched.setdefault(inv, "seed")
    floor = prev.get("lastReceived") or (now - dt.timedelta(days=FIRST_DAYS)).strftime("%Y/%m/%d %H:%M:%S")
    errors, listed, pages = [], [], 0
    for p in range(1, MAX_PAGES + 1):
        try:
            r = get(f"{BASE}/document", params={"pageNumber": p, "pageSize": PAGE_SIZE}, headers=headers, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            docs = parse_docs(r.text)
        except Exception as e:  # noqa: BLE001
            errors.append(f"목록 {p}쪽 {str(e)[:60] or type(e).__name__}")
            break
        pages = p
        listed += docs
        if not docs or min(_received(docs) or [""]) <= floor:  # 지난 실행의 마지막 문서까지 닿음
            break
        sleep(0.5)
    reached = bool(listed) and min(_received(listed) or [""]) <= floor

    def note_watch(d):
        inv = d["investigationNumber"]
        if inv and is_sec337(d) and companies_in(" ".join([d["onBehalfOf"], d["documentTitle"]])):
            fresh = inv not in watched
            watched[inv] = "seed" if watched.get(inv) == "seed" else max(watched.get(inv) or "", d["officialReceivedDate"])
            return fresh
        return False

    added = {d["investigationNumber"] for d in listed if note_watch(d)}
    # 지켜보는 조사의 최근 문서: 첫 실행·목록 공백 때는 전부, 평소엔 이번에 새로 지켜보게 된 조사만(과거 맥락 채우기)
    ask = sorted(watched, key=lambda k: (watched[k] == "seed", watched[k]), reverse=True)[:WATCH_MAX] if baseline or not reached else sorted(added)
    got = list(listed)
    for inv in ask[:WATCH_MAX]:
        try:
            r = get(f"{BASE}/document", params={"investigationNumber": inv, "pageNumber": 1, "pageSize": PAGE_SIZE},
                    headers=headers, timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            got += parse_docs(r.text)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{inv} {str(e)[:40] or type(e).__name__}")
        sleep(0.5)
    by_id = {}
    for d in got:
        by_id.setdefault(d["id"], d)
    exp = token_expiry(token) if token else None
    token_note = None
    if not token:
        token_note = "EDIS_API_TOKEN 미설정 — 첨부 본문·337 제소장 피제소인 미확인(기본 정보만)"
    elif exp and exp <= now:
        token_note = f"EDIS 토큰 만료({exp.date()}) — EDIS 로그인 → 이름 아래 'API Token Generator'에서 다시 발급"
    # 다운로드에 Accept: application/xml을 붙이면 406(탐침 29) — 토큰과 UA만
    auth = {"User-Agent": UA, "Authorization": f"Bearer {token}"} if token and not token_note else None
    out, a_invs, read = dict(known), {x["investigationNumber"] for x in known.values() if x.get("tier") == "A"}, 0
    for rec in out.values():  # 저장된 문서: 결정 문서 기준을 좁힌 뒤의 등급·당사자 출입처 표기(원래 값은 그대로 두고 표시용만)
        if rec.get("tier") == "B" and rec.get("why") == "지켜보는 조사의 위원회·판사 결정·공고" and not (is_decision(rec) and is_weighty(rec)):
            rec.update(tier="C", why="관련 일상 문서", retiered="B")
        if "partyHits" not in rec:
            rec["partyHits"] = party_hits(rec.get("onBehalfOf"))
        if any(caps(x) for x in rec.get("snippets") or []):
            rec["snippets"] = [x for x in rec["snippets"] if not caps(x)]
    complaints = []
    for d in sorted(by_id.values(), key=lambda x: x["officialReceivedDate"]):
        if d["id"] in seen:
            continue
        tier, why, who = classify(d, watched)
        if not tier:
            if is_new_complaint(d) and auth:
                complaints.append(d)
            continue
        seen.add(d["id"])
        inv = d["investigationNumber"]
        if tier == "A" and inv in a_invs:
            tier, why = "C", "같은 조사의 추가 제소 서류"
        if tier == "A":
            a_invs.add(inv)
        out[d["id"]] = {**d, "tier": tier, "why": why, "companies": who, "firstSeen": stamp, "url": f"{BASE}/document/{d['id']}",
                        "isNew": not baseline and d["officialReceivedDate"] >= floor, "partyHits": party_hits(d["onBehalfOf"])}
    # 새 337 제소장: 표지(앞 3쪽)에 출입처 이름이 있으면 피제소인 후보(A), 본문 앞쪽에만 있으면 B — 피제소인 여부는 원문 확인
    scanned = 0
    for d in sorted(complaints, key=lambda x: x["officialReceivedDate"], reverse=True)[:COMPLAINT_BUDGET]:
        seen.add(d["id"])
        try:
            n, pages_text, err, denied = fetch_pdf(d["id"], get=get, headers=headers, auth=auth, limit=20)
        except Exception as e:  # noqa: BLE001
            n, pages_text, err, denied = None, None, str(e)[:60] or type(e).__name__, False
        sleep(0.5)
        if denied:
            token_note = "EDIS 토큰 거부(HTTP 401, 만료 가능) — 'API Token Generator'에서 다시 발급"
            seen.discard(d["id"])
            break
        if err:
            seen.discard(d["id"])  # 다음 실행에 다시
            continue
        scanned += 1
        cover = companies_in(" ".join(pages_text[:3]))
        later = [c for c in companies_in(" ".join(pages_text[3:])) if c not in cover]
        if not cover and not later:
            continue
        tier, why = ("A", "337 제소장 표지에 출입처 이름(피제소인 후보 — 원문 확인)") if cover else ("B", "337 제소장 본문에 출입처 이름(역할 미확인)")
        who = cover + later
        watched[d["investigationNumber"]] = max(watched.get(d["investigationNumber"]) or "", d["officialReceivedDate"])
        body = " ".join(pages_text)
        out[d["id"]] = {**d, "tier": tier, "why": why, "companies": who, "firstSeen": stamp, "url": f"{BASE}/document/{d['id']}",
                        "isNew": not baseline and d["officialReceivedDate"] >= floor, "pages": n, "snippets": snippets(body, who),
                        "partyHits": party_hits(d["onBehalfOf"])}
        read += 1
    # 첨부 본문(공개 문서만): 이번에 처음 본 A·B 문서 — 출입처가 낸 서면 먼저, 최근 것부터
    todo = [x for x in out.values() if x["firstSeen"] == stamp and x["tier"] in ("A", "B") and "pages" not in x
            and x["securityLevel"].lower() == "public"]
    todo.sort(key=lambda x: x["officialReceivedDate"], reverse=True)
    todo.sort(key=lambda x: (x["tier"], not x["companies"]))
    budget = PDF_BUDGET * 2 if baseline else PDF_BUDGET
    for rec in todo[:budget] if auth and not token_note else []:
        try:
            n, pages_text, err, denied = fetch_pdf(rec["id"], get=get, headers=headers, auth=auth)
        except Exception as e:  # noqa: BLE001
            n, pages_text, err, denied = None, None, str(e)[:60] or type(e).__name__, False
        sleep(0.5)
        if denied:
            token_note = "EDIS 토큰 거부(HTTP 401, 만료 가능) — 'API Token Generator'에서 다시 발급"
            rec["bodyError"] = "토큰 거부"
            break
        if err:
            rec["bodyError"] = err
            continue
        rec["pages"], rec["snippets"] = n, snippets(" ".join(pages_text), rec["companies"])
        read += 1
    events = []
    for rec in sorted(out.values(), key=lambda x: x["officialReceivedDate"]):
        if rec["firstSeen"] != stamp or not rec["isNew"] or rec["tier"] not in ("A", "B"):
            continue
        hits = rec.get("partyHits") or []
        party = ("" if not rec["onBehalfOf"] or is_decision(rec) else
                 f"공동 당사자 중 출입처 {'; '.join(hits)}" if hits and len(rec["onBehalfOf"]) > 200 else rec["onBehalfOf"])
        body = f" · 본문 발췌: {' / '.join(rec['snippets'])}" if rec.get("snippets") else ""
        events.append({"id": f"edis:{rec['id']}", "pageId": "edis", "country": "미국", "tier": rec["tier"],
                       "label": f"USITC {rec['investigationNumber']} {rec['documentType']}"[:120],
                       "text": (f"{rec['documentTitle']} — 제출 {rec['firmOrganization'] or rec['filedBy']}"
                                f"{'(당사자 ' + party[:200] + ')' if party else ''} · 접수 {rec['officialReceivedDate']}"
                                f" · 사건 「{rec['investigationTitle'][:120]}」 · {rec['why']}{body}")[:1100],
                       "companies": rec["companies"], "url": rec["url"], "detectedAt": stamp})
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    docs = sorted((x for x in out.values() if str(x.get("firstSeen")) >= keep), key=lambda x: x["officialReceivedDate"], reverse=True)[:500]
    idle = (now - dt.timedelta(days=WATCH_IDLE_DAYS)).strftime("%Y/%m/%d")
    watched = {k: v for k, v in watched.items() if v == "seed" or v >= idle}
    last = max(_received(listed) + [prev.get("lastReceived") or ""]) or None
    warn = None
    if exp and not token_note and exp - now <= dt.timedelta(days=TOKEN_WARN_DAYS):
        warn = f"EDIS 토큰 {exp.date()} 만료 예정 — 'API Token Generator'에서 다시 발급해 GitHub 비밀값 EDIS_API_TOKEN 교체"
    gap = None if reached or baseline or errors else f"최근 {pages}쪽 안에 지난 실행 시각이 없음 — 그 사이 일부 미확인"
    left = len(complaints) - scanned if auth else len(complaints)
    notes = [n for n in (token_note, warn, gap, f"337 제소장 {left}건 본문 미확인(다음 실행)" if left > 0 and auth else None) if n]
    status = "failed" if errors and not listed else "partial" if errors or gap or token_note else "ok"
    check = {"source": "USITC EDIS 문서", "status": status, "returned": len(by_id), "pages": pages, "bodiesRead": read,
             **({"error": "; ".join(errors[:3] + notes)[:300]} if errors or notes else {})}
    doc = {"checkedAt": stamp, "lastReceived": last, "docs": docs, "watched": watched, "seen": sorted(seen)[-SEEN_MAX:],
           "tokenExpires": exp.isoformat() if exp else None, "tokenNote": token_note or warn,
           "baselineSince": prev.get("baselineSince") or stamp, "rules": RULES}
    return doc, events, check


RULES = ["USITC EDIS는 제출된 서류 목록이다. 제소장·청원·서면은 당사자 주장이고, 결론은 위원회·행정판사 문서(결정·의견·명령)로 확인한다.",
         "A: 제목에 Korea가 든 조사의 제소장·청원(조사 개시, 관보 고시보다 앞섬), 표지에 출입처 이름이 든 337 제소장. "
         "B: 출입처가 당사자(onBehalfOf)인 서면, 출입처가 당사자인 337 조사의 위원회·판사 결정·공고, 한국 조사의 위원회 판정. "
         "출석 통지·보호명령·질문서·상대방 서면·일정 공고는 C(목록에만).",
         "출입처 판별은 당사자·제출처·제목·제소장 앞쪽의 영문 회사명 일치다. 이름이 나와도 피제소인·제3자·고객 중 무엇인지는 원문에서 확인한다. "
         "로펌 한 곳이 여러 피제소인을 함께 대리하면 회사별 입장 차이도 원문에서 확인한다.",
         "본문 발췌는 공개본 첫 첨부에서 요청·종결·결정 낱말이나 출입처 이름이 든 문장이다(EDIS API 토큰 필요, 14일마다 다시 발급). "
         "비공개(Confidential) 문서는 본문을 읽지 않는다.",
         "조회 실패·토큰 만료는 0건이 아니라 미확인."]
