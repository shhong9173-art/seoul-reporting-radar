"""노조 성명·보도자료 — 산별노조 공개 게시판에 출입처 이름이 나온 새 글(기자 전용 저장소 union-notices).

- 왜: 경쟁지 [단독] 30일 역추적에서 레이더가 못 잡은 26건 중 노사·안전 기사(포스코 임단협 재개, 현대제철 노동자 사망, 기아 노조원
  정보 유출, 현대모비스 램프사업 분할 가처분, 현대제철 경조휴가 차별)가 많았다. 노조는 성명·보도자료를 자기 게시판에 먼저 올린다.
- 원천(11-03 탐침 146·148): 금속노조(kmwu.kr) '보도자료/성명'(ce_B12) — robots.txt는 /adm/만 막음, 11-03 「[보도자료] 현대위아 특수사업부
  노동…」·「[보도자료] 금호타이어 광주공장 끼임…」. 화섬식품노조(kctfu.org) '보도자료/성명'(bodo)·'주요소식'(news) — robots.txt 없음.
  둘 다 그누보드(목록 → 글: <title>·bo_v_info '작성일 26-11-03 21:34'·bo_v_con 본문).
- 새 글(본 wr_id 아님)만 글을 열어 제목·본문 앞부분에서 출입처 이름을 찾는다(요청 2초 간격, 게시판마다 한 실행 15건 —
  금속노조 누리집은 robots.txt Crawl-delay 180초를 지켜 181초 간격·게시판마다 2건, 11-08).
- 등급: 제목·본문 첫머리에 사망·사고·파업·쟁의·결렬·폐쇄·매각·분할·구조조정·해고·가처분·고발·원청 교섭 같은 낱말이 있으면 A, 아니면 B.
  출입처 이름이 제목에 없고 본문에만 있으면 한 단계 내린다.
- 노조 발표는 한쪽 주장이다 — 회사 입장·사실관계(사고 경위·교섭 일정)는 확인해야 한다. 첫 실행은 기준선. 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "union_notices/v1"
UA = {"User-Agent": "seoul-reporting-radar (newsroom research; union public statements)"}
BOARDS = [("금속노조 보도자료/성명", "https://www.kmwu.kr", "ce_B12"),
          ("화섬식품노조 보도자료/성명", "https://kctfu.org", "bodo"),
          ("화섬식품노조 주요소식", "https://kctfu.org", "news"),
          # 지부·지회 소식(11-08 탐침 201): 금속노조 '지역소식'(ce_B13) — 인천·구미·경주지부 소식지, 금속충남통신, GGM지회 단식농성 등.
          # 현대차지부·기아지부 같은 개별 노조 누리집은 GitHub에서 주소가 열리지 않았다(hhu.or.kr 등 연결 실패).
          ("금속노조 지역소식(지부·지회)", "https://www.kmwu.kr", "ce_B13")]
PAUSE = 2.0
PER_BOARD = 15
# robots.txt 'Crawl-delay: 180'(kmwu.kr, 11-08 탐침 200 확인 — 11-03 탐침 때는 /adm/ 막음만 보고 2초 간격으로 읽었다). 같은 누리집 요청 사이
# 181초를 둔다. 그래서 이 누리집은 게시판마다 한 실행에 글 2개까지만 열고(나머지는 다음 실행), 실행은 최대 약 15분이 걸린다.
CRAWL_DELAY = {"https://www.kmwu.kr": 181.0}
SLOW_PER_BOARD = 2
KEEP_DAYS = 60
UNION_BEATS = [
    ("현대차", r"현대자동차|현대차(?!증권)"), ("기아", r"기아(?=차|자동차|지부|지회|노조|사측|노동자|오토랜드)|기아(?![가-힣])"),
    ("현대모비스", r"현대모비스|(?<![가-힣])모비스"), ("현대위아", r"현대위아"), ("HL만도", r"(?:HL|에이치엘)\s?만도|(?<![가-힣])만도(?![가-힣])"),
    ("한국GM", r"한국\s?(?:GM|지엠)"), ("KG모빌리티", r"(?:KG|케이지)\s?모빌리티"), ("르노코리아", r"르노코리아"),
    ("한국타이어", r"한국타이어"), ("넥센타이어", r"넥센타이어"), ("금호타이어", r"금호타이어"),
    ("포스코", r"포스코(?!퓨처엠|인터내셔널|이앤씨|DX|엠텍|플로우|스틸리온|홀딩스|케미칼)"), ("현대제철", r"현대제철"),
    ("KG스틸", r"(?:KG|케이지)\s?스틸"), ("세아제강", r"세아제강"), ("동국제강", r"동국제강"), ("동국씨엠", r"동국씨엠"),
    ("고려아연", r"고려아연"), ("영풍", r"영풍(?=제련소|석포|그룹|\s|$|,|·|은|는|이|가|의|에)|석포제련소"),
    ("HD현대일렉트릭", r"(?:HD|에이치디)?\s?현대일렉트릭"), ("LS일렉트릭", r"(?:LS|엘에스)\s?일렉트릭"), ("대한전선", r"대한전선"),
    ("LS전선", r"(?:LS|엘에스)\s?전선"), ("LS MnM", r"(?:LS|엘에스)\s?(?:MnM|엠앤엠)"), ("두산에너빌리티", r"두산에너빌리티"),
    ("GS칼텍스", r"(?:GS|지에스)\s?칼텍스"), ("한화솔루션", r"한화솔루션|한화큐셀"), ("OCI", r"(?<![가-힣A-Za-z])OCI(?!\s?홀딩스)|오씨아이"),
    ("태광", r"태광산업"), ("동성케미칼", r"동성케미칼"), ("DL케미칼", r"(?:DL|디엘)\s?케미칼"), ("LG화학", r"(?:LG|엘지)\s?화학"),
    ("롯데케미칼", r"롯데케미칼"), ("금호석유화학", r"금호석유화학|금호석화"), ("S-OIL", r"에쓰\s?-?\s?오일|S-?OIL"),
    ("SK이노베이션", r"(?:SK|에스케이)\s?이노베이션"), ("HD현대오일뱅크", r"현대오일뱅크"),
]
BEAT_RX = [(k, re.compile(v, re.I)) for k, v in UNION_BEATS]
A_WORDS = re.compile(r"사망|숨져|숨진|중대재해|끼임|추락|폭발|화재|파업|쟁의|결렬|폐쇄|매각|분할|구조조정|희망퇴직|해고|가처분|고발|고소|"
                     r"원청\s?교섭|교섭\s?거부|불법\s?파견|직장\s?폐쇄|감산|휴업|공장\s?이전|철수")


def tidy(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def beats_in(text):
    hits = []
    for k, rx in BEAT_RX:
        m = rx.search(text or "")
        if m:
            hits.append((m.start(), k))
    return [k for _, k in sorted(hits)]


def list_ids(page, bo):
    out = []
    for wid in re.findall(r'bo_table=' + re.escape(bo) + r'&(?:amp;)?wr_id=(\d+)', page or ""):
        if wid not in out:
            out.append(wid)
    return out


def parse_post(page):
    title = re.search(r'<h2[^>]*id="bo_v_title"[^>]*>(.*?)</h2>', page, re.S)
    title = tidy(title.group(1)) if title else tidy((re.search(r"<title>(.*?)</title>", page, re.S) or [None, ""])[1]).split(" > ")[0]
    title = re.sub(r"^(?:보도자료|성명|주요소식)\s+", "", title).strip()
    info = page.find("bo_v_info")
    date = None
    m = re.search(r"작성일\s*(\d{2})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})", tidy(page[info: info + 1500]) if info >= 0 else "")
    if m:
        date = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:00+09:00"
    con = page.find("bo_v_con")
    body = tidy(re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page[con: con + 60000])) if con >= 0 else ""
    body = re.sub(r'^bo_v_con"?[^>]*>\s*', "", body)
    return {"title": title, "date": date, "body": body}


def tier_of(title, body, in_title):
    t = "A" if A_WORDS.search(title) or A_WORDS.search(body[:600]) else "B"
    if not in_title:
        t = {"A": "B", "B": "C"}[t]
    return t


def run(now, previous=None, *, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    seen = {k: list(v) for k, v in (prev.get("seen") or {}).items()}
    known = {x["id"]: x for x in prev.get("posts") or [] if isinstance(x, dict) and x.get("id")}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict)]
    checks = []
    used = set()

    def wait(base):
        # 같은 누리집은 robots.txt Crawl-delay만큼, 다른 누리집으로 넘어갈 때는 2초
        if base in used:
            sleep(CRAWL_DELAY.get(base, PAUSE))
        elif used:
            sleep(PAUSE)
        used.add(base)

    for label, base, bo in BOARDS:
        key = f"{base}|{bo}"
        first = key not in seen
        wait(base)
        try:
            r = get(f"{base}/bbs/board.php", params={"bo_table": bo}, headers=UA, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            ids = list_ids(r.text, bo)
            if not ids:
                raise RuntimeError("목록 0줄 — 형식 바뀜일 수 있음")
        except Exception as e:  # noqa: BLE001
            checks.append({"source": label, "status": "failed", "returned": 0, "error": f"{type(e).__name__}: {str(e)[:60]}"})
            continue
        if first:   # 첫 실행: 지금 목록은 기준선(글은 열지 않는다)
            seen[key] = ids[:200]
            checks.append({"source": label, "status": "ok", "returned": len(ids), "note": "첫 실행 기준선"})
            continue
        new = [i for i in ids if i not in seen[key]][:SLOW_PER_BOARD if base in CRAWL_DELAY else PER_BOARD]
        bad = 0
        for wid in new:
            wait(base)
            try:
                d = get(f"{base}/bbs/board.php", params={"bo_table": bo, "wr_id": wid}, headers=UA, timeout=30)
                if d.status_code != 200:
                    raise RuntimeError(f"HTTP {d.status_code}")
                post = parse_post(d.text)
            except Exception:  # noqa: BLE001
                bad += 1
                continue   # 다음 실행에 다시
            seen[key] = ([wid] + seen[key])[:300]
            in_title = beats_in(post["title"])
            comps = list(dict.fromkeys(in_title + beats_in(post["body"][:2000])))
            if not comps:
                continue
            tier = tier_of(post["title"], post["body"], bool(in_title))
            pid = f"un:{bo}:{wid}"
            m = next(rx.search(post["body"]) for k, rx in BEAT_RX if k == comps[0]) if not in_title and comps else None
            excerpt = (post["body"][max(0, m.start() - 80): m.end() + 160] if m else post["body"][:240]).strip()
            rec = {"id": pid, "board": label, "title": post["title"][:200], "date": post["date"], "companies": comps, "company": comps[0],
                   "tier": tier, "inTitle": bool(in_title), "excerpt": excerpt[:260], "url": f"{base}/bbs/board.php?bo_table={bo}&wr_id={wid}",
                   "firstSeen": stamp}
            known[pid] = rec
            if tier in ("A", "B"):
                events.append({"id": pid, "tier": tier, "kind": "노조 성명·보도자료", "company": comps[0], "board": label, "title": rec["title"],
                               "detectedAt": stamp, "url": rec["url"],
                               "text": (f"{label} 「{rec['title']}」({(post['date'] or '')[:16].replace('T', ' ') or '게시 시각 미확인'})"
                                        + (f" · 출입처 {'·'.join(comps)}" if len(comps) > 1 else "")
                                        + ("" if in_title else " · 이름은 본문에만") + f" · 앞부분 「{excerpt[:200]}」"
                                        + " · 노조 발표(한쪽 주장) — 회사 입장·사실관계 확인")})
        checks.append({"source": label, "status": "ok" if not bad else "partial", "returned": len(ids), "opened": len(new) - bad,
                       **({"error": f"글 {bad}건 읽기 실패"} if bad else {})})
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    ok = [c for c in checks if c["status"] != "failed"]
    status = "failed" if not ok else "complete" if all(c["status"] == "ok" for c in checks) else "partial"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "seen": seen,
            "posts": sorted((x for x in known.values() if str(x.get("firstSeen")) >= keep), key=lambda x: str(x.get("date") or x.get("firstSeen")), reverse=True)[:300],
            "events": sorted((e for e in events if str(e.get("detectedAt")) >= keep), key=lambda e: e["detectedAt"], reverse=True)[:200],
            "rules": ["금속노조·화섬식품노조 공개 게시판(보도자료·성명·주요소식, 금속노조 지역소식의 지부·지회 소식지)의 새 글 중 제목·본문 앞부분에 출입처 이름이 나온 것. 노조 발표는 한쪽 주장이다 — 회사 입장·사실관계 확인.",
                      "금속노조 누리집은 robots.txt의 요청 간격(180초)을 지켜 게시판마다 한 실행에 글 2개까지만 연다 — 새 글이 많으면 다음 실행으로 넘어간다(늦게 잡힐 수 있음).",
                      "사망·사고·파업·쟁의·결렬·폐쇄·매각·분할·구조조정·해고·가처분·고발·원청 교섭 낱말이 있으면 A, 아니면 B. 이름이 본문에만 있으면 한 단계 내림.",
                      "첫 실행은 기준선(그때 목록의 글은 열지 않음). 조회 실패 게시판은 0건이 아니라 미확인."]}


def main():
    import private_store
    now = dt.datetime.now(KST).replace(microsecond=0)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("union-notices", token)
        except private_store.StoreError as e:
            print(f"::warning title=union-notices-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
        if private_store.late_scheduled_duplicate(previous, now, hours=2):
            return
    doc = run(now, previous)
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=union-notices::상태 {doc['status']} · 보관 {len(doc['posts'])}건 · 이번 새 이벤트 {len(new)} · "
          + " / ".join(f"{c['source']} {c['status']}({c.get('returned', 0)}, 연 글 {c.get('opened', 0)})" for c in doc["checks"]))
    if not token:
        print("::warning title=union-notices-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("노조 게시판 조회 전체 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("union-notices", doc, token)
    print(f"::notice title=union-notices-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
