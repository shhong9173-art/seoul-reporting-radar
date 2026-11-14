"""probe 242: CITT 진행 사건 목록(반덤핑·상계) 페이지 꼴과 사건 상세·일정 페이지. 공개 페이지만, 저장 안 함."""
import re
import time

import requests

OUT = []
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "en-CA,en;q=0.9"}
BASE = "https://www.citt-tcce.gc.ca"


def txt(x):
    return re.sub(r"\s+", " ", re.sub(r"&nbsp;|&#160;", " ", re.sub(r"<[^>]+>", " ", x))).strip()


def main_of(html):
    m = re.search(r"<main\b.*?</main>", html, re.S | re.I)
    return m.group(0) if m else html


r = requests.get(BASE + "/en/anti-dumping-injury-inquiries/active-dumping-and-subsidizing-cases", headers=H, timeout=60)
m = main_of(r.text)
OUT.append(f"## 진행 사건 목록: HTTP {r.status_code} · main {len(m)}자 · 표 {len(re.findall(r'<table', m, re.I))} · h2/h3 {[txt(x)[:40] for x in re.findall(r'<h[23]\b.*?</h[23]>', m, re.S | re.I)][:12]}")
case_links = []
for i, tb in enumerate(re.findall(r"<table\b.*?</table>", m, re.S | re.I)):
    rows = re.findall(r"<tr\b.*?</tr>", tb, re.S | re.I)
    cells = lambda row: [txt(x)[:70] for x in re.findall(r"<t[hd]\b.*?</t[hd]>", row, re.S | re.I)]
    OUT.append(f"표{i} 줄 {len(rows)} · 머리 {cells(rows[0]) if rows else ''}")
    for row in rows[1:]:
        c = cells(row)
        href = re.findall(r'href="([^"]+)"', row)
        korea = bool(re.search(r"Korea", row))
        if korea or len(case_links) < 3:
            OUT.append(("  ★ " if korea else "    ") + " | ".join(c) + " → " + " , ".join(h[-80:] for h in href[:2]))
        if href and (korea or len(case_links) < 2):
            case_links.append((korea, href[0]))
if not re.findall(r"<table", m, re.I):
    OUT.append("표 없음 — 본문 앞: " + txt(m)[:900])
    for a in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m, re.S | re.I):
        if re.search(r"Korea|transformer|line pipe|RR-|NQ-|PI-|LE-", a.group(0), re.I):
            OUT.append(f"    링크 {txt(a.group(2))[:80]} → {a.group(1)[-90:]}")
            case_links.append((bool(re.search('Korea', a.group(0))), a.group(1)))
case_links.sort(key=lambda x: not x[0])
for korea, href in case_links[:3]:
    time.sleep(2)
    url = href if href.startswith("http") else BASE + href
    try:
        r = requests.get(url, headers=H, timeout=60)
        m = main_of(r.text)
        OUT.append(f"### 사건 페이지 {'★' if korea else ''} {url[-80:]}: HTTP {r.status_code} · main {len(m)}자 · 「{txt((re.search(r'<h1.*?</h1>', m, re.S | re.I) or [''])[0])[:120]}」")
        OUT.append("   h2/h3: " + " ‖ ".join(txt(x)[:50] for x in re.findall(r"<h[23]\b.*?</h[23]>", m, re.S | re.I)[:14]))
        for i, tb in enumerate(re.findall(r"<table\b.*?</table>", m, re.S | re.I)[:4]):
            rows = re.findall(r"<tr\b.*?</tr>", tb, re.S | re.I)
            OUT.append(f"   표{i} 줄 {len(rows)}: " + " ‖ ".join(" | ".join(txt(x)[:60] for x in re.findall(r"<t[hd]\b.*?</t[hd]>", row, re.S | re.I)) for row in rows[:12])[:1400])
        dl = re.findall(r"<dt\b.*?</dt>\s*<dd\b.*?</dd>", m, re.S | re.I)
        if dl:
            OUT.append("   dl: " + " ‖ ".join(txt(x)[:110] for x in dl[:14]))
        OUT.append("   본문 앞: " + txt(m)[:700])
        docs = [(txt(a.group(2))[:70], a.group(1)[-80:]) for a in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m, re.S | re.I) if re.search(r"schedule|notice|calendar|decisions\.citt|\.pdf", a.group(0), re.I)]
        OUT.append("   문서 링크: " + " ‖ ".join(f"{n} → {h}" for n, h in docs[:10]))
    except Exception as e:  # noqa: BLE001
        OUT.append(f"### {url[-80:]}: 실패 {type(e).__name__} {str(e)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
