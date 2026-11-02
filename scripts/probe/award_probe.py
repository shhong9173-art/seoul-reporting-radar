"""probe 101: 바레인 입찰위원회 월간 낙찰 보고서(스캔 이미지 PDF) OCR 가능성 — 쪽수·쪽당 OCR 시간·출입처 영문 이름 일치 줄."""
import io, os, re, subprocess, sys, tempfile, time
import requests
sys.path.insert(0, "scripts")
OUT = []
def p(*a):
    OUT.append(" ".join(str(x) for x in a))
UA = {"User-Agent": "Mozilla/5.0 (research; seoul-reporting-radar)"}
SITE = "https://www.tenderboard.gov.bh"
try:
    from overseas_award_watch import beat_of, bh_reports
except Exception as e:
    p("import fail", type(e).__name__, e); beat_of = None
r = requests.get(SITE + "/Tenders/AwardedTenders/", headers=UA, timeout=60)
reps = bh_reports(r.text)
p("list HTTP", r.status_code, "reports", len(reps), [x["subject"][:50] for x in reps[:4]])
p("tesseract", subprocess.run(["tesseract", "--version"], capture_output=True, text=True).stdout.splitlines()[:1])
for rep in reps[:2]:
    t = time.time()
    pr = requests.get(SITE + rep["href"].replace(" ", "%20"), headers=UA, timeout=180)
    p("\n==", rep["subject"][:60], "HTTP", pr.status_code, "MB", round(len(pr.content) / 1e6, 1), f"{time.time()-t:.0f}s")
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(pr.content))
    p("pages", len(rd.pages), "text chars", sum(len(pg.extract_text() or "") for pg in rd.pages))
    with tempfile.TemporaryDirectory() as d:
        pdf = os.path.join(d, "r.pdf"); open(pdf, "wb").write(pr.content)
        t = time.time()
        subprocess.run(["pdftoppm", "-r", "200", "-gray", "-png", pdf, os.path.join(d, "pg")], check=True)
        imgs = sorted(f for f in os.listdir(d) if f.startswith("pg"))
        p("raster", len(imgs), f"{time.time()-t:.0f}s")
        t = time.time(); text = []
        for i, f in enumerate(imgs):
            if time.time() - t > 600:
                p("OCR time cap at page", i); break
            out = subprocess.run(["tesseract", os.path.join(d, f), "-", "--psm", "6"], capture_output=True, text=True).stdout
            text.append(out)
        p("ocr pages", len(text), f"{time.time()-t:.0f}s", "chars", sum(map(len, text)))
        full = "\n".join(text)
        lines = [ln.strip() for ln in full.splitlines() if ln.strip()]
        rx = re.compile(r"korea|hyundai|hyosung|iljin|ls\s*cable|ls\s*electric|taihan|posco|kepco|doosan|samsung|daewoo|\bgs\b|hanwha|cable works", re.I)
        hits = [i for i, ln in enumerate(lines) if rx.search(ln)]
        p("hint lines", len(hits))
        for i in hits[:10]:
            p("  ctx|", " // ".join(lines[max(0, i - 3): i + 4])[:700])
        # 300dpi on the page holding the first korea hit (better OCR?)
        kpage = next((n for n, tx in enumerate(text) if re.search(r"korea", tx, re.I)), None)
        if kpage is not None:
            subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", "-f", str(kpage + 1), "-l", str(kpage + 1), pdf, os.path.join(d, "hi")], check=True)
            hi = sorted(f for f in os.listdir(d) if f.startswith("hi"))[0]
            for psm in ("6", "4", "11"):
                out = subprocess.run(["tesseract", os.path.join(d, hi), "-", "--psm", psm], capture_output=True, text=True).stdout
                ls = [x.strip() for x in out.splitlines() if x.strip()]
                ks = [j for j, x in enumerate(ls) if re.search(r"korea|cable", x, re.I)]
                p(f"  300dpi psm{psm} korea/cable lines", len(ks))
                for j in ks[:4]:
                    p("   ", " // ".join(ls[max(0, j - 4): j + 5])[:800])
        if beat_of:
            hits = [(beat_of(ln), ln.strip()) for ln in full.splitlines() if beat_of(ln)]
            p("beat lines", len(hits))
            for b, ln in hits[:15]:
                p("  B|", b, "|", ln[:200])
        # sample of how award lines look (first 6 non-empty lines of page 2)
        if len(text) > 1:
            p("sample p2:", " / ".join([x for x in text[1].splitlines() if x.strip()][:8])[:600])
text = "\n".join(OUT)
open("/tmp/probe_out.txt", "w").write(text)
print(text)
