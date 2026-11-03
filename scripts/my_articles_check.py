"""기자 기사 자동 대조(my-articles): 홍성효 기자가 쓴 출입처 기사에 레이더가 먼저 잡은 항목이 있었는지.

- 왜: 기자 판정(씀·킬·보류·봤음)이 14일에 1건뿐이라 어느 감시가 기사로 이어지는지 가릴 수 없었다(11-03). 기자 제안: "아이뉴스24 홍성효
  기자 검색해서 썼는지 안 썼는지 확인하면 되지". 쓴 기사는 자동으로 찾을 수 있다. 안 쓴 항목은 이유(가치 없음·취재 중·시간 없음)를
  모르므로 킬로 세지 않는다.
- 기사 목록: 아이뉴스24 뉴스 사이트맵(https://www.inews24.com/sitemap.xml — robots 'Allow:/sitemap.xml$'; 11-03 탐침 159: 최근 기사
  800여 건의 주소·발행시각·제목). 제목에 출입처 이름이 든 새 기사만 열어(robots 'Allow:/view/') 기사 작성자 메타
  `<meta property="article:author" content="…">`가 '홍성효'인지 본다. 한 실행 80건, 1.5초 간격. 한 번 본 주소는 다시 열지 않는다.
- 처음 실행에는 지난 30일을 구글 뉴스 제목 색인('"홍성효" site:inews24.com', 100건 한도)으로 채운다. 이 기사들은 작성자 메타를
  확인하지 못한 것(verified=false)이라 따로 표시한다. 탐침 158: 7일 32건 — 출입처 기사와 주말 당직 기사(국제·정치)가 섞여 있었다.
  네이버 뉴스 검색 API는 기자 이름으로 찾지 못했다(탐침 155: 아이뉴스24 0건).
- 대조: reverse_prior_capture.match — 같은 회사(그룹) 레이더 항목을 기사 60일 전~직전에 처음 봤고 사건 낱말이 겹치면 '먼저 잡은 후보'.
  같은 사건인지는 열어 봐야 한다. 결과는 기자 전용 저장소(my-articles)로만(레이더 기억에 기자 전용 항목이 있다). 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import reverse_prior_capture as rpc  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "my_articles/v1"
AUTHOR = "홍성효"
SITEMAP = "https://www.inews24.com/sitemap.xml"
GOOGLE = "https://news.google.com/rss/search"
UA = {"User-Agent": "seoul-reporting-radar (newsroom research; own byline check)"}
PAUSE = 1.5
OPEN_BUDGET = 80
KEEP_DAYS = 120
WINDOW_DAYS = 30
# 제목에서 출입처 찾기(대조용 회사 이름). 계열사(포스코퓨처엠·포스코인터내셔널·포스코이앤씨, LG에너지솔루션, SK온 등)는 출입처가 아니다.
BEAT_RX = [
    ("현대차", r"현대(?:자동)?차(?!증권|그룹\s?정몽)|현대자동차|제네시스"), ("기아", r"(?<![가-힣])기아(?!\s?(?:타이거즈|퇴치|문제|아동))"),
    ("현대모비스", r"현대모비스"), ("현대위아", r"현대위아"), ("HL만도", r"HL만도|(?<![가-힣])만도(?![가-힣])"),
    ("한국GM", r"한국\s?(?:GM|지엠)|GM\s?한국"), ("KG모빌리티", r"KG\s?모빌리티|KGM"), ("르노코리아", r"르노코리아"),
    ("벤츠", r"벤츠|메르세데스"), ("BMW", r"BMW"), ("폭스바겐", r"폭스바겐|아우디"), ("혼다", r"혼다"),
    ("한국타이어", r"한국타이어"), ("넥센타이어", r"넥센타이어"), ("금호타이어", r"금호타이어"),
    ("포스코", r"포스코(?!퓨처엠|인터내셔널|이앤씨|E&C|DX|엠텍|플로우|리튬|스틸리온|와이드|휴먼스)"), ("현대제철", r"현대제철"),
    ("KG스틸", r"KG스틸"), ("세아제강", r"세아(?:제강|홀딩스)"), ("동국제강", r"동국제강"), ("동국씨엠", r"동국씨엠"),
    ("고려아연", r"고려아연"), ("영풍", r"영풍(?!문고)|석포제련소"),
    ("HD현대일렉트릭", r"현대일렉트릭"), ("LS일렉트릭", r"LS\s?일렉트릭|LS\s?ELECTRIC"), ("대한전선", r"대한전선"), ("LS전선", r"LS\s?전선"),
    ("LS", r"LS\s?MnM|LS엠앤엠|(?<![A-Za-z])LS(?:그룹)?(?=\s|,|·|…|$)"), ("두산에너빌리티", r"두산에너빌리티"),
    ("GS칼텍스", r"GS\s?칼텍스"), ("한화솔루션", r"한화솔루션|한화큐셀"), ("OCI", r"OCI"), ("태광", r"태광산업|태광그룹"),
    ("동성케미칼", r"동성케미칼"), ("DL케미칼", r"DL케미칼"),
    ("LG화학", r"LG화학"), ("롯데케미칼", r"롯데케미칼"), ("금호석유화학", r"금호석유화학|금호석화"),
    ("S-OIL", r"S-?OIL|에쓰오일|에쓰-오일"), ("SK이노베이션", r"SK이노베이션"), ("HD현대오일뱅크", r"현대오일뱅크"),
]
BEAT = [(name, re.compile(rx, re.I)) for name, rx in BEAT_RX]


def companies_in(title):
    return [name for name, rx in BEAT if rx.search(title or "")]


def clean_title(t):
    return re.sub(r"\s+-\s+아이뉴스24\s*$", "", html.unescape(str(t or ""))).strip()


def parse_sitemap(xml_text):
    """[{url, title, published}] — news 사이트맵(<url><loc>…</loc><news:publication_date>…<news:title>…)."""
    out = []
    for block in re.findall(r"<url>(.*?)</url>", xml_text or "", re.S):
        loc = re.search(r"<loc>\s*([^<]+?)\s*</loc>", block)
        when = re.search(r"<news:publication_date>\s*([^<]+?)\s*</news:publication_date>", block)
        title = re.search(r"<news:title>(.*?)</news:title>", block, re.S)
        if not (loc and "/view/" in loc.group(1) and when and title):
            continue
        t = rpc.parse_time(when.group(1))
        if not t:
            continue
        out.append({"url": loc.group(1).strip(), "title": clean_title(re.sub(r"<!\[CDATA\[|\]\]>", "", title.group(1))),
                    "published": t.astimezone(KST).isoformat(timespec="seconds")})
    return out


def author_of(page):
    m = re.search(r'<meta[^>]+property="(?:og:)?article:author"[^>]*content="([^"]*)"', page or "")
    return html.unescape(m.group(1)).strip() if m else None


def google_backfill(get, now):
    """처음 실행용: 구글 뉴스 제목 색인(작성자 메타 미확인)."""
    q = {"q": f'"{AUTHOR}" site:inews24.com when:{WINDOW_DAYS}d', "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    r = get(GOOGLE + "?" + urllib.parse.urlencode(q), headers=UA, timeout=25)
    if getattr(r, "status_code", 200) != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    out = []
    for it in ET.fromstring(r.content).findall(".//item"):
        try:
            when = parsedate_to_datetime(it.findtext("pubDate") or "").astimezone(KST)
        except (TypeError, ValueError, IndexError):
            continue
        if when < now - dt.timedelta(days=WINDOW_DAYS):
            continue
        out.append({"url": None, "title": clean_title(it.findtext("title")), "published": when.isoformat(timespec="seconds"), "verified": False})
    return out


def key_of(a):
    return re.sub(r"\s", "", a.get("title") or "")[:60] + "|" + str(a.get("published") or "")[:10]


def run(now, previous=None, docs=None, clues=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    checked = dict(prev.get("checked") or {})
    mine = {key_of(a): a for a in prev.get("mine") or [] if isinstance(a, dict)}
    errors, opened, entries, cands, found = [], 0, [], [], 0
    try:
        r = get(SITEMAP, headers=UA, timeout=30)
        if getattr(r, "status_code", 200) != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        entries = parse_sitemap(r.text)
    except Exception as e:  # noqa: BLE001
        errors.append(f"사이트맵:{type(e).__name__}")
    cands = [e for e in entries if e["url"] not in checked and companies_in(e["title"])]
    for e in cands[:OPEN_BUDGET]:
        sleep(PAUSE)
        opened += 1
        try:
            page = get(e["url"], headers=UA, timeout=25)
            if getattr(page, "status_code", 200) != 200:
                raise RuntimeError(f"HTTP {page.status_code}")
            who = author_of(page.text)
        except Exception as ex:  # noqa: BLE001
            errors.append(f"기사:{type(ex).__name__}")
            continue   # 다음 실행에 다시(사이트맵에 남아 있으면)
        checked[e["url"]] = who or ""
        if who == AUTHOR:
            found += 1
            a = {**e, "companies": companies_in(e["title"]), "verified": True}
            # 구글 색인으로 먼저 넣은 같은 기사(제목·날짜)는 확인된 것으로 바꾼다
            mine.pop(key_of(a), None)
            mine[key_of(a)] = a
    backfill = None
    if not prev.get("backfilledAt"):
        try:
            got = google_backfill(get, now)
            for a in got:
                a["companies"] = companies_in(a["title"])
                mine.setdefault(key_of(a), a)
            backfill = len(got)
        except Exception as e:  # noqa: BLE001
            errors.append(f"구글 색인:{type(e).__name__}")
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    mine_list = sorted((a for a in mine.values() if str(a.get("published")) >= keep), key=lambda a: a["published"], reverse=True)
    # 레이더 기억과 대조(최근 30일 기사)
    adapter_errors = {}
    items = rpc.memory(docs or {}, clues or {}, adapter_errors)
    since = (now - dt.timedelta(days=WINDOW_DAYS)).isoformat(timespec="seconds")
    rows, hits = [], {}
    for a in mine_list:
        if str(a["published"]) < since:
            continue
        verdict, best, n = rpc.match({"published": a["published"], "title": a["title"], "companies": a.get("companies") or []}, items)
        rows.append({**{k: a.get(k) for k in ("url", "title", "published", "companies", "verified")}, "verdict": verdict, "best": best, "sameCompanyItems": n})
        if verdict == "먼저 잡은 후보" and best:
            hits.setdefault(best["id"], {"title": a["title"], "published": a["published"], "url": a.get("url"), "verified": a.get("verified", False)})
    by_source = {}
    for r_ in rows:
        if r_["verdict"] == "먼저 잡은 후보":
            s = by_source.setdefault(r_["best"]["label"], {"caught": 0, "lead": []})
            s["caught"] += 1
            s["lead"].append(r_["best"]["leadHours"])
    counts = {v: sum(1 for r_ in rows if r_["verdict"] == v) for v in ("먼저 잡은 후보", "같은 회사 항목만", "없음", "회사 미상")}
    status = "failed" if not entries and errors and not backfill else "partial" if errors else "complete"
    pending = max(0, len(cands) - OPEN_BUDGET)
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "author": AUTHOR,
            **({"backfilledAt": prev.get("backfilledAt") or (stamp if backfill is not None else None)} if (prev.get("backfilledAt") or backfill is not None) else {}),
            "checks": [{"source": "아이뉴스24 뉴스 사이트맵", "status": "failed" if status == "failed" else "partial" if errors else "ok",
                        "returned": len(entries), "candidates": len(cands), "opened": opened, **({"pending": pending} if pending else {}),
                        "mineNew": found,
                        **({"backfill": backfill} if backfill is not None else {}),
                        **({"error": "; ".join(errors[:4])} if errors else {})}],
            "checked": dict(list(checked.items())[-4000:]), "mine": mine_list[:600],
            "articles": rows, "counts": counts, "bySource": {k: {"caught": v["caught"], "leadHoursMedian": median(v["lead"])}
                                                             for k, v in sorted(by_source.items(), key=lambda t: -t[1]["caught"])},
            "itemHits": hits, "memoryItems": len(items), "adapterErrors": adapter_errors,
            "rules": [f"기자({AUTHOR}) 기사는 아이뉴스24 사이트맵에서 제목에 출입처 이름이 든 기사의 작성자 메타로 확인한다(verified). "
                      "출입처 이름이 제목에 없는 기사(업계 전체 기사)·당직 기사는 대조에서 빠진다.",
                      "첫 실행의 지난 30일은 구글 뉴스 제목 색인(작성자 미확인, verified=false)이다.",
                      "'먼저 잡은 후보'는 같은 회사(그룹) 레이더 항목을 기사 60일 전~직전에 처음 봤고 사건 낱말이 겹친 경우다. 같은 사건인지는 열어 봐야 한다.",
                      "기자 판정(씀·킬·보류·봤음)과 별개인 자동 기록이다. 안 쓴 항목은 이유를 모르므로 킬로 세지 않는다."]}


def main():
    import private_store
    now = dt.datetime.now(KST).replace(microsecond=0)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("MCP_ACCESS_TOKEN 미설정 — 레이더 기억을 읽을 수 없음(미확인)")
    previous = None
    try:
        previous = private_store.get("my-articles", token)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"이전 결과 조회 실패: {type(e).__name__}(기준을 잃지 않게 멈춤)")
    docs, failed = {}, []
    for f in rpc.FEEDS:
        try:
            d = private_store.get(f, token)
            if isinstance(d, dict):
                docs[f] = d
        except Exception as e:  # noqa: BLE001
            failed.append(f"{f}:{type(e).__name__}")
    clues = json.loads((ROOT / "tools" / "clues.json").read_text(encoding="utf-8"))
    doc = run(now, previous, docs, clues)
    doc["feedsFailed"] = failed
    c = doc["checks"][0]
    print(f"::notice title=my-articles::상태 {doc['status']} · 사이트맵 {c['returned']} · 출입처 제목 새 기사 {c['candidates']} · 열람 {c['opened']}"
          f" · 기자 기사(30일) {len(doc['articles'])} · {json.dumps(doc['counts'], ensure_ascii=False)}"
          + (f" · 구글 색인 채움 {c['backfill']}" if "backfill" in c else "") + (f" · 감시 조회 실패 {failed}" if failed else "")
          + (f" · {c['error']}" if c.get("error") else ""))
    try:
        status = private_store.put("my-articles", doc, token)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"저장 실패: {type(e).__name__}")
    print(f"::notice title=my-articles-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
