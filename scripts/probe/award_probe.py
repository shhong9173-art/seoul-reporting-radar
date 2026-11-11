"""probe 210: 무역위 보도자료 상세 본문·첨부 — 판정 보도자료에 신청인(국내 생산자) 이름이 적히는지.
공개 자료. 저장 안 함. 요청 사이 1초. 목록 3쪽·상세 최대 14건."""
import re
import sys
import time

sys.path.insert(0, "scripts")
import requests  # noqa: E402
import ktc_watch as k  # noqa: E402

OUT = []


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


http = k.Http(requests.Session())
rows = []
for page in (1, 2, 3):
    body = None
    try:
        body = http.post(k.NEWS[0], {"menuId": k.NEWS[1], "pageIndex": str(page)})
    except Exception as e:  # noqa: BLE001
        log("LIST", page, "ERR", type(e).__name__)
    got = k.parse_news(body) if body else []
    log("LIST", page, len(got))
    rows += got
    time.sleep(1)
seen = set()
pick = [r for r in rows if re.search(r"덤핑|관세|판정|조사|세이프가드", r["title"]) and not (r["id"] in seen or seen.add(r["id"]))][:14]
for r in pick:
    time.sleep(1)
    try:
        raw = http.get("/boardView.do", {"bbs_id": r["id"], "menuId": "57"})
    except Exception as e:  # noqa: BLE001
        log("D", r["id"], "ERR", type(e).__name__)
        continue
    t = k.plain(raw or "")
    i = t.find(r["title"][:10])
    body = t[i:i + 2500] if i >= 0 else t[:2500]
    files = re.findall(r"(?:fileDown|download)[^'\"]*['\"]([^'\"]+)['\"]", raw or "")[:4]
    fnames = re.findall(r"[\w가-힣()\-\s\.]+\.(?:hwp|hwpx|pdf|docx)", raw or "")[:4]
    log("D", r["id"], r["title"][:50], "| len", len(t), "| files", fnames)
    for m in re.finditer(r"신청", body):
        log("   ctx:", body[max(0, m.start() - 90):m.end() + 40].replace("\n", " "))
    if "신청" not in body:
        log("   head:", body[:400])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
