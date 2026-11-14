"""probe 234: 인도 DGTR 판정문(Final Findings)·개시 고시 PDF의 글 꼴 — 세율 표·한국 줄·조사 대상 기간·신청인이 어디에 어떻게 나오는지. 공개 PDF만, 저장 안 함."""
import io
import re
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})
B = "https://www.dgtr.gov.in/en/anti-dumping-cases/"
FINAL = "https://www.dgtr.gov.in/sites/default/files/2026-11/Final%20Findings%20UFS%20NCV.pdf"
INIT_CASES = [("ipa", B + "anti-dumping-investigation-concerning-imports-isopropyl-alcohol-european-union"),
              ("tdi", B + "anti-dumping-investigation-concerning-imports-toluene-diisocyanate-tdi")]


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


def mask(x):
    return re.sub(r"[\w.+-]+@[\w.-]+", "<mail>", x)


def pages_of(url):
    import pypdf
    r = S.get(url, timeout=120)
    doc = pypdf.PdfReader(io.BytesIO(r.content))
    return r.status_code, len(r.content), [(pg.extract_text() or "") for pg in doc.pages]


def lines_of(text):
    return [y for y in (re.sub(r"\s+", " ", x).strip() for x in text.splitlines()) if y]


try:
    st, size, pages = pages_of(FINAL)
    OUT.append(f"## 판정문(흄드실리카 SSR Final Findings): {st} · {size // 1024}KB · {len(pages)}쪽 · 글 {sum(len(p) for p in pages)}자")
    kor = [(i + 1, len(re.findall(r"\bKorea\b", p))) for i, p in enumerate(pages) if re.search(r"\bKorea\b", p)]
    OUT.append(f"   'Korea' 든 쪽 {len(kor)}쪽: " + " ".join(f"{n}:{c}" for n, c in kor)[:500])
    for word in (r"duty table", r"recommendation", r"conclusion", r"dumping margin", r"injury margin", r"OCI", r"non-?injurious|NIP", r"US\$|USD|MT\b"):
        hit = [i + 1 for i, p in enumerate(pages) if re.search(word, p, re.I)]
        OUT.append(f"   '{word}' 든 쪽 {len(hit)}: {hit[:30]}")
    tail = lines_of("\n".join(pages[-6:]))
    OUT.append(f"   끝 6쪽 줄 {len(tail)} · 줄 길이 중간 {sorted(len(x) for x in tail)[len(tail) // 2]}")
    idx = [i for i, x in enumerate(tail) if re.search(r"duty table|^S\.?\s*N|recommend", x, re.I)]
    OUT.append(f"   끝 6쪽에서 표·권고 낱말 줄 번호 {idx[:20]}")
    start = next((i for i, x in enumerate(tail) if re.search(r"duty table", x, re.I)), max(0, len(tail) - 70))
    OUT.append("   세율 표 둘레(줄바꿈 ⏎): " + " ⏎ ".join(x[:95] for x in tail[max(0, start - 6):start + 64])[:4200])
    allp = lines_of("\n".join(pages))
    rec = [i for i, x in enumerate(allp) if re.match(r"^[A-Z]\.?\s*RECOMMENDATION|^RECOMMENDATION", x)]
    OUT.append(f"   전체 줄 {len(allp)} · 'RECOMMENDATION' 머리 줄 {rec[:6]}")
    if rec:
        OUT.append("   권고 첫 14줄: " + " ⏎ ".join(x[:110] for x in allp[rec[-1]:rec[-1] + 14])[:1500])
    kl = [i for i, x in enumerate(allp) if re.search(r"\bKorea\b", x) and re.search(r"margin|duty|%|negative|de ?minimis|range", x, re.I)]
    OUT.append(f"   Korea+마진·세율 낱말 줄 {len(kl)}개: " + " ⏎ ".join(f"[{i}] {allp[i][:120]}" for i in kl[:10])[:1500])
except Exception as e:  # noqa: BLE001
    OUT.append(f"## 판정문: 실패 {type(e).__name__} {str(e)[:100]}")

for name, url in INIT_CASES:
    time.sleep(2)
    try:
        h = S.get(url, timeout=60).text or ""
        rows = []
        for x in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I):
            cells = [txt(c) for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", x, re.I)]
            href = re.findall(r'href="([^"]+)"', x)
            if len(cells) >= 3 and re.search(r"\d{2}/\d{2}/\d{4}", cells[-1]) and re.search(r"initiation", cells[1], re.I) and href:
                rows.append((cells[-1][-10:], cells[1][:50], href[0]))
        d, title, link = max(rows, key=lambda x: x[0][6:] + x[0][3:5] + x[0][:2])
        time.sleep(2)
        st, size, pages = pages_of(link)
        ls = lines_of("\n".join(pages))
        OUT.append(f"## 개시 고시 {name} 「{title}」[{d}]: {st} · {size // 1024}KB · {len(pages)}쪽 · 글 {sum(len(p) for p in pages)}자 · 줄 {len(ls)} · 줄 길이 중간 {sorted(len(x) for x in ls)[len(ls) // 2] if ls else 0}")
        OUT.append("   앞 12줄: " + " ⏎ ".join(x[:100] for x in ls[:12])[:1100])
        heads = [(i, x) for i, x in enumerate(ls) if re.match(r"^[A-Z]\.\s+[A-Z][A-Za-z ,&/()-]{4,70}$", x) or re.match(r"^[A-Z][A-Z ,&/()-]{8,70}$", x)]
        OUT.append("   소제목 후보: " + " | ".join(f"{i}:{x[:48]}" for i, x in heads[:26])[:1300])
        for label, rx, take in (("신청인", r"application|applicant|on behalf of|filed by|petition", 3), ("조사 대상 기간", r"period of investigation|\bPOI\b", 3),
                                ("한국", r"\bKorea\b", 6), ("수출자·생산자", r"known (?:producers|exporters)|producers?/exporters?|exporters? (?:and|or) producers?", 4),
                                ("마진 주장", r"dumping margin|de ?minimis|injury margin", 3), ("기한", r"within \d+ days|thirty|30 days|time limit", 2)):
            hit = [i for i, x in enumerate(ls) if re.search(rx, x, re.I)]
            OUT.append(f"   {label} 줄 {len(hit)}개: " + " ⏎ ".join(f"[{i}] {mask(' '.join(ls[i:i + 2]))[:190]}" for i in hit[:take])[:1300])
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## 개시 고시 {name}: 실패 {type(e).__name__} {str(e)[:100]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
