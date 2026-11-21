"""통합환경허가 정보공개 — 국립환경과학원 통합환경허가시스템(ieps.nier.go.kr) '정보공개 > 통합허가' 게시판의 출입처 사업장 글.

11-21 기자 "너 추천대로 멈추지말고 계속 업데이트". 환경오염시설법 제27조제5항에 따라 허가·변경허가를 받은 사업장의
'배출시설등 설치·운영허가 검토 결과서'를 공개하는 게시판이다. 제목 꼴(11-21 탐침):
  [통합허가, 무기화학]금호석유화학(주) 율촌CNT공장 정보공개(제0733-01호)
  [변경허가, 철강]현대제철(주)포항1공장 정보공개(제0526-02호)
  [연간보고서]현대제철(주)당진제철소_2023(2022년 기준)
변경허가 글의 검토 결과서 앞쪽에는 허가 이력(통합허가·변경허가·변경신고 날짜)과 변경 항목('배출시설 및 방지시설 추가'·
'폐수처리공정 변경' 등)이 적혀 있다 — 설비 증설·공정 변경의 공식 기록. 다만 공개는 허가 뒤 몇 달~몇 년 늦을 수 있다(허가일은 문서로 확인).

등급: 출입처 사업장의 변경허가 = B, 통합허가(첫 허가·전환) = C, 연간보고서는 저장하지 않는다. 관련 기업(효성중공업·일진전기) = C.
공개 로그에는 건수만 찍는다(회사·사업장 이름은 기자 전용 저장소로만).
"""
from __future__ import annotations

import datetime as dt
import html
import io
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "ieps_permits/v1"
BASE = "https://ieps.nier.go.kr"
LIST = BASE + "/web/board/7?pMENUMST_ID=176&page={}"
VIEW = BASE + "/web/board/7/{}/?pMENUMST_ID=176"
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research)"}
PAGES = 3            # 실행마다 앞 3쪽(한 쪽 10건, 주 20건 안팎 올라온다)
FIRST_PAGES = 5      # 첫 실행은 기준선
PDF_BUDGET = 2       # 검토 결과서 PDF는 수 MB(11-21 탐침: 227쪽 6.9MB) — 실행당 2건, 앞 8쪽만
PDF_PAGES = 8
PAUSE = 2.0
KEEP_DAYS = 365
SEEN_KEEP = 600

TITLE_RX = re.compile(r"^\[(?P<kind>[^,\]]+?)(?:\s*,\s*(?P<ind>[^\]]+?))?\]\s*(?P<site>.+?)\s*(?:정보\s*공개)?\s*"
                      r"(?:\((?P<no>제?\s*\d+(?:-\d+)?\s*호)\))?\s*(?:\(\d+\))?\s*$")
STRIP = [re.compile(p) for p in (r"\(주\)", r"㈜", r"주식회사", r"\(유\)", r"유한회사", r"\(재\)", r"\s+")]
# 영문 표기 → 공장등록 규칙(data/factory_watch.json)의 한글 이름
ALIAS = [(re.compile(r"^OCI(?!홀딩스)", re.I), "오씨아이"), (re.compile(r"^LS(?=전선|일렉트릭|엠앤엠)", re.I), "엘에스")]
CHANGE_LINE = re.compile(r"(?:배출시설|방지시설|배출구|오염물질|공정|시설|설비|생산|원료|연료).{0,30}(?:변경|추가|신설|증설|폐쇄|삭제|교체|설치)")
HISTORY_RX = re.compile(r"(20\d\d)\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2}|00)\s*\.?\s*<?\s*(통\s*합\s*허\s*가|변\s*경\s*허\s*가|변\s*경\s*신\s*고)")


def now_kst():
    return dt.datetime.now(KST).replace(microsecond=0)


def text_of(h):
    h = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def load_rules(path=ROOT / "data" / "factory_watch.json"):
    """공장등록 감시의 출입처 이름 규칙(앞에서부터 맞춤). '(관련)' 기업은 관련으로 따로 표시."""
    rules = []
    for c in json.loads(Path(path).read_text(encoding="utf-8")).get("companies", []):
        name = str(c.get("company") or "")
        if name and c.get("accept"):
            rules.append((name.replace("(관련)", ""), "(관련)" in name, re.compile(c["accept"])))
    return rules


RULES = load_rules()


def norm(site):
    s = site or ""
    for rx in STRIP:
        s = rx.sub("", s)
    for rx, ko in ALIAS:
        s = rx.sub(ko, s)
    return s


# 공장등록 규칙은 '포스코 + 사업장(8자 안) + 공장'을 받는다 — 이 게시판 사업장 이름은 '포스코퓨처엠(주) 광양공장'처럼 계열사 이름이 앞에 온다
AFFILIATE = re.compile(r"^포스코(?:퓨처엠|인터내셔널|이앤씨|엠텍|스틸리온|플로우|FLOW|DX|디엑스|씨앤씨|와이드|휴먼스|모빌리티솔루션|에이앤씨|건설|기술투자|그린|실리콘|케미칼|켐텍|아이씨티)"
                       r"|^현대(?:스틸파이프|비앤지스틸|IFC|아이에프씨|케미칼|오일터미널)|^(?:엘지|LG)(?:에너지솔루션|디스플레이|이노텍|전자)|^(?:에스케이|SK)(?:에너지|지오센트릭|온|인천석유화학|피유코어)"
                       r"|^롯데(?:정밀화학|엠시씨|이네오스)|^한화(?:토탈|임팩트|첨단소재)|^금호(?:피앤비|미쓰이)|^세아(?:베스틸|창원특수강|씨엠)|^고려아연(?:\S*자회사)|^영풍(?:정밀|전자)", re.I)


def beat_of(site, rules=None):
    """사업장 이름 → (회사, 관련 여부) 또는 (None, False)."""
    name = norm(site)
    if AFFILIATE.search(name):
        return None, False
    for comp, related, rx in rules or RULES:
        if rx.search(name):
            return comp, related
    return None, False


def parse_title(title):
    m = TITLE_RX.match(re.sub(r"\s+", " ", title or "").strip())
    if not m:
        return None
    kind = m.group("kind").strip()
    site = m.group("site").strip()
    if kind == "연간보고서":
        site = re.sub(r"_\d{4}.*$", "", site)
    return {"kind": kind, "industry": (m.group("ind") or "").strip(), "site": site,
            "no": re.sub(r"\s+", "", m.group("no") or "") or None}


def list_rows(page_html):
    """목록 → [{seq, title, date}] (게시판 글 번호·제목·등록일)."""
    out, seen = [], set()
    for row in re.findall(r"<tr\b.*?</tr>", page_html or "", re.S | re.I):
        a = re.search(r'href=["\'](?:[^"\']*?)/web/board/7/(\d+)/[^"\']*["\'][^>]*>(.*?)</a>', row, re.S | re.I)
        d = re.search(r"20\d\d-\d\d-\d\d", row)
        if a and d and a.group(1) not in seen:
            seen.add(a.group(1))
            out.append({"seq": a.group(1), "title": text_of(a.group(2)), "date": d.group(0)})
    return out


def files_of(view_html):
    return [(html.unescape(h), text_of(t)) for h, t in re.findall(r'href=["\'](/jfile/readDownloadFile\.do\?[^"\']+)["\'][^>]*>(.*?)</a>',
                                                                    view_html or "", re.S | re.I)]


def pdf_text(raw, pages=PDF_PAGES):
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(raw))
    return "\n".join((rd.pages[i].extract_text() or "") for i in range(min(pages, len(rd.pages)))), len(rd.pages)


def changes_of(text):
    """검토 결과서 앞쪽 → (허가 이력 [(날짜, 종류)], 변경 항목 줄 5개까지)."""
    hist = []
    for y, mo, d, kind in HISTORY_RX.findall(text or ""):
        k = re.sub(r"\s+", "", kind)
        item = (f"{y}-{int(mo):02d}" + (f"-{int(d):02d}" if d != "00" else ""), k)
        if item not in hist:
            hist.append(item)
    lines = []
    for raw in (text or "").splitlines():
        l = re.sub(r"^\s*(?:\d+\s*[.)]|[가-하]\s*\.|[□○■▢·-])\s*", "", raw.strip())
        l = re.sub(r"\s+", " ", l)
        if 4 <= len(l) <= 80 and CHANGE_LINE.search(l) and l not in lines and not re.search(r"(?:법률|시행규칙|제\d+조)", l):
            lines.append(l)
        if len(lines) >= 5:
            break
    return hist[:8], lines


def tier_of(kind, related):
    if related:
        return "C"
    if kind.startswith("변경"):
        return "B"
    return "C"


def line_of(x):
    ind = f"({x['industry']})" if x.get("industry") else ""
    no = f" · 허가번호 {x['no']}" if x.get("no") else ""
    bits = [f"통합환경허가 정보공개 · {x['kind']}{ind} · {x['site']}{no} · 게시 {x['date']}"]
    if x.get("history"):
        bits.append("허가 이력(검토 결과서): " + ", ".join(f"{d} {k}" for d, k in x["history"][:5]))
    if x.get("changes"):
        bits.append("변경 항목(검토 결과서 앞쪽): " + " / ".join(x["changes"][:4]))
    if x.get("pdfError"):
        bits.append(f"검토 결과서 못 읽음({x['pdfError']})")
    bits.append("게시는 허가 뒤 늦을 수 있다 — 허가일·변경 내용·규모는 결과서 원문과 회사로 확인")
    return " · ".join(bits)


def run(now, previous=None, *, get=None, sleep=time.sleep, rules=None, read_pdf=None):
    if get is None:
        import requests
        session = requests.Session()
        session.headers.update(UA)
        get = session.get
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    first = not prev.get("baselineAt")
    seen = list(prev.get("seen") or [])
    seen_set = set(seen)
    items = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)]
    rows, err, pages = [], None, 0
    for n in range(1, (FIRST_PAGES if first else PAGES) + 1):
        if n > 1:
            sleep(PAUSE)
        try:
            r = get(LIST.format(n), timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            got = list_rows(r.text)
        except Exception as e:  # noqa: BLE001 — 실패는 0건이 아니라 미확인
            err = f"{n}쪽 {type(e).__name__}: {str(e)[:60]}"
            break
        pages += 1
        if not got:
            if n == 1:
                err = "목록 0줄(형식 변경 의심)"
            break
        rows += got
        if not first and all(x["seq"] in seen_set for x in got):
            break
    budget = PDF_BUDGET
    counts = {"rows": len(rows), "new": 0, "beat": 0, "events": 0, "pdf": 0}
    for row in rows:
        if row["seq"] in seen_set:
            continue
        seen.append(row["seq"])
        seen_set.add(row["seq"])
        counts["new"] += 1
        t = parse_title(row["title"])
        if not t or t["kind"] == "연간보고서":
            continue
        comp, related = beat_of(t["site"], rules)
        if not comp:
            continue
        counts["beat"] += 1
        x = {"id": f"ieps:{row['seq']}", "company": comp, "related": related, **t, "date": row["date"], "title": row["title"][:200],
             "url": VIEW.format(row["seq"]), "tier": tier_of(t["kind"], related), "firstSeen": stamp, "baseline": first}
        # 결과서는 출입처 글이면 등급과 상관없이 읽는다(11-21 격리 실행: 최근 50줄 중 출입처 3건이 모두 통합허가 C — 이력·변경 줄이 있어야 새 공장인지 볼 수 있다)
        if not first and budget > 0 and not related:
            budget -= 1
            try:
                sleep(PAUSE)
                v = get(x["url"], timeout=30)
                files = files_of(v.text) if v.status_code == 200 else []
                x["files"] = [name[:120] for _, name in files][:4]
                pdf = next((h for h, name in files if name.lower().endswith(".pdf")), None)
                if pdf:
                    sleep(PAUSE)
                    f = get(BASE + pdf, timeout=90, headers={**UA, "Referer": x["url"]})
                    raw = getattr(f, "content", b"") or b""
                    if f.status_code == 200 and raw[:5] == b"%PDF-":
                        text, n_pages = (read_pdf or pdf_text)(raw)
                        x["history"], x["changes"] = changes_of(text)
                        x["pdfPages"] = n_pages
                        counts["pdf"] += 1
                    else:
                        x["pdfError"] = f"HTTP {f.status_code}" if f.status_code != 200 else "PDF 아님"
                else:
                    x["pdfError"] = "첨부 PDF 없음"
            except Exception as e:  # noqa: BLE001
                x["pdfError"] = f"{type(e).__name__}"[:40]
        items[x["id"]] = x
        if not first:
            events.append({"id": x["id"], "tier": x["tier"], "kind": f"통합환경허가 {x['kind']}", "company": comp, "site": x["site"],
                           "industry": x["industry"], "no": x["no"], "date": x["date"], "url": x["url"], "text": line_of(x),
                           "detectedAt": stamp})
            counts["events"] += 1
    keep = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    status = "failed" if err and not rows else "partial" if err else "ok"
    checks = [{"source": "통합환경허가 정보공개(게시판)", "status": status, "returned": len(rows), "pages": pages,
               **({"error": err} if err else {})}]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "baselineAt": prev.get("baselineAt") or stamp,
            "checks": checks, "counts": counts, "seen": seen[-SEEN_KEEP:],
            "items": sorted([x for x in items.values() if str(x.get("date") or "") >= keep], key=lambda x: (x["date"], x["id"]), reverse=True),
            "events": [e for e in events if str(e.get("detectedAt") or "") >= (now - dt.timedelta(days=60)).isoformat()],
            "rules": ["국립환경과학원 통합환경허가시스템 '정보공개 > 통합허가' 게시판(환경오염시설법 제27조제5항 공개)의 출입처 사업장 글만. 계열사·이름이 다른 회사는 빼고, 효성중공업·일진전기는 관련(C).",
                      "변경허가 = B(설비·공정 변경의 공식 기록), 통합허가(첫 허가·전환) = C, 연간보고서는 저장하지 않는다.",
                      "게시는 허가 뒤 몇 달~몇 년 늦을 수 있다 — 허가일·변경 내용·생산 규모는 검토 결과서 원문과 회사로 확인. 결과서 앞 8쪽에서 뽑은 이력·변경 줄은 자동 추출이다.",
                      "조회 실패는 0건이 아니라 미확인."]}


def main():
    import private_store
    now = now_kst()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("ieps-permits", token)
        except private_store.StoreError as e:
            print(f"::warning title=ieps-state::이전 상태 조회 실패({e}) — 기준선부터 다시")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(now, previous)
    c = doc["counts"]
    print(f"::notice title=ieps-permits::상태 {doc['status']} · 목록 {c['rows']}줄 · 새 글 {c['new']} · 출입처 {c['beat']} · 이벤트 {c['events']}"
          f" · 결과서 읽음 {c['pdf']} · 저장 {len(doc['items'])}{' · 첫 실행 기준선' if not previous else ''}")
    if not token:
        print("::warning title=ieps-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("통합환경허가 게시판 조회 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("ieps-permits", doc, token)
    print(f"::notice title=ieps-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
