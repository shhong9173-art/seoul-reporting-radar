"""캐나다 국제무역재판소(CITT) 진행 사건 일정 — 반덤핑·상계관세 피해 조사와 종료재심(기자 11-15 02:54).

캐나다는 덤핑·보조금 판정을 CBSA가, 피해 판정과 조치 연장 여부(종료재심)를 CITT가 한다. 레이더는 CBSA 쪽만 봤다(cbsa_cases.py).
CITT '진행 중인 덤핑·보조금 사건' 쪽(탐침 242·243, 2026-11-15)은 사건마다 표 하나다:
  <h2>Expiry reviews</h2>
  <table><caption>RR-2026-007—Certain Small Power Transformers: dumping (Chinese Taipei and Korea)</caption>
    Document | Date issued or updated        (줄마다 <th scope="row">문서</th><td>날짜</td> — 탐침 244)
    Notice of expiry review of finding | October 1, 2026   (이미 나온 문서는 decisions.citt-tcce.gc.ca 링크)
    Questionnaires | March 1, 2027
    Public hearing | Week of May 25, 2027
    Order and reasons | August 5, 2027
11-15 기준 13건 중 한국은 RR-2026-007(소형 변압기 종료재심) 1건. 표 제목(caption)에 Korea가 든 사건만 저장한다.

이벤트(처음 읽은 것은 기준선): 새 한국 사건, 일정 줄에 문서 링크가 새로 붙음(문서가 나옴), 일정 날짜가 바뀜, 진행 목록에서 빠짐.
등급: 새 사건·결정 문서(Finding·Order·Determination·Reasons)가 나옴·결정 예정일이 바뀜·목록에서 빠짐은 B, 그 밖(질문서·공청회 날짜 바뀜,
개시 공고 링크)은 C. A는 내지 않는다 — 표에 회사 이름이 없다. 날짜와 문서 이름만 읽는다(결정 내용은 원문).
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import re
import time
from urllib.parse import urljoin

URL = "https://www.citt-tcce.gc.ca/en/anti-dumping-injury-inquiries/active-dumping-and-subsidizing-cases"
SOURCE = "캐나다 CITT 진행 사건 일정"
PAGE_ID = "citt"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en-CA,en;q=0.9"}
KOREA = re.compile(r"\bKorea\b", re.I)
CASE_NO = re.compile(r"\b([A-Z]{2}-\d{4}-\d{3})\b")
DECISION = re.compile(r"finding|order|determination|reasons|decision", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
GROUP_KO = {"preliminary injury inquiries": "예비 피해 조사", "final injury inquiries": "최종 피해 조사", "expiry reviews": "종료재심",
            "interim reviews": "중간재심", "public interest inquiries": "공익 조사", "requests for ruling": "판단 요청"}
GONE_KEEP = 12


def plain(raw):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", raw or "")).replace("\xa0", " ")).strip()


def iso_date(text):
    """'October 1, 2026' · 'Week of May 25, 2027' → '2026-10-01' (못 읽으면 '')."""
    m = re.search(r"\b([A-Za-z]+) (\d{1,2}), (20\d{2})\b", str(text or ""))
    if not m or m.group(1).lower() not in MONTHS:
        return ""
    try:
        return dt.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2))).isoformat()
    except ValueError:
        return ""


def parse(page):
    """(사건 [{no, title, group, korea, rows:[{doc, when, date, url}]}], 쪽 마지막 갱신일 ISO 또는 '')."""
    m = re.search(r"<main\b[\s\S]*?</main>", page, re.I)
    main = m.group(0) if m else page
    cases, group = [], ""
    for x in re.finditer(r"<h2[^>]*>([\s\S]*?)</h2>|<table[\s\S]*?</table>", main, re.I):
        if x.group(1) is not None:
            group = plain(x.group(1))
            continue
        table = x.group(0)
        cap = re.search(r"<caption[^>]*>([\s\S]*?)</caption>", table, re.I)
        caption = plain(cap.group(1)) if cap else ""
        no = CASE_NO.search(caption)
        if not no:
            continue
        rows = []
        for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", table, re.I):
            # 실제 쪽(탐침 244)은 문서 칸이 <th scope="row">, 날짜 칸이 <td>다. 머리줄은 <td>가 하나도 없다
            cells = re.findall(r"<(t[hd])\b[^>]*>([\s\S]*?)</\1>", row, re.I)
            if len(cells) < 2 or not any(tag.lower() == "td" for tag, _ in cells):
                continue
            tds = [body for _, body in cells]
            if not plain(tds[0]):
                continue
            href = re.search(r'href="([^"]+)"', tds[0])
            link = urljoin(URL, htmllib.unescape(href.group(1))) if href else ""
            # 이미 나온 문서만 결정 사이트 링크다 — 질문서·공청회 안내 쪽 링크는 문서가 나왔다는 뜻이 아니다
            rows.append({"doc": plain(tds[0])[:120], "when": plain(tds[1])[:60], "date": iso_date(tds[1]),
                         "url": link if "decisions.citt-tcce.gc.ca" in link else ""})
        title = re.sub(r"^[A-Z]{2}-\d{4}-\d{3}\s*[—–-]\s*", "", caption)[:200]
        cases.append({"no": no.group(1), "title": title, "group": group, "korea": bool(KOREA.search(caption)), "rows": rows})
    upd = re.search(r"last updated on ([A-Za-z]+ \d{1,2}, 20\d{2})", plain(main))
    return cases, iso_date(upd.group(1)) if upd else ""


def group_ko(group):
    return GROUP_KO.get(str(group or "").strip().lower(), str(group or "").strip() or "사건")


def schedule(rows):
    return " · ".join(f"{r['doc']} {r['date'] or r['when']}{'(나옴)' if r.get('url') else ''}" for r in rows)


def collect(previous, now, *, get, sleep=time.sleep):
    """(구역, 이벤트, 점검). 쪽을 못 읽으면 직전 구역을 그대로 두고 실패로 표시한다(0건 아님)."""
    prev = previous if isinstance(previous, dict) else {}
    stamp = now.isoformat(timespec="seconds")
    try:
        sleep(1)
        r = get(URL, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        try:
            r.encoding = "utf-8"
        except Exception:  # noqa: BLE001 — 테스트용 응답
            pass
        cases, updated = parse(r.text)
        if not cases:
            raise RuntimeError("사건 표 없음(형식 변경 의심)")
    except Exception as e:  # noqa: BLE001
        why = str(e)[:80] or type(e).__name__
        section = {**prev, "status": "failed", "error": why, "checkedAt": stamp} if prev else None
        return section, [], {"source": SOURCE, "status": "failed", "returned": len(prev.get("cases") or {}), "total": prev.get("total"), "events": 0, "error": why}
    had = bool(prev.get("baselineAt"))
    old_cases = prev.get("cases") if isinstance(prev.get("cases"), dict) else {}
    events, kept = [], {}
    counts = {"newCases": 0, "issued": 0, "moved": 0, "gone": 0}

    def push(no, c, key, text, tier, url=None):
        events.append({"id": f"{PAGE_ID}:{no}:{key}"[:160], "pageId": PAGE_ID, "country": "캐나다", "label": f"캐나다 CITT {group_ko(c.get('group'))} {no}",
                       "text": text, "url": url or URL, "detectedAt": stamp, "tier": tier})

    for c in cases:
        if not c["korea"]:
            continue
        no, old = c["no"], old_cases.get(c["no"])
        kept[no] = {"title": c["title"], "group": c["group"], "rows": c["rows"], "firstSeen": (old or {}).get("firstSeen") or stamp}
        if not had:
            continue
        if old is None:
            counts["newCases"] += 1
            push(no, c, "new", f"새 한국산 사건 — {c['title']} · 일정: {schedule(c['rows'])}", "B", next((x["url"] for x in c["rows"] if x["url"]), None))
            continue
        if not (old.get("rows") or []):
            continue  # 저장된 일정이 비어 있으면(11-15 첫 기준선은 줄을 못 읽었다) 이번에 읽은 줄이 기준선이다 — '새로 생김'으로 알리지 않는다
        before = {x.get("doc"): x for x in old.get("rows") or []}
        for x in c["rows"]:
            o = before.get(x["doc"])
            decision = bool(DECISION.search(x["doc"])) and not re.search(r"notice of (?:commencement|expiry review)", x["doc"], re.I)
            if x["url"] and not (o or {}).get("url"):
                counts["issued"] += 1
                push(no, c, f"issued:{x['doc'][:40]}", f"{c['title']} — 문서 나옴: 「{x['doc']}」({x['date'] or x['when']})", "B" if decision else "C", x["url"])
            elif o is not None and o.get("when") != x["when"]:
                counts["moved"] += 1
                push(no, c, f"moved:{x['doc'][:40]}:{x['date'] or x['when'][:20]}", f"{c['title']} — 일정 바뀜: 「{x['doc']}」 {o.get('when') or '?'} → {x['when']}", "B" if decision else "C")
            elif o is None:
                counts["moved"] += 1
                push(no, c, f"row:{x['doc'][:40]}", f"{c['title']} — 일정 줄이 새로 생김: 「{x['doc']}」 {x['when']}", "B" if decision else "C", x["url"] or None)
    gone = [g for g in prev.get("gone") or [] if isinstance(g, dict)]
    for no, old in old_cases.items():
        if no in kept:
            continue
        counts["gone"] += 1
        gone.append({"no": no, "title": old.get("title"), "group": old.get("group"), "goneAt": stamp, "rows": old.get("rows") or []})
        push(no, old, "gone", f"{old.get('title')} — 진행 사건 목록에서 빠짐: 결정이 나왔을 수 있음(마지막으로 본 일정: {schedule(old.get('rows') or [])}). 결정문은 CITT 결정 사이트에서 확인", "B",
             "https://decisions.citt-tcce.gc.ca/citt-tcce/en/nav.do")
    section = {"status": "ok", "checkedAt": stamp, "baselineAt": prev.get("baselineAt") or stamp, "url": URL, "total": len(cases), "updated": updated,
               "cases": kept, **({"gone": gone[-GONE_KEEP:]} if gone else {})}
    check = {"source": SOURCE, "status": "ok", "returned": len(kept), "total": len(cases), "updated": updated, "events": len(events), "baseline": not had, **counts}
    return section, events, check
