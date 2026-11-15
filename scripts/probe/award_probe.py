"""probe 245: 미국 관보 사전 공개본(public inspection) API 꼴과 PDF 글자. 공개 자료만, 저장 안 함."""
import io, json, re, subprocess, sys, tempfile

import requests

OUT = []
H = {"User-Agent": "seoul-reporting-radar probe (contact: github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/json"}
B = "https://www.federalregister.gov/api/v1/public-inspection-documents"
try:
    r = requests.get(B + "/current.json", headers=H, timeout=60)
    OUT.append(f"current.json HTTP {r.status_code} {len(r.content)}B")
    d = r.json()
    res = d.get("results") or []
    OUT.append(f"최상위 키 {sorted(d.keys())} · count {d.get('count')} · results {len(res)}")
    if res:
        OUT.append("첫 문서 키: " + ", ".join(sorted(res[0].keys())))
    def ag(x):
        return [a.get("slug") or a.get("name") for a in x.get("agencies") or [] if isinstance(a, dict)]
    trade = [x for x in res if any(s in ("international-trade-administration", "international-trade-commission") for s in ag(x))]
    OUT.append(f"ITA·ITC 문서 {len(trade)}건 · 그중 제목에 Korea {sum(1 for x in trade if re.search('korea', x.get('title') or '', re.I))}건")
    for x in trade[:14]:
        OUT.append(" · ".join(str(v) for v in [x.get("document_number"), x.get("filing_type"), "filed " + str(x.get("filed_at")), "pub " + str(x.get("publication_date")),
            (x.get("title") or "")[:110], "raw_text " + str(bool(x.get("raw_text_url"))), "pdf " + str(bool(x.get("pdf_url"))), "dockets " + str(x.get("docket_numbers"))]))
    # 세율 표가 있을 만한 문서 하나의 PDF 글자
    pick = next((x for x in trade if re.search(r"Results of (?:Antidumping|Countervailing)|Final Determination|Preliminary Determination", x.get("title") or "") and x.get("pdf_url")), None)
    if pick:
        p = requests.get(pick["pdf_url"], headers={"User-Agent": H["User-Agent"]}, timeout=90)
        OUT.append(f"PDF {pick['document_number']} HTTP {p.status_code} {len(p.content)//1024}KB magic {p.content[:5]!r} · {pick['title'][:90]}")
        text = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(p.content); f.flush()
                text = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, timeout=60).stdout.decode("utf-8", "ignore")
            OUT.append(f"pdftotext 글자 {len(text)}")
        except Exception as e:
            OUT.append(f"pdftotext 실패 {type(e).__name__}")
            try:
                import pypdf
                text = "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(io.BytesIO(p.content)).pages)
                OUT.append(f"pypdf 글자 {len(text)}")
            except Exception as e2:
                OUT.append(f"pypdf 실패 {type(e2).__name__}")
        lines = [l.rstrip() for l in text.split("\n")]
        hits = [i for i, l in enumerate(lines) if re.search(r"percent\)|Weighted-Average|Subsidy Rate|Dumping Margin", l)]
        for i in hits[:3]:
            OUT.append("표 근처: " + " ⏎ ".join(l.strip()[:120] for l in lines[max(0, i - 1):i + 9] if l.strip()))
        OUT.append("첫 줄들: " + " ⏎ ".join(l.strip()[:100] for l in lines[:14] if l.strip()))
    # 검색 주소(기관으로 거르기)
    s = requests.get(B + ".json", params=[("conditions[agencies][]", "international-trade-administration"), ("conditions[agencies][]", "international-trade-commission"), ("per_page", "100")], headers=H, timeout=60)
    try:
        sj = s.json()
        OUT.append(f"검색 주소 HTTP {s.status_code} · count {sj.get('count')} · results {len(sj.get('results') or [])} · 키 {sorted(sj.keys())}")
    except Exception as e:
        OUT.append(f"검색 주소 HTTP {s.status_code} · JSON 아님 {type(e).__name__} · {s.text[:120]!r}")
except Exception as e:
    OUT.append(f"실패 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
