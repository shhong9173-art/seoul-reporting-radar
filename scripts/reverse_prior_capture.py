"""경쟁지 [단독] 자동 역추적: 레이더가 기사보다 먼저 같은 회사·같은 사건 낱말을 잡았는지(자동 후보, 미검토).

- 입력: digests/reverse_trace_latest.json(업종 [단독] 제목 색인)과 레이더 기억 — 기자 전용 저장소의 감시 결과(처음 본 시각)와
  tools/clues.json(공개 원자료 단서, 게시일).
- 판정은 사람이 하는 Y/P/N(exclusive_reverse_trace.py, 기사 전문·원자료 비교)과 다르다. 여기서는 '먼저 잡은 후보 있음 /
  같은 회사 항목만 / 없음'만 자동으로 세고, 원천별로 몇 건을 몇 시간 먼저 잡았는지 모은다. 같은 사건인지는 열어 봐야 한다.
- 결과는 기자 전용 저장소(reverse-check)로만(레이더 기억에 비공개 항목이 있다). 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "reverse_check/v1"
WINDOW_DAYS = 30
LOOKBACK_DAYS = 60   # how far before an article a radar item can count
FEEDS = ["us-litigation", "partner-filings", "trade-remedy", "kr-official", "kr-signals", "us-comments", "page-watch",
         "trademarks", "assembly-bills", "us-recalls", "scoop-screen", "us-epa", "kr-fuel"]
LABEL = {"us-litigation": "미국 소송·판결", "partner-filings": "해외 파트너 공시", "trade-remedy": "무역구제·미국 관보",
         "kr-official": "공장등록·관보", "kr-signals": "공정위·한전·산업부", "us-comments": "미 연방 의견서", "page-watch": "해외 공식 페이지",
         "trademarks": "상표 출원", "assembly-bills": "국회 법안", "us-recalls": "미국 리콜", "scoop-screen": "단독 후보 심사",
         "us-epa": "미국 EPA 인증", "kr-fuel": "국내 연비 신고",
         "clues": "공개 원자료 단서(DART 등)"}
# Group-level names: an article about 포스코 and a radar item about 포스코홀딩스 concern the same group.
GROUP = {"현대자동차": "현대차", "제네시스": "현대차", "현대차(제네시스)": "현대차", "포스코홀딩스": "포스코", "엘에스일렉트릭": "LS일렉트릭",
         "아우디코리아": "아우디", "폭스바겐코리아": "폭스바겐", "BMW코리아": "BMW", "메르세데스-벤츠 코리아": "벤츠", "혼다코리아": "혼다",
         "효성중공업(관련)": "효성중공업", "일진전기(관련)": "일진전기", "OCI홀딩스": "OCI", "세아홀딩스": "세아제강", "LS지주": "LS"}
# (concept, Korean headline words, words in radar items — Korean or English)
CONCEPTS = [
    ("소송·판결", r"소송|제소|항소|불복|패소|승소|판결|법원|배상", r"v\. United States|\bIn re\b|lawsuit|complaint|appeal|opinion|court|소송|판결|항소|법원|Sustaining|Remand"),
    ("관세·무역구제", r"관세|상계|반덤핑|덤핑|무역구제|세이프가드|보조금", r"countervail|anti-?dumping|duty|tariff|subsid|관세|덤핑|쿼터|quota"),
    ("리콜·결함", r"리콜|결함|화재|발화|시정조치", r"recall|defect|fire|리콜|결함"),
    ("특허·상표", r"특허|상표|브랜드|명칭", r"patent|PTAB|trademark|상표|특허"),
    ("지분·합작·거래", r"지분|합작|매각|인수|철수|정리|양도|합병", r"equity|joint venture|disposal|acquisition|exit|transaction|investment in|양도|합병|지분|merger"),
    ("공장·생산", r"공장|증설|감산|생산|가동|라인|투자", r"plant|factory|공장|고용|주생산품|production|capacity"),
    ("수주·입찰", r"수주|낙찰|입찰|공급계약|계약", r"tender|award|bid|입찰|낙찰|supply agreement|contract|offtake"),
    ("입법·규제", r"법안|입법|개정안|국회|규제|시행령|입법예고", r"법률안|개정안|입법예고|bill|regulation|rule"),
    ("보육·복지", r"어린이집|보육|직장", r"nursery|child ?care|daycare|어린이집"),
    ("가격", r"가격|값|인상|인하", r"MSRP|price|\$\s?\d|가격"),
    ("배터리", r"배터리|셀|전지", r"battery|cell|배터리"),
    ("신차·인증", r"신차|출시|투입|연식|연비|인증|주행거리|부분변경|신형|트림", r"EPA|연비|새 모델|model year|range|주행거리|1회 충전|연식"),
]
# 판결 기사(패소·승소 등)는 판결 항목만 같은 사건으로 센다. 같은 회사의 다른 소송 접수는 다른 사건번호일 수 있다
# (10-28: 포스코 패소 기사 = 국제무역법원 24-00006 판결(Slip Op. 26-131), 레이더가 먼저 본 것은 1:26-cv-04229 접수).
RULING_TITLE = re.compile(r"패소|승소|판결|기각|인용|선고")
RULING_ITEM = re.compile(r"\bopinion\b|Sustain|Remand|Affirm|Revers|holding|판결|결정 유지|환송", re.I)
# 출입 업종에서 너무 흔한 사건 낱말: 이것 하나만 겹치면 같은 사건 근거로 약하다(10-28 첫 실행: '배터리'·'공장'만 겹친 오탐 2건).
WEAK_CONCEPTS = {"공장·생산", "배터리", "가격"}
GENERIC_WORDS = {"공장", "배터리", "미국", "생산", "가격", "투자", "계약", "중국", "한국", "글로벌", "사업", "신규"}
STOP = {"단독", "기자", "업계", "관계자", "국내", "최대", "최초", "올해", "내년", "전략", "본격", "사업", "추진", "확대", "주목", "위해",
        "이유", "속도", "결국", "다시", "직접", "모두", "현대", "그룹"}


def canon(name):
    n = re.sub(r"\(.*?\)", "", str(name or "")).strip()
    return GROUP.get(str(name or "").strip(), GROUP.get(n, n))


def parse_time(v):
    v = str(v or "").strip()
    if not v:
        return None
    try:
        if re.fullmatch(r"\d{8}", v):
            return dt.datetime(int(v[:4]), int(v[4:6]), int(v[6:8]), tzinfo=KST)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            return dt.datetime.fromisoformat(v).replace(tzinfo=KST)
        t = dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=KST)
    except ValueError:
        return None


def mem(source, iid, companies, text, seen, url=None):
    when = parse_time(seen)
    names = sorted({canon(c) for c in companies if isinstance(c, str) and c.strip()})
    if not when or not names:
        return None
    return {"source": source, "id": str(iid), "companies": names, "text": re.sub(r"\s+", " ", str(text or ""))[:500], "seen": when, "url": url}


def split_names(v):
    return [x for x in re.split(r"[·,/]", str(v or "")) if x.strip()]


def memory(docs, clues, errors=None):
    """Radar items with the time the radar first had them. Each feed is read by its own adapter; a shape surprise in one feed
    is recorded (feed name and exception type only) and does not stop the others."""
    out = []
    for name, fn in ADAPTERS:
        try:
            got = []
            fn(docs.get(name) or {} if name != "clues" else clues or {}, lambda m: m and got.append(m))
            out += got
        except Exception as e:  # noqa: BLE001 — one feed's shape must not stop the measurement
            if errors is not None:
                errors[name] = type(e).__name__
    return out


def _litigation(d, add):
    for x in d.get("cases") or []:
        add(mem("us-litigation", x.get("id"), x.get("beat") or [], f"{x.get('caseName')} {x.get('summary') or ''} {x.get('category') or ''}", x.get("firstSeen") or x.get("dateFiled"), x.get("url")))
    for x in d.get("opinions") or []:
        add(mem("us-litigation", x.get("id"), x.get("beat") or [], f"{x.get('caseName')} opinion {x.get('holding') or ''}", x.get("firstSeen") or x.get("dateFiled"), x.get("url")))
    for x in d.get("itc") or []:
        add(mem("us-litigation", x.get("id"), [n.get("company") for n in x.get("named") or []], f"ITC 337 patent {x.get('title')}", x.get("firstSeen") or x.get("date"), x.get("url")))


def _partners(d, add):
    for x in d.get("items") or []:
        add(mem("partner-filings", x.get("id"), x.get("beat") or [], f"{x.get('filer')} {x.get('title')} {x.get('snippet') or ''}", x.get("firstSeen") or x.get("date"), x.get("url")))


def _trade(d, add):
    for x in d.get("federalRegister") or []:
        add(mem("trade-remedy", x.get("id"), [n.get("company") for n in x.get("named") or []],
                f"{x.get('title')} duty {' '.join(x.get('memoTopics') or [])}", x.get("firstSeen") or x.get("date"), x.get("url")))


def _official(d, add):
    for x in d.get("events") or []:
        add(mem("kr-official", x.get("id"), [x.get("company")], f"공장 {x.get('kind')} {x.get('text')}", x.get("detectedAt"), None))
    for x in d.get("factories") or []:
        if x.get("registeredOn"):
            add(mem("kr-official", x.get("id"), [x.get("company")], f"공장 새 등록 {x.get('cmpnyNm')} {x.get('mainProductCn') or ''}", x.get("firstSeen") or x.get("registeredOn"), None))


def _signals(d, add):
    for x in d.get("decisions") or []:
        add(mem("kr-signals", x.get("id"), [m.get("company") for m in x.get("mentions") or []], f"공정위 {x.get('name')} {x.get('action') or ''}", x.get("fileDate") or x.get("decidedOn"), x.get("url")))
    for x in d.get("kepco") or []:
        add(mem("kr-signals", x.get("id"), [x.get("company")], f"한전 입찰 {x.get('name')}", x.get("noticeDate"), None))
    for x in d.get("motir") or []:
        add(mem("kr-signals", x.get("id"), x.get("companies") or [], f"산업부 {x.get('title')}", x.get("date"), x.get("url")))


def _comments(d, add):
    for x in d.get("items") or []:
        add(mem("us-comments", x.get("id"), [x.get("company")], f"{x.get('agency')} 의견서 {x.get('docketTitle') or ''}", x.get("firstSeen") or x.get("postedDate"), x.get("url")))


def _pages(d, add):
    for x in d.get("events") or []:
        a = x.get("added") or {}
        added = " ".join(str(v) for vs in (a.values() if isinstance(a, dict) else [a]) for v in (vs if isinstance(vs, list) else [vs]))
        add(mem("page-watch", f"{x.get('pageId')}:{x.get('detectedAt')}", [x.get("company")], f"{x.get('label')} {added}", x.get("detectedAt"), x.get("url")))


def _marks(d, add):
    for x in d.get("filings") or []:
        add(mem("trademarks", x.get("id"), [x.get("company")], f"상표 {x.get('title')}", x.get("firstSeen") or x.get("applicationDate"), None))


def _recalls(d, add):
    for x in d.get("recalls") or []:
        add(mem("us-recalls", x.get("id"), [w.get("name") for w in x.get("why") or []] + [w.get("beat") for w in x.get("why") or []],
                f"recall 리콜 {x.get('models')} {x.get('component')} {x.get('defect') or ''} {x.get('supplierBox') or ''}", x.get("firstSeen") or x.get("received"), x.get("url")))


def _epa(d, add):
    for v in d.get("vehicles") or []:
        add(mem("us-epa", v.get("id"), [v.get("company")], f"EPA 연비 인증 {v.get('kind')} {v.get('year')} {v.get('make')} {v.get('model')} {v.get('baseModel') or ''}"
                f"{' 주행거리 range ' + str(v.get('range')) if v.get('range') else ''}", v.get("firstSeen"), v.get("url")))


def _fuel(d, add):
    for v in d.get("vehicles") or []:
        add(mem("kr-fuel", v.get("id"), [v.get("company")], f"연비 신고 표시연비 {v.get('kind')} {v.get('maker')} {v.get('model')} {v.get('year')}년 {v.get('fuel') or ''}"
                f"{' 1회 충전 주행거리 ' + str(v.get('range')) if v.get('range') else ''}", v.get("firstSeen"), v.get("url")))


def _screen(d, add):
    for x in d.get("candidates") or []:
        add(mem("scoop-screen", x.get("id"), split_names(x.get("company")), x.get("title"), x.get("published") or x.get("filedOn"), x.get("url")))


def _clues(d, add):
    for x in d.get("items") or []:
        add(mem("clues", x.get("id"), x.get("companies") or [], x.get("title"), x.get("firstSeen") or x.get("published"), x.get("url")))


ADAPTERS = [("us-litigation", _litigation), ("partner-filings", _partners), ("trade-remedy", _trade), ("kr-official", _official),
            ("kr-signals", _signals), ("us-comments", _comments), ("page-watch", _pages), ("trademarks", _marks),
            ("us-recalls", _recalls), ("scoop-screen", _screen), ("us-epa", _epa), ("kr-fuel", _fuel), ("clues", _clues)]


def nouns(title):
    t = re.sub(r"\[[^\]]*\]|\([^)]*\)|\s+-\s+[^-]{1,40}$", " ", title)
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", t) if w not in STOP and not re.fullmatch(r"\d+", w)}


def match(article, items):
    """Best radar item for an article: same group company first seen before publication, ranked by event overlap."""
    pub = parse_time(article.get("published"))
    comps = {canon(c) for c in article.get("companies") or []}
    if not pub or not comps:
        return "회사 미상", None, 0
    title = article.get("title") or ""
    concepts = {name for name, ko, _ in CONCEPTS if re.search(ko, title)}
    words = nouns(title) - comps
    same = [m for m in items if comps & set(m["companies"]) and pub - dt.timedelta(days=LOOKBACK_DAYS) <= m["seen"] < pub]
    best, best_score = None, 0
    concept_words = {w for w in words if any(name in concepts and re.search(ko, w) for name, ko, _ in CONCEPTS)}
    for m in same:
        hit_c = sorted(name for name, _, rx in CONCEPTS if name in concepts and re.search(rx, m["text"], re.I))
        if "소송·판결" in hit_c and RULING_TITLE.search(title) and not RULING_ITEM.search(m["text"]):
            hit_c.remove("소송·판결")
        # 사건 낱말로 이미 센 단어·흔한 단어는 따로 세지 않는다
        hit_w = sorted(w for w in words - concept_words - GENERIC_WORDS if w in m["text"])
        score = sum(1 if c in WEAK_CONCEPTS else 2 for c in hit_c) + len(hit_w)
        if score > best_score or (score == best_score and best and m["seen"] > best["seen"]):
            best, best_score = {**m, "why": hit_c + hit_w}, score
    if best and best_score >= 2:
        verdict = "먼저 잡은 후보"
    elif same:
        verdict = "같은 회사 항목만"
        best = max(same, key=lambda m: m["seen"])
        best = {**best, "why": []}
    else:
        verdict = "없음"
    if best:
        best = {"source": best["source"], "label": LABEL.get(best["source"], best["source"]), "id": best["id"], "text": best["text"][:240],
                "seen": best["seen"].isoformat(timespec="minutes"), "url": best.get("url"), "why": best["why"][:6],
                "leadHours": round((pub - best["seen"]).total_seconds() / 3600, 1)}
    return verdict, best, len(same)


def run(trace, docs, clues, *, now):
    since = now - dt.timedelta(days=WINDOW_DAYS)
    adapter_errors = {}
    items = memory(docs, clues, adapter_errors)
    rows = []
    seen_titles = set()
    for a in trace.get("items") or []:
        pub = parse_time(a.get("published"))
        if not pub or pub < since or pub > now:
            continue
        # 같은 기사가 색인에 두 번 들어온 경우(같은 제목·같은 날) 한 번만 센다
        tkey = (re.sub(r"\s+", "", re.sub(r"\s+-\s+[^-]{1,40}$", "", a.get("title") or "")), pub.date().isoformat())
        if tkey in seen_titles:
            continue
        seen_titles.add(tkey)
        verdict, best, n = match(a, items)
        rows.append({"articleId": a.get("articleId"), "title": re.sub(r"\s+-\s+[^-]{1,40}$", "", a.get("title") or "")[:200], "published": a.get("published"),
                     "source": a.get("sourceName"), "companies": a.get("companies") or [], "kind": a.get("kind"), "verdict": verdict,
                     "best": best, "sameCompanyItems": n})
    rows.sort(key=lambda r: r["published"] or "", reverse=True)
    by_source = {}
    for r in rows:
        if r["verdict"] == "먼저 잡은 후보":
            s = by_source.setdefault(r["best"]["label"], {"caught": 0, "lead": []})
            s["caught"] += 1
            s["lead"].append(r["best"]["leadHours"])
    summary = {k: {"caught": v["caught"], "leadHoursMedian": median(v["lead"])} for k, v in sorted(by_source.items(), key=lambda t: -t[1]["caught"])}
    counts = {v: sum(1 for r in rows if r["verdict"] == v) for v in ("먼저 잡은 후보", "같은 회사 항목만", "없음", "회사 미상")}
    loaded = {f: f in docs for f in FEEDS}
    return {"schema": SCHEMA, "generatedAt": now.isoformat(timespec="seconds"), "windowDays": WINDOW_DAYS, "articles": rows, "counts": counts,
            "bySource": summary, "memoryItems": len(items), "feedsLoaded": loaded, "adapterErrors": adapter_errors, "traceGeneratedAt": trace.get("generatedAt"),
            "rules": ["자동 후보다. 사람이 기사 전문과 원자료를 비교하는 Y/P/N 판정(역추적 기록)과 다르고, 그 수를 바꾸지 않는다.",
                      "'먼저 잡은 후보'는 같은 회사(그룹) 항목을 기사 60일 전~직전에 레이더가 처음 봤고, 사건 낱말(한·영 대응)이 겹친 경우다. 같은 사건인지는 열어 봐야 한다.",
                      "레이더 기억은 지금 저장된 결과뿐이다(보관 기간이 지나 지워진 항목·저장 실패한 감시는 '없음'으로 나올 수 있다 — 0건 아님).",
                      "경쟁지 [단독] 목록은 구글 뉴스 제목 색인이라 일부다."],
            "confirmedScoops": 0}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("MCP_ACCESS_TOKEN 미설정 — 레이더 기억을 읽을 수 없음(미확인)")
    trace = json.loads((ROOT / "digests" / "reverse_trace_latest.json").read_text(encoding="utf-8"))
    clues = json.loads((ROOT / "tools" / "clues.json").read_text(encoding="utf-8"))
    docs, failed, empty = {}, [], []
    for f in FEEDS:
        try:
            d = private_store.get(f, token)
            if isinstance(d, dict):
                docs[f] = d
            else:
                empty.append(f)  # 저장된 결과가 아직 없음(첫 실행 전 등) — 조회 실패와 구분
        except Exception as e:  # noqa: BLE001 — network, HTTP or JSON: this feed is 미확인, the rest still count
            failed.append(f"{f}:{type(e).__name__}")
    doc = run(trace, docs, clues, now=now)
    doc["feedsFailed"] = failed
    doc["feedsEmpty"] = empty
    # Public log: counts, feed names and exception types only.
    print(f"::notice title=reverse-check::경쟁지 단독 {len(doc['articles'])}건 · {json.dumps(doc['counts'], ensure_ascii=False)} · "
          f"레이더 기억 {doc['memoryItems']}건 · 감시 읽음 {len(docs)}/{len(FEEDS)}" + (f" · 조회 실패 {failed}" if failed else "")
          + (f" · 저장 결과 없음 {empty}" if empty else "")
          + (f" · 읽기 오류 {doc['adapterErrors']}" if doc["adapterErrors"] else ""))
    try:
        status = private_store.put("reverse-check", doc, token)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"저장 실패: {type(e).__name__}")
    print(f"::notice title=reverse-check-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
