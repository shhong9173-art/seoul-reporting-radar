"""인도 상장 법인 공시 — 현대차 인도법인(Hyundai Motor India Limited, NSE 상장)의 거래소 공시(기자 전용 저장소 india-filings).

- 원천: NSE 공시 RSS(nsearchives.nseindia.com/content/RSS/Online_announcements.xml, 전 상장사 최신 공시 약 1,400건).
  11-03 탐침 141~142: www.nseindia.com robots.txt는 전체 허용, nsearchives는 robots.txt 없음(404). 정직한 이름(UA)으로 열림.
  BSE API는 Access Denied(403)라 쓰지 않는다(머리글 바꿔 우회하지 않음).
- 항목: 회사 이름(title)·첨부 PDF 주소(link)·설명('… |SUBJECT: 공시 종류')·게시 시각(IST, '03-Nov-2026 17:30:45').
  11-03 실제 항목: 「Hyundai Motor India Limited has informed the Exchange about Transcript |SUBJECT: Analysts/Institutional Investor Meet…」.
- 등급: 인수·합병·설비·공장·생산능력·로열티·특수관계 거래 낱말 A, 이사회 결과·보도자료·임원 변경·신용등급·규정 30조 공시 등 B,
  녹취록·거래 제한 기간·신문 공고·애널리스트 미팅 안내 등 C. A·B는 첨부 PDF 첫머리 글자(600자)를 붙인다(하루 몇 건).
- 첫 실행은 기준선(목록에만, 이벤트 없음). RSS는 최신 약 1,400건뿐이라 실행 사이에 밀려난 공시는 못 볼 수 있다(덮는 시간 폭을 기록).
- 현대차 인도법인은 현대차 자회사(별도 상장사)다 — 레이더에는 '현대차(인도 법인)'으로 적고, 기사에는 인도법인으로 구분해 쓴다.
- 결과는 기자 전용 저장소로만. 공개 로그는 건수만. 조회 실패는 0건이 아니라 미확인.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
SCHEMA = "india_filings/v1"
RSS = "https://nsearchives.nseindia.com/content/RSS/Online_announcements.xml"
UA = {"User-Agent": "seoul-reporting-radar (newsroom research; exchange announcements)"}
PAUSE = 3.0
KEEP_DAYS = 120
PDF_MAX = 4          # 한 실행에 첨부 PDF를 읽는 최대 수
COMPANIES = [("현대차(인도 법인)", re.compile(r"^Hyundai Motor India\b", re.I))]
A_WORDS = re.compile(r"acqui|amalgamat|merger|scheme of arrangement|expansion|capacity|new plant|plant|commencement of (?:commercial )?production|"
                     r"capital expenditure|capex|royalt|related party|joint venture|investment in", re.I)
C_WORDS = re.compile(r"transcript|trading window|newspaper|analysts?/institutional investor meet|investor meet|investor presentation|"
                     r"loss of share|duplicate share|certificate under reg|reg(?:ulation)? 74|copy of newspaper|audio recording|"
                     r"shareholders? meeting|postal ballot|book closure|record date|esop|esos", re.I)


def ist_time(s):
    try:
        return dt.datetime.strptime((s or "").strip(), "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)
    except ValueError:
        return None


def items_of(xml_bytes):
    root = ET.fromstring(xml_bytes)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("RSS 아님")
    out = []
    for it in root.findall("./channel/item"):
        title = (it.findtext("title") or "").strip()
        desc = re.sub(r"\s+", " ", it.findtext("description") or "").strip()
        subject = desc.split("|SUBJECT:", 1)[1].strip() if "|SUBJECT:" in desc else ""
        when = ist_time(it.findtext("pubDate"))
        out.append({"company": title, "url": (it.findtext("link") or "").strip(), "desc": desc.split(" |SUBJECT:")[0].strip(),
                    "subject": subject, "published": when.astimezone(KST).isoformat(timespec="seconds") if when else None})
    return out


def beat_of(name):
    return next((ko for ko, rx in COMPANIES if rx.search(name or "")), None)


def tier_of(x):
    text = f"{x.get('subject') or ''} {x.get('desc') or ''}"
    if A_WORDS.search(text):
        return "A"
    if C_WORDS.search(text):
        return "C"
    return "B"


def pdf_head(content, n=600):
    from pypdf import PdfReader
    pages = PdfReader(io.BytesIO(content)).pages
    text = " ".join((pages[i].extract_text() or "") for i in range(min(2, len(pages))))
    return re.sub(r"\s+", " ", text).strip()[:n]


def run(now, previous=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    known = {x["id"]: x for x in prev.get("filings") or [] if isinstance(x, dict) and x.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)]
    first = not prev.get("baselineAt")
    try:
        # 11-03 탐침 143: 첫 요청이 한 번 실패하고 바로 다음 실행은 정상 — 10초 뒤 한 번만 다시 묻는다
        for attempt in (1, 2):
            try:
                r = get(RSS, headers=UA, timeout=60)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                rows = items_of(r.content)
                break
            except Exception:  # noqa: BLE001
                if attempt == 2:
                    raise
                sleep(10)
    except Exception as e:  # noqa: BLE001
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "failed",
                "checks": [{"source": "NSE 공시 RSS", "status": "failed", "returned": 0, "error": f"{type(e).__name__}: {str(e)[:60]}"}],
                "filings": list(known.values()), "events": events, **({"baselineAt": prev["baselineAt"]} if prev.get("baselineAt") else {})}
    times = sorted(x["published"] for x in rows if x["published"])
    span = {"oldest": times[0] if times else None, "newest": times[-1] if times else None}
    # 직전 실행의 가장 새 공시보다 이번 RSS의 가장 오래된 공시가 늦으면 그 사이를 못 봤을 수 있다
    gap = bool(prev.get("span", {}).get("newest") and span["oldest"] and span["oldest"] > prev["span"]["newest"])
    # 11-04: RSS는 인도 자정(03:30 KST)에 하루치를 새로 시작한다(05:04 실행이 13건, 03:34부터). 직전 실행이 자정 전 60분 안(03:10 칸)이면
    # 그 뒤 몇 분만 못 본 것이라 '일부'로 올리지 않고 메모로 남긴다. 그보다 앞(22:10 칸)이면 그날 인도 저녁 공시를 못 봤을 수 있어 '일부'.
    reset_note = None
    if gap:
        try:
            last = dt.datetime.fromisoformat(str(prev.get("generatedAt")))
            reset = last.astimezone(KST).replace(hour=3, minute=30, second=0, microsecond=0)
            if reset <= last:
                reset += dt.timedelta(days=1)
            oldest = dt.datetime.fromisoformat(span["oldest"]).astimezone(KST)
            if oldest >= reset and (reset - last) <= dt.timedelta(minutes=60):
                gap = False
                reset_note = f"RSS가 인도 자정(03:30 KST)에 새로 시작 — 직전 실행({last.astimezone(KST):%H:%M}) 뒤 {int((reset - last).total_seconds() // 60)}분은 못 봄"
        except (TypeError, ValueError):
            pass
    pdfs = 0
    for x in rows:
        comp = beat_of(x["company"])
        if not comp or not x["url"]:
            continue
        fid = "nse:" + x["url"].rsplit("/", 1)[-1]
        if fid in known:
            continue
        tier = tier_of(x)
        rec = {"id": fid, "company": comp, "issuer": x["company"], "subject": x["subject"], "desc": x["desc"], "published": x["published"],
               "url": x["url"], "tier": tier, "firstSeen": stamp, **({"baseline": True} if first else {})}
        if tier in ("A", "B") and not first and pdfs < PDF_MAX:
            sleep(PAUSE)
            pdfs += 1
            try:
                d = get(x["url"], headers=UA, timeout=60)
                if d.status_code == 200 and "pdf" in (d.headers.get("content-type") or "").lower():
                    rec["excerpt"] = pdf_head(d.content)
            except Exception:  # noqa: BLE001
                rec["excerptError"] = "첨부 PDF 읽기 실패"
        known[fid] = rec
        if not first and tier in ("A", "B"):
            events.append({"id": fid, "tier": tier, "kind": "인도 법인 공시", "company": comp, "detectedAt": stamp, "url": x["url"],
                           "subject": x["subject"],
                           "text": (f"{x['company']} NSE 공시({(x['published'] or '')[:16].replace('T', ' ')} KST) · {x['subject'] or '종류 미기재'}"
                                    f" · 「{x['desc'][:200]}」" + (f" · 첨부 첫머리 「{rec['excerpt'][:240]}」" if rec.get("excerpt") else "")
                                    + " · 거래소 공시 원문(PDF) 확인 — 현대차 자회사(별도 상장사)")})
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    filings = sorted((x for x in known.values() if str(x.get("published") or x.get("firstSeen")) >= keep), key=lambda x: str(x.get("published")), reverse=True)
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "complete" if not gap else "partial",
            "baselineAt": prev.get("baselineAt") or stamp, "span": span,
            "checks": [{"source": "NSE 공시 RSS", "status": "ok" if not gap else "partial", "returned": len(rows),
                        "note": f"RSS가 덮는 시간 {span['oldest'][:16] if span['oldest'] else '?'} ~ {span['newest'][:16] if span['newest'] else '?'}",
                        **({"error": "직전 실행 뒤 공시 일부가 RSS에서 밀려났을 수 있음"} if gap else {}),
                        **({"reset": reset_note} if reset_note else {})}],
            "filings": filings[:300], "events": sorted((e for e in events if str(e.get("detectedAt")) >= keep), key=lambda e: e["detectedAt"], reverse=True)[:200],
            "rules": ["NSE(인도 국립증권거래소) 공시 RSS에서 현대차 인도법인(Hyundai Motor India Limited) 공시만. 현대차 자회사(별도 상장사)라 기사에는 인도법인으로 구분한다.",
                      "인수·합병·설비·생산능력·로열티·특수관계 거래 낱말 A, 이사회 결과·보도자료·임원 변경 등 B, 녹취록·거래 제한·신문 공고·애널리스트 미팅 안내 C. 낱말 분류일 뿐 — 내용은 첨부 PDF 원문.",
                      "첫 실행은 기준선. RSS는 인도 자정(03:30 KST)에 하루치를 새로 시작한다 — 평일 22:10 실행 뒤 인도 저녁 공시는 화~토 03:10 실행이 읽는다. 실행 사이 공시가 밀려나면 못 볼 수 있다(그때는 '일부'로 표시). 조회 실패는 0건이 아니라 미확인."]}


def main():
    import private_store
    now = dt.datetime.now(KST).replace(microsecond=0)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("india-filings", token)
        except private_store.StoreError as e:
            print(f"::warning title=india-filings-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
        if private_store.late_scheduled_duplicate(previous, now, hours=2):
            return
    doc = run(now, previous)
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    c = doc["checks"][0]
    print(f"::notice title=india-filings::상태 {doc['status']} · RSS {c.get('returned', 0)}건 · 인도 법인 공시 보관 {len(doc['filings'])}건 · 이번 새 이벤트 {len(new)}"
          f" · {c.get('note', '')}")
    if not token:
        print("::warning title=india-filings-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("NSE 공시 RSS 조회 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("india-filings", doc, token)
    print(f"::notice title=india-filings-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
