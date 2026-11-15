"""probe 256: USTR 2027 NTE 의견서 중 철강·자동차·화학 제출자 6곳의 한국 대목 전문(공개 정부 자료). 저장 안 함."""
import io
import os
import re
import time

import requests

OUT = []
UA = {"User-Agent": "Mozilla/5.0 (seoul-reporting-radar probe)", "Accept": "application/json"}
KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "").strip() or "DEMO_KEY"
API = "https://api.regulations.gov/v4"
KOREA = re.compile(r"(?<![Nn]orth )\bKorea(?:n|ns|'s|’s)?\b|\bKORUS\b|\bROK\b")
WANT = [("USTR-2026-0498-0102", "Ford", 4200), ("USTR-2026-0498-0147", "Rebar Trade Action Coalition", 7500), ("USTR-2026-0498-0086", "Steel Manufacturers Association", 6500),
        ("USTR-2026-0498-0146", "AISI", 3800), ("USTR-2026-0498-0141", "Olin", 4200), ("USTR-2026-0498-0168", "Line Pipe", 2600)]


def pdf_text(data):
    import pypdf
    pdf = pypdf.PdfReader(io.BytesIO(data))
    return re.sub(r"[ \t]+", " ", "\n".join((p.extract_text() or "") for p in pdf.pages)), len(pdf.pages)


for cid, name, budget in WANT:
    try:
        r = requests.get(f"{API}/comments/{cid}", params={"include": "attachments", "api_key": KEY}, headers=UA, timeout=40)
        time.sleep(1.2)
        body = r.json()
        a = (body.get("data") or {}).get("attributes") or {}
        urls = [f["fileUrl"] for inc in body.get("included") or [] for f in (inc.get("attributes") or {}).get("fileFormats") or [] if str(f.get("format")).lower() == "pdf" and f.get("fileUrl")]
        text, pages = "", 0
        for u in urls[:2]:
            d = requests.get(u, headers={"User-Agent": UA["User-Agent"]}, timeout=60)
            t, n = pdf_text(d.content)
            text += "\n" + t
            pages += n
        text = re.sub(r"\s+", " ", text)
        segs = []
        for m in KOREA.finditer(text):
            s, e = max(0, m.start() - 500), min(len(text), m.end() + 700)
            if segs and s <= segs[-1][1]:
                segs[-1][1] = e
            else:
                segs.append([s, e])
        OUT.append(f"■■ {name} | {cid} | {a.get('title')} | 게시 {str(a.get('postedDate'))[:10]} | {pages}쪽 {len(text)}자 | 한국 대목 {len(segs)}토막 | 첨부 {urls[:1]}")
        left = budget
        for s, e in segs:
            if left <= 200:
                OUT.append(f"   …(남은 토막 생략)")
                break
            piece = text[s:e][:left]
            OUT.append(f"   [{s}~{e}] {piece}")
            left -= len(piece)
    except Exception as ex:  # noqa: BLE001
        OUT.append(f"■■ {name} | {cid} | 실패 {type(ex).__name__}: {str(ex)[:120]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
