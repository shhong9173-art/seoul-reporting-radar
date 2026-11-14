"""probe 235: (1) DGTR 판정문 세율 표·OCI·Korea 줄 꼴 (2) 스캔 개시 고시 글자 인식 (3) 캐나다 CBSA 목록·사건 페이지 꼴. 공개 페이지만, 저장 안 함."""
import io
import os
import re
import subprocess
import tempfile
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})
B = "https://www.dgtr.gov.in/en/anti-dumping-cases/"
FINAL = "https://www.dgtr.gov.in/sites/default/files/2026-11/Final%20Findings%20UFS%20NCV.pdf"


def txt(h):
    import html
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def lines_of(text):
    return [y for y in (re.sub(r"\s+", " ", x).strip() for x in text.splitlines()) if y]


try:
    import pypdf
    r = S.get(FINAL, timeout=120)
    pages = [(pg.extract_text() or "") for pg in pypdf.PdfReader(io.BytesIO(r.content)).pages]
    for n in (51, 52):
        ls = lines_of(pages[n - 1])
        OUT.append(f"## 판정문 {n}쪽 {len(ls)}줄: " + " ⏎ ".join(x[:110] for x in ls[:60])[:3300])
    for n in (5, 42, 45):
        ls = lines_of(pages[n - 1])
        for i, x in enumerate(ls):
            if re.search(r"\bOCI\b", x):
                OUT.append(f"   OCI {n}쪽[{i}]: " + " ⏎ ".join(y[:120] for y in ls[max(0, i - 1):i + 3])[:520])
    for n in (2, 3, 32, 33):
        ls = lines_of(pages[n - 1])
        for i, x in enumerate(ls):
            if re.search(r"\bKorea\b", x):
                OUT.append(f"   Korea {n}쪽[{i}]: " + " ⏎ ".join(y[:120] for y in ls[max(0, i - 1):i + 2])[:420])
    ls = lines_of(pages[0])
    OUT.append("   1쪽 앞 16줄: " + " ⏎ ".join(x[:100] for x in ls[:16])[:1300])
except Exception as e:  # noqa: BLE001
    OUT.append(f"## 판정문: 실패 {type(e).__name__} {str(e)[:100]}")

# (2) 스캔 개시 고시 글자 인식
try:
    h = S.get(B + "anti-dumping-investigation-concerning-imports-isopropyl-alcohol-european-union", timeout=60).text or ""
    link = None
    for x in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I):
        cells = [txt(c) for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", x, re.I)]
        href = re.findall(r'href="([^"]+)"', x)
        if len(cells) >= 3 and re.search(r"initiation", cells[1], re.I) and href:
            link = href[0]
    raw = S.get(link, timeout=120).content
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "r.pdf")
        open(pdf, "wb").write(raw)
        r = subprocess.run(["pdftoppm", "-r", "200", "-gray", "-png", "-l", "12", pdf, os.path.join(d, "pg")], capture_output=True, timeout=200)
        t1 = time.monotonic()
        texts = []
        for f in sorted(f for f in os.listdir(d) if f.startswith("pg")):
            o = subprocess.run(["tesseract", os.path.join(d, f), "-", "--psm", "6"], capture_output=True, text=True, timeout=120)
            texts.append(o.stdout or "")
    t2 = time.monotonic()
    OUT.append(f"## 개시 고시(IPA) 글자 인식: 쪽 그림 {t1 - t0:.0f}초 · 인식 {t2 - t1:.0f}초 · {len(texts)}쪽 · 쪽별 글자 {[len(x) for x in texts]}")
    ls = lines_of("\n".join(texts))
    OUT.append(f"   줄 {len(ls)} · 앞 14줄: " + " ⏎ ".join(x[:105] for x in ls[:14])[:1500])
    heads = [(i, x) for i, x in enumerate(ls) if re.match(r"^[A-Z]\.\s+[A-Z][A-Za-z ,&/()-]{4,70}$", x)]
    OUT.append("   소제목 후보: " + " | ".join(f"{i}:{x[:46]}" for i, x in heads[:24])[:1200])
    for label, rx, take, span in (("신청인", r"application|applicant|on behalf of|petition", 3, 3), ("조사 대상 기간", r"period of investigation|\(POI\)", 3, 3),
                                  ("한국", r"\bKorea\b", 8, 2), ("수출자", r"known (?:producers|exporters)|producers?/exporters?|exporters? (?:and|or) producers?", 3, 4),
                                  ("마진", r"dumping margin|de ?minimis|injury margin", 2, 3), ("대상 품목", r"product under consideration|\bPUC\b", 2, 3)):
        hit = [i for i, x in enumerate(ls) if re.search(rx, x, re.I)]
        OUT.append(f"   {label} 줄 {len(hit)}개: " + " ⏎ ".join(f"[{i}] {' '.join(ls[i:i + span])[:330]}" for i in hit[:take])[:1500])
except Exception as e:  # noqa: BLE001
    OUT.append(f"## 개시 고시 글자 인식: 실패 {type(e).__name__} {str(e)[:120]}")

# (3) 캐나다 CBSA
try:
    base = "https://www.cbsa-asfc.gc.ca/sima-lmsi/i-e/menu-eng.html"
    try:
        rb = S.get("https://www.cbsa-asfc.gc.ca/robots.txt", timeout=40)
        rl = [x.strip() for x in rb.text.splitlines() if x.strip() and not x.startswith("#")]
        OUT.append(f"## CBSA robots {rb.status_code}: 줄 {len(rl)} · Crawl-delay {[x for x in rl if x.lower().startswith('crawl')]} · sima 관련 {[x for x in rl if 'sima' in x.lower()][:6]} · 앞 10줄 {' | '.join(rl[:10])[:500]}")
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## CBSA robots 실패 {type(e).__name__}")
    r = S.get(base, timeout=60)
    h = r.text or ""
    OUT.append(f"## CBSA 목록 {r.status_code} · {len(h)}자 · table {len(re.findall(r'<table', h, re.I))} · tr {len(re.findall(r'<tr', h, re.I))} · li {len(re.findall(r'<li', h, re.I))} · h2 {[txt(x)[:40] for x in re.findall(r'<h2[^>]*>([\s\S]*?)</h2>', h, re.I)][:10]}")
    ths = [txt(x)[:30] for x in re.findall(r"<th[^>]*>([\s\S]*?)</th>", h, re.I)]
    OUT.append(f"   표 머리 {ths[:14]}")
    rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I)
    kor = [x for x in rows if re.search(r"korea", x, re.I)]
    OUT.append(f"   한국 든 표 줄 {len(kor)}/{len(rows)}")
    links = []
    for x in kor[:6]:
        cells = [txt(c)[:90] for c in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", x, re.I)]
        hrefs = re.findall(r'href="([^"]+)"', x)
        links += hrefs
        OUT.append("     " + " ¦ ".join(cells)[:420] + f" ¦ href {hrefs[:3]}")
    from urllib.parse import urljoin
    seen = []
    for href in links:
        u = urljoin(base, href)
        if u in seen or not re.search(r"/sima-lmsi/", u) or len(seen) >= 2:
            continue
        seen.append(u)
        time.sleep(2)
        c = S.get(u, timeout=60)
        ch = c.text or ""
        main = ch[ch.find("<main"):] if "<main" in ch else ch
        OUT.append(f"## CBSA 사건 {u[-40:]} {c.status_code} · {len(ch)}자 · h1 {[txt(x)[:80] for x in re.findall(r'<h1[^>]*>([\s\S]*?)</h1>', main, re.I)][:2]}")
        OUT.append(f"   h2·h3 {[txt(x)[:44] for x in re.findall(r'<h[23][^>]*>([\s\S]*?)</h[23]>', main, re.I)][:16]}")
        OUT.append(f"   table {len(re.findall(r'<table', main, re.I))} · 표 머리 {[txt(x)[:30] for x in re.findall(r'<th[^>]*>([\s\S]*?)</th>', main, re.I)][:12]}")
        crow = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", main, re.I)
        for x in crow[:5] + crow[-3:]:
            cells = [txt(cc)[:70] for cc in re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", x, re.I)]
            OUT.append("     " + " ¦ ".join(cells)[:330] + f" ¦ href {[y[-50:] for y in re.findall(r'href=\"([^\"]+)\"', x)[:2]]}")
        lis = [(txt(x)[:100], re.findall(r'href="([^"]+)"', x)) for x in re.findall(r"<li[^>]*>([\s\S]*?)</li>", main, re.I)]
        dated = [f"{t} → {hh[0][-40:] if hh else ''}" for t, hh in lis if re.search(r"\b(?:19|20)\d{2}\b", t)]
        OUT.append(f"   날짜 든 li {len(dated)}개: " + " | ".join(dated[:10])[:1300])
        OUT.append(f"   날짜 꼴: yyyy-mm-dd {len(re.findall(r'20\d{2}-\d{2}-\d{2}', main))} · Month d, yyyy {len(re.findall(r'(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, 20\d{2}', main))} · time 태그 {len(re.findall(r'<time', main))} · dateModified {re.findall(r'dateModified[^>]{0,80}', ch)[:1]}")
except Exception as e:  # noqa: BLE001
    OUT.append(f"## CBSA: 실패 {type(e).__name__} {str(e)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines", sum(len(x) for x in OUT), "chars")
