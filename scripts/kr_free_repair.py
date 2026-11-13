"""자동차리콜센터 '무상점검·수리' 게시판 — 출입처 브랜드의 새 무상수리 공지를 올라온 날 잡는다.

근거: 11-04 아이뉴스24 기사 「구형 팰리세이드 9만대 ABS 무상수리⋯美보다 11개월 늦어」(11-14 news_check로 확인) — 무상수리 공지가
기사로 이어진 사례다. 레이더는 같은 누리집의 리콜현황(리콜)만 보고 있었다(domestic_recall_screen.py).
탐침 11-13·11-14(GitHub에서 로그인 없이):
- 목록 https://www.car.go.kr/ri/grts/list.do (쪽 넘김은 POST currentPageNo, 한 쪽 5건, 전체 4,177건)
  <ul class="board-hrznt-list"><li><a onclick="$main.event.detailView('4874','O');"><strong>[기아] K8 HEV - … 관련 무상수리</strong>…
  <ol><li>국토교통부</li><li>2026-11-11</li><li>조회수 : 286</li></ol>
- 상세 POST /ri/grts/detail.do (gratischeckId·ctype) — 표: 제작(수입)사·차명·생산기간·무상수리기간·대수·무상점검내용·조치사항·기타문의
  예) 기아 K8(GL3) HEV 77,043대 · 생산 2021-04-23~2024-08-12 · HPCU 소프트웨어 설계 오류
- 상세는 POST로만 열린다(GET은 405) — 글마다 따로 걸 주소가 없어 원문 주소는 목록 주소 뒤에 '#글 번호'를 붙인다(항목끼리 주소가
  겹치지 않게. 열면 목록이 뜨고 글 번호·제목으로 찾는다).
- robots.txt는 없다(404, 11-14 탐침 228). 실행마다 다시 확인해 규칙이 생겨 이 경로를 막으면 읽지 않는다.

등급: 출입처 브랜드 공지 중 대상 1만 대 이상이거나 내용에 안전 낱말(화재·시동 꺼짐·제동·조향·에어백·동력 상실·주행 중 정지)이 있으면 A,
그 밖 출입처 브랜드 B, 다른 브랜드는 화면에만(C). 무상수리는 리콜(제작결함 시정)이 아니다 — 국토부 공지 원문 기준.
결과는 기자 전용 저장소(kr-fuel의 freeRepair 구역)로만. 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import html
import re
import time
import urllib.robotparser

LIST = "https://www.car.go.kr/ri/grts/list.do"
ROBOTS = "https://www.car.go.kr/robots.txt"
DETAIL = "https://www.car.go.kr/ri/grts/detail.do"
SOURCE = "자동차리콜센터 무상점검·수리 게시판"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "ko,en;q=0.8", "Referer": LIST}
MAX_PAGES = 8          # 한 번 실행에 읽는 목록 쪽(쪽마다 5건) — 본 적 있는 글만 나오는 쪽에서 멈춘다
FIRST_PAGES = 4        # 첫 실행: 최근 20건을 기준선으로
FIRST_DAYS = 2         # 첫 실행: 최근 이틀 글만 새 글로 알린다
DETAIL_BUDGET = 12     # 한 번 실행에 여는 상세 페이지
DETAIL_TRIES = 3       # 상세가 안 열리면 다음 실행에서 다시(이 횟수까지)
KEEP_DAYS = 120
BIG_UNITS = 10_000
# (출입처 이름, 제목 머리말·제작사 규칙). 계열·다른 브랜드(포르쉐·볼보·BYD 등)는 출입처가 아니다.
BRANDS = [
    ("현대차", re.compile(r"현대자동차|현대차|^\s*\[?현대\]?|제네시스|HYUNDAI|GENESIS", re.I)),
    ("기아", re.compile(r"기아", re.I)),
    ("KG모빌리티", re.compile(r"KG\s*모빌리티|케이지모빌리티|KGM|쌍용", re.I)),
    ("르노코리아", re.compile(r"르노", re.I)),
    ("한국GM", re.compile(r"한국지엠|한국GM|지엠|쉐보레|캐딜락|GMC\b|\bGM\b", re.I)),
    ("메르세데스-벤츠 코리아", re.compile(r"벤츠|메르세데스|MERCEDES", re.I)),
    ("BMW코리아", re.compile(r"비엠더블유|BMW|\bMINI\b|미니\b", re.I)),
    ("폭스바겐코리아", re.compile(r"폭스바겐|VOLKSWAGEN", re.I)),
    ("아우디코리아", re.compile(r"아우디|AUDI", re.I)),
    ("혼다코리아", re.compile(r"혼다|HONDA", re.I)),
]
# 상용차 법인(현대·기아가 아닌 이름에 '현대'가 든 곳)·다른 브랜드가 걸리지 않게 먼저 뺀다
NOT_BEAT = re.compile(r"볼보|포르쉐|테슬라|BYD|비와이디|만트럭|스카니아|다임러트럭|타타대우|에프엘오토|포드|토요타|렉서스|닛산|재규어|랜드로버|스텔란티스|지프|푸조|"
                      r"폴스타|이스즈|이베코|현대건설기계|HD현대|현대에버다임|기아대책", re.I)
SAFETY = re.compile(r"화재|발화|시동\s*꺼|주행\s*중\s*(?:정지|멈|시동)|동력\s*(?:상실|손실)|제동|브레이크|조향|에어백|가속\s*불|안전벨트|좌석안전띠|연료\s*누|누유|전복|이탈")


def plain(raw):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw or "")).replace("\xa0", " ")).strip()


def brand_of(title, maker=""):
    """제목 머리말([기아])과 제작사 칸으로 출입처를 가른다. 출입처가 아니면 None."""
    head = (re.match(r"\s*\[([^\]\[]{1,30})[\]\[]", title or "") or [None, ""])[1] or (str(title or "").split() or [""])[0]
    text = f"{head} {maker}".strip()
    if not text or NOT_BEAT.search(text):
        return None
    for name, rx in BRANDS:
        if rx.search(text):
            return name
    return None


def parse_list(page):
    """목록 페이지 → ([{id, ctype, title, source, date}], 전체 건수 | None)."""
    out = []
    for m in re.finditer(r"detailView\('(\d+)'\s*,\s*'(\w)'\)[^>]*>\s*<strong>([\s\S]*?)</strong>[\s\S]*?<ol>([\s\S]*?)</ol>", page or ""):
        meta = [plain(x) for x in re.findall(r"<li>([\s\S]*?)</li>", m.group(4))]
        date = next((x for x in meta if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)), "")
        out.append({"id": m.group(1), "ctype": m.group(2), "title": plain(m.group(3))[:200], "source": meta[0] if meta else "", "date": date})
    total = re.search(r"전체\s*([\d,]+)\s*건", plain(page))
    return out, int(total.group(1).replace(",", "")) if total else None


def parse_detail(page):
    """상세 페이지 표 → {maker, model, produced, period, units, reason, action, contact, attach}."""
    got = {}
    for row in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", page or "", re.I):
        cells = [plain(c) for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", row, re.I)]
        for k, v in zip(cells[::2], cells[1::2]):
            got[k.replace(" ", "")] = v
    units = re.search(r"[\d,]+", got.get("대수", ""))
    attach = [plain(x) for x in re.findall(r"fileDownload\([^)]*\)[^>]*>([\s\S]*?)</a>", page or "")]
    return {"maker": got.get("제작(수입)사", "")[:80], "model": got.get("차명", "")[:160], "produced": got.get("생산기간", "")[:60],
            "period": got.get("무상수리기간", got.get("무상점검기간", ""))[:60], "units": int(units.group(0).replace(",", "")) if units else None,
            "reason": got.get("무상점검내용", "")[:600], "action": got.get("조치사항", "")[:300], "contact": got.get("기타문의", "")[:80],
            "attach": [a[:120] for a in attach if a][:4]}


def classify(item):
    """(등급, 이유). 출입처 브랜드가 아니면 C."""
    if not item.get("company"):
        return "C", "출입처 브랜드 아님"
    units = item.get("units") or 0
    words = sorted({m.group(0).replace(" ", "") for m in SAFETY.finditer(f"{item.get('title', '')} {item.get('reason', '')}")})
    if units >= BIG_UNITS:
        return "A", f"대상 {units:,}대(1만 대 이상)"
    if words:
        return "A", f"안전 관련 낱말({'·'.join(words[:3])})"
    return "B", "출입처 브랜드 무상수리 공지"


def robots_allows(session):
    """(읽어도 되나, 메모). robots.txt가 없으면(4xx·HTML 안내문) 허용, 규칙이 이 경로를 막으면 불가. 서버 오류·접속 실패는 판단 보류 → 이번 실행은 읽지 않는다."""
    try:
        r = session.get(ROBOTS, headers=HEADERS, timeout=20)
    except Exception as e:  # noqa: BLE001
        return False, f"robots.txt 확인 실패({type(e).__name__})"
    body = getattr(r, "text", "") or ""
    if 400 <= r.status_code < 500 or (r.status_code == 200 and "<html" in body[:400].lower()):
        return True, "robots.txt 없음"
    if r.status_code != 200:
        return False, f"robots.txt 확인 실패(HTTP {r.status_code})"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.splitlines())
    if not (rp.can_fetch(UA, LIST) and rp.can_fetch(UA, DETAIL)):
        return False, "robots.txt가 이 게시판 경로를 막음"
    delay = rp.crawl_delay(UA)
    if delay and float(delay) > 5:
        return False, f"robots.txt 요청 간격 {delay}초 — 한 실행에 여러 쪽을 읽을 수 없음"
    return True, "robots.txt 허용"


def _page(session, n):
    r = session.post(LIST, data={"currentPageNo": str(n)}, headers=HEADERS, timeout=40) if n > 1 else session.get(LIST, headers=HEADERS, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        r.encoding = "utf-8"
    except Exception:  # noqa: BLE001 — 테스트용 응답
        pass
    return r.text


def _detail(session, item):
    r = session.post(DETAIL, data={"gratischeckId": item["id"], "ctype": item["ctype"], "currentPageNo": "1"}, headers=HEADERS, timeout=40)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        r.encoding = "utf-8"
    except Exception:  # noqa: BLE001
        pass
    return parse_detail(r.text)


def collect(prev, now, session, *, sleep=time.sleep):
    """prev: 지난 doc['freeRepair'] 또는 None. 돌려줌: (freeRepair 구역, 점검 한 줄)."""
    stamp = now.isoformat(timespec="seconds")
    baseline = not prev
    prev = prev or {}
    seen = set(prev.get("seen") or [])
    items = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    check = {"source": SOURCE, "status": "ok", "returned": 0}
    floor = (now - dt.timedelta(days=FIRST_DAYS)).date().isoformat()
    listed, total, pages, errors = [], prev.get("total"), 0, []
    allowed, robots_note = robots_allows(session)
    if not allowed:
        check.update(status="failed", error=robots_note)
        return (dict(prev, stale=True) if prev else None), check
    for n in range(1, (FIRST_PAGES if baseline else MAX_PAGES) + 1):
        try:
            rows, t = parse_list(_page(session, n))
        except Exception as e:  # noqa: BLE001
            errors.append(f"목록 {n}쪽 {str(e)[:50] or type(e).__name__}")
            break
        if n == 1 and not rows:
            errors.append("목록 1쪽에 글이 없음(형식 변경 의심)")
            break
        pages, total = n, t or total
        listed += rows
        if not baseline and rows and all(r["id"] in seen for r in rows):   # 본 적 있는 글만 나온 쪽 — 그 뒤는 볼 필요 없다
            break
        sleep(0.4)
    if errors and not listed:
        check.update(status="failed", error="; ".join(errors))
        return (dict(prev, stale=True) if prev else None), check
    budget = DETAIL_BUDGET
    fresh = [r for r in listed if r["id"] not in seen]
    # 상세를 못 읽고 넘겼거나 열리지 않은 출입처 글은 다음 실행이 이어 읽는다
    retry = [x for x in items.values() if x.get("detail") == "pending" or (x.get("detail") == "failed" and (x.get("detailTries") or 0) < DETAIL_TRIES)]
    background = []     # 기준선 글(새 항목으로 올리지 않음)도 한도가 남으면 상세를 읽어 둔다 — 화면에서 대수·내용을 보려고
    for r in fresh:
        company = brand_of(r["title"])
        announce = not baseline or (r["date"] and r["date"] >= floor)
        # baseline: 첫 실행 때 이미 올라와 있던 글(레이더에 새 항목으로 올리지 않는다) — 다음 실행에도 남는 표시
        rec = {"id": f"grts:{r['id']}", "no": r["id"], "ctype": r["ctype"], "title": r["title"], "source": r["source"], "date": r["date"],
               "company": company, "firstSeen": stamp, "isNew": bool(announce), "baseline": not announce, "url": f"{LIST}#{r['id']}"}
        if company:
            (retry if announce else background).append(rec)
        items[rec["id"]] = rec
        seen.add(r["id"])
    for rec in retry + background:
        if budget <= 0:
            rec["detail"] = "pending"
            continue
        budget -= 1
        sleep(0.4)
        try:
            d = _detail(session, {"id": rec["no"], "ctype": rec["ctype"]})
            rec.update(d, detail="ok")
            rec["company"] = brand_of(rec["title"], d.get("maker", "")) or rec["company"]
        except Exception as e:  # noqa: BLE001
            rec["detail"] = "failed"
            rec["detailTries"] = (rec.get("detailTries") or 0) + 1
            rec["detailError"] = str(e)[:50] or type(e).__name__
    for rec in items.values():
        rec["tier"], rec["why"] = classify(rec)
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    kept = sorted((x for x in items.values() if (x.get("date") or x["firstSeen"][:10]) >= keep_from), key=lambda x: (x.get("date") or "", int(x["no"])), reverse=True)[:300]
    for x in kept:
        if x["firstSeen"] != stamp:
            x["isNew"] = False
    if errors:
        check.update(status="partial", error="; ".join(errors))
    new = [x for x in kept if x["firstSeen"] == stamp and x.get("isNew")]
    check.update(returned=len(listed), pages=pages, total=total, newPosts=len(new), newBeat=sum(1 for x in new if x.get("company")),
                 detailsRead=DETAIL_BUDGET - budget, pending=sum(1 for x in kept if x.get("detail") == "pending"), robots=robots_note)
    return {"checkedAt": stamp, "baselineAt": prev.get("baselineAt") or stamp, "total": total, "items": kept, "seen": sorted(seen, key=int)[-1500:],
            "rules": ["자동차리콜센터 '무상점검·수리' 게시판의 새 글 중 출입처 브랜드만 알린다. 첫 실행은 기준선(최근 이틀 글만 새 글).",
                      "무상수리는 리콜(제작결함 시정조치)이 아니다. 대상 대수·생산기간·내용은 국토부 공지 원문 그대로 — 원인·국내외 차이는 회사 확인.",
                      "대상 1만 대 이상이거나 내용에 안전 낱말이 있으면 A. 조회 실패는 0건이 아니라 미확인."]}, check
