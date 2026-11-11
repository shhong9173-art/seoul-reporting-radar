"""probe 211: 무역위 보도자료 첨부 PDF — 내려받기 주소 꼴과 본문의 신청인 문구. 공개 자료. 저장 안 함. 요청 사이 1초, PDF 최대 8개."""
import io
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
for page in (1, 2, 3, 4):
    st, body = http.post(k.NEWS[0], {"menuId": k.NEWS[1], "pageIndex": str(page)})
    rows += k.parse_news(body) if body else []
    time.sleep(1)
pick = [r for r in rows if re.search(r"덤핑방지관세|판정|잠정|부과 건의|부과건의", r["title"])][:8]
log("rows", len(rows), "pick", len(pick))
first = True
for r in pick:
    time.sleep(1)
    st, raw = http.get("/boardView.do", {"bbs_id": r["id"], "menuId": "57"})
    raw = raw or ""
    links = re.findall(r"""(?:href|onclick)\s*=\s*["']([^"']*(?:[Ff]ile|[Dd]own)[^"']*)["']""", raw)
    if first:
        log("LINKS", r["id"], links[:6])
        first = False
    pdf = next((l for l in links if ".pdf" in l.lower() or "pdf" in l.lower()), None)
    # 자바스크립트 호출이면 인자를 뽑는다
    args = re.findall(r"""fn_?[Ff]ile[Dd]own\w*\(([^)]*)\)|fileDown\w*\(([^)]*)\)|download\w*\(([^)]*)\)""", raw)
    log("D", r["id"], r["title"][:40], "| pdf link", (pdf or "")[:160], "| args", [a for t in args[:4] for a in t if a][:4])
    url = None
    if pdf and pdf.startswith(("/", "http")):
        url = pdf if pdf.startswith("http") else k.SITE + pdf
    if not url:
        continue
    time.sleep(1)
    try:
        resp = http.s.get(url, headers=k.UA, timeout=60)
        log("   GET", resp.status_code, resp.headers.get("Content-Type"), len(resp.content))
        text, err = k.pdf_text(resp.content)
        if err:
            log("   PDF", err)
            continue
        t = re.sub(r"\s+", " ", text or "")
        log("   textlen", len(t))
        hits = [t[max(0, m.start() - 120):m.end() + 30] for m in re.finditer(r"신청", t)][:4]
        for h in hits:
            log("   ctx:", h)
        if not hits:
            log("   head:", t[:300])
    except Exception as e:  # noqa: BLE001
        log("   ERR", type(e).__name__)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
