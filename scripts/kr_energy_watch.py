"""전기위원회·원자력안전위원회 감시: 발전사업 허가·인가와 원안위 상정 안건·의결 결과.

- 전기위원회(기후에너지환경부) '위원회 개최결과' PDF: 회차마다 허가·조건부 허가·변경허가·허가 취소된 발전사업 이름.
  출입처 그룹 이름(GS·한화·두산·OCI·LS·포스코·현대 등)이 사업명에 있으면 A, 해상풍력 허가는 B(전선·변압기 수요와의
  연결은 가설), 나머지 C.
- 전기위원회 '3MW 초과 발전사업 허가대장' PDF(분기): 새 판이 올라오면 최근 허가·변경일 줄 중 출입처 그룹 상호만.
- 원자력안전위원회 '일정/회의결과/회의록': 회의 며칠 전 올라오는 상정 안건과 뒤에 붙는 의결 결과.
  건설허가·운영허가·표준설계인가·SMR = A, 계속운전·사용후핵연료 등 = B, 나머지 C.
- 결과는 기자 전용 저장소(kr-energy)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html as htmlmod
import io
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_energy/v1"
B = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml"}
KOREC = "https://www.korec.go.kr"
KOREC_RESULTS = KOREC + "/notice/result/selectNoticeList.do"
KOREC_NOTICES = KOREC + "/notice/selectNoticeList.do"
KOREC_FILE = KOREC + "/commonfile/fileDownLoad.do"
NSSC = "https://www.nssc.go.kr"
NSSC_PAGE = NSSC + "/ko/cms/FR_CON/index.do?MENU_ID=170"
NSSC_LIST = NSSC + "/ajaxf/FR_BBS_SVC/BBSViewList.do"
KEEP_DAYS = 200
LEDGER_DAYS = 120
FIRST_RUN_MEETINGS = 2
MAX_NEW_MEETINGS = 4

# 출입처 그룹 이름(사업명·상호). 계열사도 그룹으로 묶되 표시는 출입처 이름.
GROUPS = [
    ("GS칼텍스", r"GS\s*칼텍스|지에스\s*칼텍스"),
    ("GS", r"(?<![A-Za-z])GS(?![A-Za-z])|지에스"),
    ("한화솔루션", r"한화|큐셀"),
    ("두산에너빌리티", r"두산"),
    ("OCI", r"OCI|오씨아이"),
    ("LS", r"(?<![A-Za-z])LS(?![A-Za-z])|엘에스"),
    ("포스코", r"포스코|POSCO"),
    ("HD현대일렉트릭", r"HD\s*현대일렉트릭|현대일렉트릭"),
    ("현대제철", r"현대제철"),
    ("현대차", r"현대자동차|현대차(?!량)|기아(?:자동차|\(주\)|\s*주식회사)"),
    ("효성중공업(관련)", r"효성"),
    ("고려아연", r"고려아연|아크에너지"),
    ("영풍", r"영풍"),
    ("세아", r"세아"),
    ("동국제강", r"동국제강|동국씨엠"),
    ("KG스틸", r"KG\s*스틸|케이지스틸"),
    ("태광", r"태광산업"),
    ("DL케미칼", r"DL\s*케미칼|디엘케미칼"),
    ("한국타이어", r"한국타이어"),
]
GROUP_RX = [(name, re.compile(rx)) for name, rx in GROUPS]
OFFSHORE = re.compile(r"해상\s*풍력")
NUKE_A = re.compile(r"건설\s*허가|운영\s*허가|표준설계\s*인가|SMR|소형\s*모듈")
NUKE_B = re.compile(r"계속\s*운전|사용후\s*핵연료|고준위|재가동|영구\s*정지|해체")
RULES = [
    "전기위원회 허가는 사업 허가 단계다. 착공·준공·발주(케이블·변압기 수주)와는 다르다 — 연결은 가설.",
    "개최결과 PDF의 사업명만으로 사업자를 단정하지 않는다. 출입처 그룹 이름은 사업명·허가대장 상호에 적힌 그대로.",
    "원안위 상정 안건은 회의 전 공개다. 의결 결과가 붙기 전에는 '상정'만 사실.",
]


def norm_space(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def group_of(text):
    for name, rx in GROUP_RX:
        if rx.search(text or ""):
            return name
    return None


def _get(get, url, **kw):
    if get is None:
        import requests
        get = requests.get
    return get(url, headers=kw.pop("headers", B), timeout=kw.pop("timeout", 40), **kw)


def _post(post, url, **kw):
    if post is None:
        import requests
        post = requests.post
    return post(url, headers=kw.pop("headers", B), timeout=kw.pop("timeout", 60), **kw)


def pdf_text(raw):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)


def korec_file(name, *, post=None):
    url = KOREC_FILE + "?" + urllib.parse.urlencode({"attachingFilePath": "/notice", "attachingFileNm": name})
    r = _post(post, url, timeout=150)
    if r.status_code != 200 or r.content[:4] != b"%PDF":
        raise RuntimeError(f"PDF HTTP {r.status_code}")
    return r.content, url


# ---------------------------------------------------------------- 전기위원회 개최결과
def result_rows(page_html):
    """[(title, posted, file name)] newest first from the 위원회 개최결과 list."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page_html, re.S | re.I):
        f = re.search(r"cf_downloadFile\('/notice','([^']+\.pdf)'\)", row)
        title = re.search(r'title="([^"]*전기위원회[^"]*)"', row)
        day = re.search(r"(20\d{2}-\d{2}-\d{2})", re.sub(r"<[^>]+>", " ", row))
        if f and title:
            out.append((htmlmod.unescape(title.group(1)).strip(), day.group(1) if day else None, htmlmod.unescape(f.group(1))))
    return out


SECTION = re.compile(r"(조건부\s*허가|조건부\s*인가|허가\s*취소|허가|인가|승인)\s*건\s*\(\s*\d+\s*\)")
PROJECT = re.compile(r"(?:\d+\.\s*)?([가-힣A-Za-z0-9·ㆍ&\(\)\-\s]{2,60}?발전사업)\s*(변경\s*허가|허가\s*취소|허가)?\s*(?:\(\s*안\s*\)|안)")


def meeting_items(text):
    """Projects under the 허가·조건부 허가·허가 취소 sections of one 개최결과 PDF."""
    t = re.sub(r"[ \t]+", " ", text)
    t = re.sub(r"\s*\n\s*", "\n", t)
    flat = t.replace("\n", " ")
    counts = {norm_space(k): int(v) for k, v in re.findall(r"ㅇ\s*(조건부\s*허가|조건부\s*인가|허가\s*취소|허가|인가|승인)\s*건\s*:\s*(\d+)", flat)}
    md = re.search(r"[`'‘’]\s*(\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.", flat)
    held = f"20{md.group(1)}-{int(md.group(2)):02d}-{int(md.group(3)):02d}" if md else None
    marks = [(m.start(), norm_space(m.group(1))) for m in SECTION.finditer(flat)]
    items, seen = [], set()
    for i, (start, sec) in enumerate(marks):
        if sec not in ("허가", "조건부 허가", "허가 취소"):
            continue
        end = marks[i + 1][0] if i + 1 < len(marks) else len(flat)
        for m in PROJECT.finditer(flat[start:end]):
            raw = norm_space(m.group(1))
            held_back = bool(re.search(r"보류", raw))
            # the regex span can start inside the previous sentence: keep what follows the last 허가/보류/건(n)/후
            name = re.sub(r"^.*(?:허가|보류|건\s*\(\s*\d+\s*\)|확인\s*후|후)\s+", "", raw)
            name = norm_space(re.sub(r"^[\d\.\s()]+|^[①-⑳]\s*", "", name))
            if len(name) < 5 or name in seen:
                continue
            seen.add(name)
            act = norm_space(m.group(2) or "허가")
            kind = ("심의 보류" if held_back else "허가 취소" if sec == "허가 취소" or "취소" in act
                    else "변경허가" if "변경" in act else sec)
            items.append({"project": name, "kind": kind})
    return held, counts, items


def korec_meetings(previous, *, get=None, post=None, sleep=time.sleep):
    seen = set((previous or {}).get("korecSeen") or [])
    first = not previous
    r = _get(get, KOREC_RESULTS)
    if r.status_code != 200:
        raise RuntimeError(f"목록 HTTP {r.status_code}")
    rows = result_rows(r.text)
    if not rows:
        raise RuntimeError("목록 형식 미상")
    todo = [x for x in rows if x[2] not in seen][: (FIRST_RUN_MEETINGS if first else MAX_NEW_MEETINGS)]
    out, read = [], []
    for title, posted, name in todo:
        raw, url = korec_file(name, post=post)
        held, counts, items = meeting_items(pdf_text(raw))
        no = re.search(r"제\s*(\d+)\s*차", title)
        meeting = f"제{no.group(1)}차" if no else title
        read.append(name)
        summary = " · ".join(f"{k} {v}" for k, v in counts.items())
        out.append({"id": f"korec:{meeting}", "source": "전기위원회", "kind": "개최결과", "title": f"{meeting} 전기위원회 개최결과" + (f" — {summary}" if summary else ""),
                    "meeting": meeting, "held": held, "posted": posted, "company": None, "tier": "C", "url": url})
        for it in items:
            grp = group_of(it["project"])
            tier = "A" if grp else "B" if OFFSHORE.search(it["project"]) and it["kind"] not in ("허가 취소", "심의 보류") else "C"
            out.append({"id": f"korec:{meeting}:{hashlib.sha1(it['project'].encode()).hexdigest()[:10]}", "source": "전기위원회", "kind": it["kind"],
                        "title": it["project"], "meeting": meeting, "held": held, "posted": posted, "company": grp, "tier": tier, "url": url})
        sleep(1)
    keep = sorted(seen | set(read) | ({x[2] for x in rows[FIRST_RUN_MEETINGS:]} if first else set()))
    return out, {"source": "전기위원회 개최결과", "status": "ok", "returned": len(rows), "read": len(read)}, keep[-60:]


# ---------------------------------------------------------------- 전기위원회 허가대장
DATE = re.compile(r"(20\d{2})[-.](\d{2})[-.](\d{2})")
ROW_START = re.compile(r"^\d{1,5}\s+\S")


def ledger_rows(text, since_day):
    """Rows whose first date (허가 및 변경일) is on or after since_day, joined across wrapped lines."""
    rows, buf = [], []
    for line in (norm_space(x) for x in text.splitlines()):
        if not line or line.startswith(("NO 상호", "(동 자료는")):
            continue
        if ROW_START.match(line) and not DATE.search(line):
            buf = [line]
            continue
        buf.append(line)
        d = DATE.search(line)
        if d:
            day = f"{d.group(1)}-{d.group(2)}-{d.group(3)}"
            if day >= since_day:
                rows.append({"day": day, "text": " ".join(buf)[:300]})
            buf = []
    return rows


def korec_ledger(previous, now, *, get=None, post=None):
    seen = (previous or {}).get("ledgerFile")
    r = _get(get, KOREC_NOTICES)
    if r.status_code != 200:
        raise RuntimeError(f"공지 목록 HTTP {r.status_code}")
    files = [htmlmod.unescape(n) for n in re.findall(r"cf_downloadFile\('/notice','([^']+\.pdf)'\)", r.text) if "허가대장" in htmlmod.unescape(n)]
    if not files:
        raise RuntimeError("허가대장 파일 없음")
    name = files[0]
    if name == seen:
        return [], {"source": "전기위원회 허가대장", "status": "ok", "returned": 1, "note": "새 판 없음"}, name
    raw, url = korec_file(name, post=post)
    since = (now - dt.timedelta(days=LEDGER_DAYS)).date().isoformat()
    rows = ledger_rows(pdf_text(raw), since)
    out = []
    for row in rows:
        grp = group_of(row["text"])
        if not grp:
            continue
        out.append({"id": f"ledger:{hashlib.sha1(row['text'].encode()).hexdigest()[:12]}", "source": "전기위원회 허가대장", "kind": "허가대장 새 줄",
                    "title": row["text"], "meeting": None, "held": row["day"], "posted": None, "company": grp, "tier": "B",
                    "url": url, "ledger": re.sub(r"_w\d{14}", "", name)})
    return out, {"source": "전기위원회 허가대장", "status": "ok", "returned": len(rows), "matched": len(out)}, name


# ---------------------------------------------------------------- 원자력안전위원회
AGENDA = re.compile(r"\(\s*(심의\s*[∙·ㆍ‧]?\s*의결|보고)\s*제\s*(\d+)\s*호\s*\)\s*(.+?)(?=\s*-\s*\(\s*(?:심의|보고)|\s*[○ㅇ]\s|\s*구\s*분\s*안건|$)")
RESULTS = ("원안의결", "수정의결", "조건부의결", "보류", "부결", "철회", "보고접수", "접수")
SPLIT_RESULT = re.compile(r"[○ㅇ]\s*결과")


def compact(s):
    return re.sub(r"[\s·‧∙ㆍ•()（）「」｢｣\[\]]", "", s or "")


def nssc_post_items(subject, contents):
    text = norm_space(htmlmod.unescape(re.sub(r"<[^>]+>", " ", contents or "")))
    parts = SPLIT_RESULT.split(text, maxsplit=1)
    head, tail = parts[0], (parts[1] if len(parts) > 1 else "")
    ctail = compact(tail)
    items = []
    for kind, no, title in AGENDA.findall(head):
        title = norm_space(title).rstrip(" -")
        res = None
        key = compact(title)[:18]
        i = ctail.find(key) if key and ctail else -1
        if i >= 0:
            window = ctail[i + len(key): i + len(key) + 90]
            hits = [(window.find(w), w) for w in RESULTS if window.find(w) >= 0]
            res = min(hits)[1] if hits else None
        items.append({"no": int(no), "kind": "보고" if kind.startswith("보고") else "심의·의결", "title": title[:200], "result": res})
    md = re.search(r"\((\d{1,2})\.(\d{1,2})\)", subject or "")
    return md, items


def nssc(previous, now, *, get=None, post=None, session=None):
    import requests
    s = session or requests.Session()
    s.headers.update(B)
    s.get(NSSC_PAGE, timeout=30)
    body = {"pageNo": 1, "pagePerCnt": 15, "MENU_ID": 170, "CONTENTS_NO": "", "SITE_NO": 2, "BOARD_SEQ": 14, "BBS_SEQ": "", "USER_NAME": "",
            "TEL_NO": "", "WRITER_DI": "", "_csrf": "", "SEARCH_FLD": "", "SEARCH": ""}
    r = s.post(NSSC_LIST, data=body, timeout=30, headers={"Accept": "application/json, text/javascript, */*; q=0.01",
                                                          "X-Requested-With": "XMLHttpRequest", "Referer": NSSC_PAGE})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        lst = json.loads(r.text)["data"]["list"]
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("응답 형식 미상")
    out = []
    for p in lst:
        subject = norm_space(p.get("SUBJECT"))
        if not re.search(r"제\s*\d{4}-\d+\s*회", subject):
            continue
        md, items = nssc_post_items(subject, p.get("CONTENTS"))
        posted = str(p.get("WRITE_DATE") or "").replace(".", "-")[:10]
        held = f"{posted[:4]}-{int(md.group(1)):02d}-{int(md.group(2)):02d}" if md and posted[:4].isdigit() else None
        seq = p.get("BBS_SEQ")
        url = f"{NSSC}/ko/cms/FR_BBS_CON/BoardView.do?MENU_ID=170&SITE_NO=2&BOARD_SEQ=14&BBS_SEQ={seq}"
        for it in items:
            tier = "A" if NUKE_A.search(it["title"]) else "B" if NUKE_B.search(it["title"]) else "C"
            out.append({"id": f"nssc:{seq}:{it['no']}:{it['kind']}", "source": "원자력안전위원회", "kind": f"{it['kind']} 안건",
                        "title": it["title"], "meeting": subject, "held": held, "posted": posted, "company": None,
                        "result": it["result"], "tier": tier, "url": url})
    return out, {"source": "원자력안전위원회 회의", "status": "ok", "returned": len(lst), "matched": len(out)}


# ---------------------------------------------------------------- run
def run(*, now, previous=None, get=None, post=None, sleep=time.sleep, nssc_session=None):
    stamp = now.isoformat(timespec="seconds")
    baseline = not (isinstance(previous, dict) and previous.get("items") is not None)
    found, checks = [], []
    korec_seen = (previous or {}).get("korecSeen") or []
    ledger_file = (previous or {}).get("ledgerFile")
    try:
        got, chk, korec_seen = korec_meetings(None if baseline else previous, get=get, post=post, sleep=sleep)
        found += got
        checks.append(chk)
    except Exception as e:  # noqa: BLE001
        checks.append({"source": "전기위원회 개최결과", "status": "failed", "error": str(e)[:80] or type(e).__name__})
    try:
        got, chk, ledger_file = korec_ledger(None if baseline else previous, now, get=get, post=post)
        found += got
        checks.append(chk)
    except Exception as e:  # noqa: BLE001
        checks.append({"source": "전기위원회 허가대장", "status": "failed", "error": str(e)[:80] or type(e).__name__})
    try:
        got, chk = nssc(previous, now, get=get, post=post, session=nssc_session)
        found += got
        checks.append(chk)
    except Exception as e:  # noqa: BLE001
        checks.append({"source": "원자력안전위원회 회의", "status": "failed", "error": str(e)[:80] or type(e).__name__})

    old = {x["id"]: x for x in (previous or {}).get("items") or []}
    items = dict(old)
    found_ids = set()
    for it in found:
        prev = old.get(it["id"])
        found_ids.add(it["id"])
        it["firstSeen"] = prev["firstSeen"] if prev else stamp
        it["baseline"] = bool(prev.get("baseline")) if prev else baseline
        it["isNew"] = not prev and not baseline
        if prev and it.get("result") and it.get("result") != prev.get("result"):
            it["resultSeen"] = stamp  # 의결 결과가 새로 붙음
            it["isNew"] = not baseline
        elif prev:
            it["resultSeen"] = prev.get("resultSeen")
        items[it["id"]] = it
    for k, x in items.items():
        if k not in found_ids:
            x["isNew"] = False
    cut = (now - dt.timedelta(days=KEEP_DAYS)).date().isoformat()
    kept = sorted((x for x in items.values() if str(x.get("held") or x.get("posted") or x["firstSeen"])[:10] >= cut),
                  key=lambda x: (str(x.get("held") or x.get("posted") or ""), x["id"]), reverse=True)
    failed = [c for c in checks if c["status"] == "failed"]
    status = "failed" if len(failed) == len(checks) else "partial" if failed else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "items": kept[:500],
            "korecSeen": korec_seen, "ledgerFile": ledger_file, "rules": RULES,
            "baselineSince": (previous or {}).get("baselineSince") or stamp}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("kr-energy", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-energy-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(now=now, previous=previous)
    tiers = {}
    for x in doc["items"]:
        if x.get("isNew"):
            tiers[x["tier"]] = tiers.get(x["tier"], 0) + 1
    print(f"::notice title=kr-energy::상태 {doc['status']} · " + " · ".join(f"{c['source']} {c['status']}" for c in doc["checks"])
          + f" · 새 항목 {tiers} · 보관 {len(doc['items'])}")
    if not token:
        print("::warning title=kr-energy-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("전기위원회·원안위 전체 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-energy", doc, token)
    print(f"::notice title=kr-energy-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
