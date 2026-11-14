"""probe 232: 인도 DGTR 사건 페이지 — 일정표의 '개시' 줄이 여럿인 사건(재심·우회조사), 이해관계자 명단 PDF의 글 꼴. 공개 페이지만, 저장 안 함. 이메일은 가린다."""
import io
import re
import time

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
OUT = []
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en,ko;q=0.8"})
B = "https://www.dgtr.gov.in/en/anti-dumping-cases/"
CASES = [("phenol", B + "anti-dumping-investigation-concerning-imports-phenol-saudi-arabia-singapore", True),
         ("acetone", B + "anti-dumping-investigation-concerning-imports-acetone-republic-singapore", True),
         ("chisel", B + "anti-dumping-investigation-concerning-imports-alloy-steel-chisel-tool-and", True),
         ("tdi", B + "anti-dumping-investigation-concerning-imports-toluene-diisocyanate-tdi", False),
         ("nacn", B + "anti-dumping-investigation-concerning-imports-sodium-cyanide-nacn-originating-or", False),
         ("silica", B + "anti-dumping-investigation-concerning-imports-untreated-fumed-silica-china-pr", False)]
NAMES = re.compile(r"\bLG\b|Kumho|Lotte|Hanwha|\bSK\b|Hyundai|POSCO|\bOCI\b|Samsung|Kolon|Hyosung", re.I)


def txt(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()


def mask(x):
    return re.sub(r"[\w.+-]+@[\w.-]+", "<mail>", x)


for name, url, pdf in CASES:
    time.sleep(2)
    try:
        r = S.get(url, timeout=60)
        h = r.text or ""
        rows = []
        for x in re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", h, re.I):
            cells = [txt(c) for c in re.findall(r"<td[^>]*>([\s\S]*?)</td>", x, re.I)]
            href = re.findall(r'href="([^"]+)"', x)
            if len(cells) >= 3 and re.search(r"\d{2}/\d{2}/\d{4}", cells[-1]):
                rows.append((cells[1][:70], cells[-1][-10:], href[0] if href else ""))
        OUT.append(f"## {name}: {r.status_code} · 일정표 {len(rows)}줄")
        OUT.append("   " + " | ".join(f"{t} [{d}]" for t, d, _ in rows)[:1500])
        parties = [x for x in rows if re.search(r"interested\s+part", x[0], re.I) and x[2]]
        if not pdf or not parties:
            continue
        t, d, link = max(parties, key=lambda x: x[1][6:] + x[1][3:5] + x[1][:2])
        time.sleep(2)
        import pypdf
        p = S.get(link, timeout=90)
        doc = pypdf.PdfReader(io.BytesIO(p.content))
        pages = [(pg.extract_text() or "") for pg in doc.pages[:12]]
        lines = [re.sub(r"\s+", " ", x).strip() for x in "\n".join(pages).splitlines()]
        lines = [x for x in lines if x]
        OUT.append(f"   명단 PDF [{d}] {p.status_code} {len(p.content) // 1024}KB · {len(doc.pages)}쪽 · 글 {sum(len(x) for x in pages)}자 · 줄 {len(lines)} · 줄 길이 중간값 {sorted(len(x) for x in lines)[len(lines) // 2] if lines else 0}")
        OUT.append("   앞 14줄: " + " ⏎ ".join(mask(x)[:90] for x in lines[:14]))
        hits = [i for i, x in enumerate(lines) if re.search(r"\bKorea\b|\bROK\b", x, re.I) or NAMES.search(x)]
        OUT.append(f"   Korea·회사 이름 줄 {len(hits)}개(줄 번호 {hits[:40]})")
        shown = set()
        for i in hits[:14]:
            if i in shown:
                continue
            seg = range(max(0, i - 1), min(len(lines), i + 3))
            shown.update(seg)
            OUT.append(f"     [{i}] " + " ⏎ ".join(mask(lines[j])[:110] for j in seg))
        OUT.append("   번호로 시작하는 줄 비율: " + f"{sum(1 for x in lines if re.match(r'^\d{1,3}[.)]?\s', x))}/{len(lines)}"
                   + " · 표 머리 후보: " + " ⏎ ".join(mask(x)[:80] for x in lines if re.search(r"S\.?\s*No|Name of|Category|Interested Part", x, re.I))[:400])
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## {name}: 실패 {type(e).__name__} {str(e)[:80]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
