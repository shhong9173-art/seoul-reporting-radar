"""캐나다 CBSA 한국 관련 사건의 문서 줄과 시행 중 조치의 수출자 표(11-14).

배경: 레이더는 CBSA '조사 목록'의 한국 줄(사건 머리)만 봤다. 사건 머리는 거의 안 바뀌고, 새 문서는 머리 아래 표에 붙는다 — 그래서 10-26 기준선 뒤
캐나다 새 줄이 0건이었다. 종료재심·행정재심 목록은 아예 안 봤다. 탐침 237·239가 찾은 것(레이더가 못 본 것):
- 종료재심: 'Small Power Transformers: Dumping (Chinese Taipei and South Korea)—Concludes on February 26, 2027' — 2026-10-02 개시 공지.
- 행정재심: 'Carbon and alloy steel line pipe 2: Dumping (South Korea)—Concludes on December 14, 2026'(2026-06-26 개시, 10-06 연장 공지),
  'Small and Large Power Transformers: Dumping (South Korea and Chinese Taipei)—Concluded on August 14, 2026'.
- 조치 페이지(대형 변압기 TR)의 수출자 표: 'Iljin Electric Co., Ltd. … Cooperative since 2026-08 · Last revised 2026-08'.

탐침 236~239(GitHub에서 로그인 없이, robots.txt는 /sima-lmsi/를 막지 않음 — 막힌 것은 /sima/·/lmsi/ 등 옛 주소):
- 목록 세 곳(조사 i-e · 종료재심 er-rre · 행정재심 ar-ra, 옛 '재조사 ri-re'는 ar-ra로 옮김)이 같은 꼴이다:
  <details class="box"><summary><h4>사건 이름: <span>Dumping (나라들)&mdash;Concludes on <time datetime="2026-12-14">…</time></span></h4></summary>
   <table> <tr><td><a href="/sima-lmsi/ar-ra/lp22026/lp2202601-ni-eng.html">Notice of initiation of administrative review</a></td>
   <td><time datetime="2026-06-26">26-Jun-2026</time></td></tr> … </table></details>
  사건 수 130·131·202, 한국 관련 22·28·44. 머리 안에 주석(<!-- … -->)이 있어 지우고 읽는다. 옛 줄은 날짜가 '2021-04-15' 글자다.
- 시행 중 조치 목록(mif-mev/menu): 표 'MIF code | Product | Type | Country | Tariff classification numbers' — 한국 줄 14개(13쪽).
  조치 쪽: 'Investigation information' 표(Action | Date)와 수출자 표(… Exporter | Exporter ID | Cooperative since | Last revised, 나라 칸이 있거나
  바로 앞 h3 'Country of origin or export: South Korea').

하는 일
- 목록 세 곳에서 머리나 표에 Korea가 든 사건만: 사건 머리(결론 예정·종결 날짜)와 문서 줄을 저장하고, **새 문서 줄**·**머리의 상태 바뀜**·**새 사건**을 이벤트로 낸다.
  '조사' 목록의 새 사건은 기존 목록 줄 감시(ca-cbsa)가 이미 내므로 여기서는 내지 않는다. 'Exhibit list'·'Listing of counsel'은 세지만 이벤트로 내지 않는다.
- 조치 쪽: 새 Action 줄, 새 수출자, 'Last revised'가 바뀐 수출자를 이벤트로 낸다(한국 수출자만).
- 처음 읽는 목록·쪽은 기준선이다(이벤트 없음). 못 읽으면 직전 상태를 그대로 두고 미확인.
- 등급: 판정·개시·종결 문서와 출입처 이름이 든 것은 B, 일정·연장 같은 절차 문서는 C. **A는 붙이지 않는다**(새 원천 — 올릴지는 기자가 정한다).
- 공개 로그엔 건수만.
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import re
import time
from urllib.parse import urljoin

HOST = "https://www.cbsa-asfc.gc.ca"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en,ko;q=0.8"}
LISTS = (("i-e", "조사", HOST + "/sima-lmsi/i-e/menu-eng.html"), ("er-rre", "종료재심", HOST + "/sima-lmsi/er-rre/menu-eng.html"),
         ("ar-ra", "행정재심", HOST + "/sima-lmsi/ar-ra/menu-eng.html"))
MIF_MENU = HOST + "/sima-lmsi/mif-mev/menu-eng.html"
SOURCE = "캐나다 CBSA 사건 문서·시행 중 조치"
PAGE_ID = "cbsa"
GAP = 1.5
MIF_BUDGET = 20          # 한 실행에 여는 조치 쪽(한국 줄 13쪽)
FULL_DAYS = 500          # 이 안에 문서가 붙은 사건·진행 중 사건만 문서 줄을 통째로 저장(나머지는 열쇠만)
KOREA = re.compile(r"\bKorea\b", re.I)
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
STATE = re.compile(r"\b(Concludes|Concluded|Terminated|Undertaking Accepted|Suspended)\b[^—\-–]{0,20}?\bon\b", re.I)
# 세지만 알리지 않는 줄(누가 열람 허가를 받았는지·증거 목록 — 날짜가 자주 바뀐다)
SILENT = re.compile(r"^(?:Exhibit list|Listing of counsel)", re.I)
# 절차 문서(C): 일정·연장·기록 마감
PROCEDURAL = re.compile(r"schedule|extension|close of record|update[ds]? ", re.I)


def plain(raw):
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", raw or "")).replace("\xa0", " ")).strip()


def iso_date(raw):
    """<time datetime> · '2021-04-15' · '11-Aug-2025' · '2020-Mar-20' · 'December 14, 2026' → 'YYYY-MM-DD'(못 읽으면 '')."""
    m = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', raw or "")
    if m:
        return m.group(1)
    t = plain(raw)
    m = re.search(r"\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b", t)
    if m:
        return m.group(0)
    m = re.search(r"\b(\d{1,2})-([A-Za-z]{3})[a-z]*-(\d{4})\b", t) or None
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    m = re.search(r"\b(\d{4})-([A-Za-z]{3})[a-z]*-(\d{1,2})\b", t)
    if m and m.group(2).lower() in MONTHS:
        return f"{m.group(1)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(3)):02d}"
    m = re.search(r"\b([A-Z][a-z]{2})[a-z]*\.? (\d{1,2}), (\d{4})\b", t)
    if m and m.group(1).lower() in MONTHS:
        return f"{m.group(3)}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return ""


def main_of(page):
    page = re.sub(r"<!--[\s\S]*?-->", "", page or "")
    a, b = page.find("<main"), page.find("</main>")
    return page[a:b] if a >= 0 and b > a else page


def doc_key(url, title):
    m = re.search(r"/sima-lmsi/[^\"?#]+?([a-z0-9]+-[a-z0-9]+)-eng\.html", url or "")
    return m.group(1) if m else re.sub(r"\W+", "-", title.lower())[:40]


def case_key(list_id, docs, title):
    for d in docs:
        m = re.search(r"/sima-lmsi/[a-z-]+/([a-z0-9]+)/([a-z0-9]+?)-[a-z0-9]+-eng\.html", d.get("url") or "")
        if m:
            return f"{list_id}/{m.group(1)}/{m.group(2)}"
    return f"{list_id}/" + re.sub(r"\W+", "-", re.split(r"—| - Conclud| – ", title)[0].lower())[:60]


def parse_list(page, list_id, base):
    """목록 쪽 → 한국 관련 사건 [{key, title, state, stateDate, docs:[{key,title,date,url}]}], 전체 사건 수."""
    main = main_of(page)
    blocks = re.findall(r"<details\b[^>]*>([\s\S]*?)</details>", main)
    out = []
    for block in blocks:
        s = re.search(r"<summary[^>]*>([\s\S]*?)</summary>", block)
        title = plain(s.group(1)) if s else ""
        if not title or not KOREA.search(title + " " + plain(block)):
            continue
        docs = []
        for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", block):
            tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row)
            if len(tds) < 2:
                continue
            href = re.search(r'href="([^"]+)"', tds[0])
            url = urljoin(base, htmllib.unescape(href.group(1))) if href else ""
            t = plain(tds[0])
            if t:
                docs.append({"key": doc_key(url, t), "title": t[:140], "date": iso_date(tds[-1]), "url": url})
        st = STATE.search(title)
        tail = s.group(1)[s.group(1).lower().rfind(st.group(1).lower()):] if st and s else ""
        out.append({"key": case_key(list_id, docs, title), "title": title[:240], "state": st.group(1).capitalize() if st else "",
                    "stateDate": iso_date(tail) if st else "", "docs": docs})
    return out, len(blocks)


def parse_mif_menu(page, base=MIF_MENU):
    """시행 중 조치 목록 → 한국 줄 [{code, product, type, url}](쪽 주소 기준으로 겹치지 않게)."""
    out, seen = [], set()
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", main_of(page)):
        tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row)
        if len(tds) < 4 or not KOREA.search(plain(tds[3])):
            continue
        href = re.search(r'href="([^"]+)"', tds[1])
        url = urljoin(base, href.group(1)) if href else ""
        if not url:
            continue
        types = plain(tds[2])
        if url in seen:
            for x in out:
                if x["url"] == url and types not in x["type"]:
                    x["type"] += "·" + types
            continue
        seen.add(url)
        out.append({"code": plain(tds[0]), "product": plain(tds[1])[:80], "type": types, "url": url})
    return out


def parse_measure(page, base):
    """조치 쪽 → (Action 줄 [{title,date,url}], 한국 수출자 [{name, since, revised, country}])."""
    main = main_of(page)
    actions, exporters = [], []
    a = re.search(r"<h2[^>]*>\s*Investigations? information\s*</h2>", main, re.I)
    if a:
        table = re.search(r"<table[\s\S]*?</table>", main[a.end():])
        for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", table.group(0) if table else ""):
            tds = re.findall(r"<td[^>]*>([\s\S]*?)</td>", row)
            if len(tds) >= 2 and plain(tds[0]):
                href = re.search(r'href="([^"]+)"', tds[0])
                actions.append({"title": plain(tds[0])[:140], "date": iso_date(tds[1]), "url": urljoin(base, htmllib.unescape(href.group(1))) if href else ""})
    # 수출자 표: 머리 줄에 Exporter·Last revised가 있는 표. 나라 칸이 없으면 바로 앞 h3의 나라. 나라 칸이 여러 줄에 걸치면(rowspan) 앞 줄의 나라를 잇는다
    for m in re.finditer(r"<table[\s\S]*?</table>", main):
        table = m.group(0)
        thead = re.search(r"<thead[\s\S]*?</thead>", table)
        heads = [plain(x).lower() for x in re.findall(r"<th[^>]*>([\s\S]*?)</th>", thead.group(0) if thead else table)]
        if "exporter" not in heads or not any("revised" in h for h in heads):
            continue
        h3 = re.findall(r"<h3[^>]*>([\s\S]*?)</h3>", main[:m.start()])
        section = plain(h3[-1]) if h3 else ""
        col = {h: i for i, h in enumerate(heads)}
        has_country, last_country = "country" in col, ""
        for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", table[thead.end():] if thead else table):
            tds = [plain(x) for x in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row)]
            if has_country and len(tds) == len(heads) - 1:
                tds.insert(col["country"], last_country)
            if len(tds) < len(heads) or not tds[col["exporter"]] or tds[col["exporter"]].lower() == "exporter":
                continue
            country = tds[col["country"]] if has_country else section
            last_country = country if has_country else last_country
            if not KOREA.search(country):
                continue
            since = next((tds[i] for h, i in col.items() if "cooperative" in h), "")
            revised = next((tds[i] for h, i in col.items() if "revised" in h), "")
            exporters.append({"name": tds[col["exporter"]][:100], "since": since[:10], "revised": revised[:10],
                              "country": "South Korea" if has_country else re.sub(r"^Country of origin or export:\s*", "", section)[:60]})
    return actions, exporters


def beat_in(text):
    import tra_file_watch as tra
    return tra.companies_in(text)


def tier_of(doc_title, companies):
    return "C" if PROCEDURAL.search(doc_title) and not companies else "B"


def collect(previous, now, *, get, sleep=time.sleep):
    """(section, events, check). section = {lists:{id:{status, cases:{key:case}}}, measures:{url:{…}}, checkedAt, baselineAt}."""
    prev = previous if isinstance(previous, dict) else {}
    stamp = now.isoformat(timespec="seconds")
    full_from = (now - dt.timedelta(days=FULL_DAYS)).date().isoformat()
    out = {"checkedAt": stamp, "baselineAt": prev.get("baselineAt") or stamp, "lists": {}, "measures": {}}
    events, errors, counts = [], [], {"cases": 0, "docs": 0, "open": 0, "newDocs": 0, "newCases": 0, "stateChanges": 0, "measures": 0, "exporters": 0}

    def fetch(url):
        sleep(GAP)
        r = get(url, headers=HEADERS, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        try:
            r.encoding = "utf-8"
        except Exception:  # noqa: BLE001 — 테스트용 응답
            pass
        return r.text

    def event(key, label, text, url, tier, companies):
        events.append({"id": f"{PAGE_ID}:{key}"[:160], "pageId": PAGE_ID, "country": "캐나다", "label": label, "text": text, "url": url,
                       "detectedAt": stamp, "tier": tier, **({"companies": companies} if companies else {})})

    for list_id, kind, url in LISTS:
        old = (prev.get("lists") or {}).get(list_id) or {}
        try:
            cases, total = parse_list(fetch(url), list_id, url)
            if not total:
                raise RuntimeError("사건 줄 없음(형식 변경 의심)")
        except Exception as e:  # noqa: BLE001 — 한 목록 실패가 다른 목록을 막지 않는다
            errors.append(f"{kind} {str(e)[:40] or type(e).__name__}")
            out["lists"][list_id] = {**old, "status": "failed", "error": str(e)[:60] or type(e).__name__}
            continue
        old_cases = old.get("cases") or {}
        baseline = not old_cases
        kept = {}
        for c in cases:
            o = old_cases.get(c["key"])
            seen = set((o or {}).get("seen") or [])
            firms = beat_in(c["title"])
            if o is None and not baseline and list_id != "i-e":
                first = next((d for d in c["docs"] if not SILENT.match(d["title"])), None)
                event(c["key"], f"캐나다 CBSA {kind}", f"새 사건 — {c['title']} · 문서 {len(c['docs'])}건" + (f"(「{first['title']}」 {first['date']})" if first else ""),
                      (first or {}).get("url") or url, "B", firms)
                counts["newCases"] += 1
            elif o is not None:
                for d in c["docs"]:
                    if d["key"] in seen or SILENT.match(d["title"]):
                        continue
                    both = sorted(set(firms + beat_in(d["title"])))
                    event(f"{c['key']}:{d['key']}", f"캐나다 CBSA {kind}", f"{c['title']} — 새 문서 「{d['title']}」({d['date'] or '날짜 없음'})", d["url"] or url, tier_of(d["title"], both), both)
                    counts["newDocs"] += 1
                if (o.get("state"), o.get("stateDate")) != (c["state"], c["stateDate"]) and c["state"]:
                    event(f"{c['key']}:state:{c['state']}:{c['stateDate']}", f"캐나다 CBSA {kind}",
                          f"{c['title']} — 사건 머리 바뀜: {o.get('state') or '표시 없음'} {o.get('stateDate') or ''} → {c['state']} {c['stateDate'] or '날짜 미정'}".replace("  ", " "), url, "B", firms)
                    counts["stateChanges"] += 1
            dates = [d["date"] for d in c["docs"] if d["date"]]
            ongoing = c["state"] == "Concludes"
            recent = ongoing or (max(dates) if dates else "") >= full_from
            kept[c["key"]] = {"title": c["title"], "state": c["state"], "stateDate": c["stateDate"], "seen": sorted(seen | {d["key"] for d in c["docs"]}),
                              "n": len(c["docs"]), "latest": max(dates) if dates else "", "firstSeen": (o or {}).get("firstSeen") or stamp,
                              **({"companies": firms} if firms else {}),
                              **({"docs": [{k: d[k] for k in ("title", "date", "url")} for d in c["docs"]]} if recent else {})}
            counts["cases"] += 1
            counts["docs"] += len(c["docs"])
            counts["open"] += 1 if ongoing else 0
        out["lists"][list_id] = {"status": "ok", "kind": kind, "url": url, "total": total, "cases": kept, "checkedAt": stamp}

    # 시행 중 조치: 한국 줄의 조치 쪽
    old_m = prev.get("measures") or {}
    try:
        menu = parse_mif_menu(fetch(MIF_MENU))
        if not menu:
            raise RuntimeError("한국 줄 없음(형식 변경 의심)")
    except Exception as e:  # noqa: BLE001
        errors.append(f"시행 중 조치 목록 {str(e)[:40] or type(e).__name__}")
        menu, out["measures"] = [], dict(old_m)
    for m in menu[:MIF_BUDGET]:
        o = old_m.get(m["url"])
        try:
            actions, exporters = parse_measure(fetch(m["url"]), m["url"])
            if not actions and not exporters:
                raise RuntimeError("표 없음(형식 변경 의심)")
        except Exception as e:  # noqa: BLE001
            errors.append(f"조치 {m['code']} {str(e)[:40] or type(e).__name__}")
            if o:
                out["measures"][m["url"]] = {**o, "stale": True}
            continue
        label = f"캐나다 CBSA 시행 중 조치 {m['code']}({m['product']})"
        if o is not None:
            seen_a = set(o.get("seenActions") or [])
            for a in actions:
                if f"{a['title']}|{a['date']}" not in seen_a:
                    firms = beat_in(a["title"])
                    event(f"mif:{m['code']}:{a['date']}:{doc_key(a['url'], a['title'])}", label, f"조치 쪽에 새 절차 줄 「{a['title']}」({a['date'] or '날짜 없음'})", a["url"] or m["url"], "B", firms)
            old_e = {x.get("name"): x for x in o.get("exporters") or []}
            for x in exporters:
                firms = beat_in(x["name"])
                if x["name"] not in old_e:
                    event(f"mif:{m['code']}:exp:{x['name'][:40]}", label, f"정상가격을 받은 한국 수출자에 새 이름 「{x['name']}」(협조 시작 {x['since'] or '?'} · 마지막 개정 {x['revised'] or '?'})", m["url"], "B", firms)
                elif old_e[x["name"]].get("revised") != x["revised"]:
                    event(f"mif:{m['code']}:rev:{x['name'][:40]}:{x['revised']}", label,
                          f"한국 수출자 「{x['name']}」의 정상가격 마지막 개정 {old_e[x['name']].get('revised') or '?'} → {x['revised'] or '?'}", m["url"], "B" if firms else "C", firms)
            for name in old_e:
                if name not in {x["name"] for x in exporters}:
                    event(f"mif:{m['code']}:gone:{name[:40]}", label, f"정상가격을 받은 한국 수출자 표에서 「{name}」이 빠짐", m["url"], "B", beat_in(name))
        out["measures"][m["url"]] = {"code": m["code"], "product": m["product"], "type": m["type"], "actions": actions[-6:], "exporters": exporters,
                                     "seenActions": sorted({f"{a['title']}|{a['date']}" for a in actions}),
                                     "companies": sorted({f for x in exporters for f in beat_in(x["name"])}), "checkedAt": stamp}
        counts["measures"] += 1
        counts["exporters"] += len(exporters)
    for u, o in old_m.items():                     # 이번에 못 연 쪽은 직전 상태 그대로
        out["measures"].setdefault(u, {**o, "stale": True})
    ok_lists = sum(1 for v in out["lists"].values() if v.get("status") == "ok")
    status = "ok" if not errors else "partial" if ok_lists or counts["measures"] else "failed"
    check = {"source": SOURCE, "status": status, "returned": counts["cases"], **counts, "events": len(events), **({"error": "; ".join(errors[:4])} if errors else {})}
    return out, events, check
