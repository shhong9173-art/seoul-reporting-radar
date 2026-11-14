"""probe 231: 인도 DGTR robots.txt와 사건 페이지 HTML 꼴(일정표 줄·날짜·PDF 주소·File No.). 공개 페이지만, 저장 안 함."""
import re
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})
CASES = ["https://www.dgtr.gov.in/en/anti-dumping-cases/anti-dumping-investigation-concerning-imports-phenol-saudi-arabia-singapore",
         "https://www.dgtr.gov.in/en/anti-dumping-cases/anti-dumping-investigation-concerning-imports-acetone-republic-singapore"]


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


try:
    r = S.get("https://www.dgtr.gov.in/robots.txt", timeout=40)
    body = r.text or ""
    OUT.append(f"## robots: {r.status_code} {r.headers.get('content-type')} {len(body)}자 {'HTML' if '<html' in body[:400].lower() else '글'}")
    if r.status_code == 200 and "<html" not in body[:400].lower():
        lines = [x.strip() for x in body.splitlines() if x.strip() and not x.strip().startswith("#")]
        OUT.append(f"   규칙 줄 {len(lines)} · Crawl-delay {[x for x in lines if x.lower().startswith('crawl-delay')]} · User-agent {[x for x in lines if x.lower().startswith('user-agent')][:6]}")
        OUT.append("   anti-dumping·sites/default/files 관련: " + " | ".join(x for x in lines if re.search(r"anti-dumping|/en/|sites/default|\.pdf|^Disallow: /$", x, re.I))[:500])
        OUT.append("   앞 25줄: " + " | ".join(lines[:25])[:900])
except Exception as e:  # noqa: BLE001
    OUT.append(f"## robots: 실패 {type(e).__name__}")
for n, url in enumerate(CASES):
    time.sleep(2)
    try:
        r = S.get(url, timeout=60)
        h = r.text or ""
        OUT.append(f"## 사건 {n + 1}: {r.status_code} {len(h)}자 · table {len(re.findall(r'<table', h, re.I))} · tr {len(re.findall(r'<tr', h, re.I))} · pdf 링크 {len(re.findall(r'href=\"[^\"]+\.pdf', h, re.I))}")
        m = re.search(r"File\s*No\.?[^<]{0,80}", h)
        OUT.append("   File No 둘레: " + (re.sub(r"\s+", " ", h[max(0, m.start() - 160):m.end() + 60]) if m else "못 찾음")[:420])
        i = h.find("Initiation")
        OUT.append("   'Initiation' 둘레 HTML: " + re.sub(r"\s+", " ", h[max(0, i - 700):i + 500])[:1250] if i >= 0 else "   'Initiation' 못 찾음")
        rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I)
        OUT.append(f"   표 줄 {len(rows)} — 앞 3·뒤 3:")
        for x in rows[:3] + rows[-3:]:
            cells = [txt(c)[:60] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", x, re.I)]
            href = re.findall(r'href="([^"]+)"', x)
            OUT.append("     " + " ¦ ".join(cells) + (f" ¦ href …{href[0][-70:]}" if href else ""))
        dates = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", txt(h))
        OUT.append(f"   dd/mm/yyyy 날짜 {len(dates)}개 · 처음 {dates[:2]} · 끝 {dates[-2:]} · 클래스 이름(view·field) {sorted(set(re.findall(r'class=\"((?:view|field|timeline|case)[^\" ]*)', h)))[:14]}")
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## 사건 {n + 1}: 실패 {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
