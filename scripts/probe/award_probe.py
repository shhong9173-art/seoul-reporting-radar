"""probe 241: (a) 호주 industry.gov.au PDF가 GitHub에서 받아지는지 (b) CBSA Statement of reasons 페이지의 수출자별 마진 표 꼴 (c) CITT 누리집 접근·일정 페이지. 공개 페이지만, 저장 안 함."""
import re
import subprocess
import sys
import tempfile
import time

import requests

sys.path.insert(0, "scripts/probe")
OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "en-AU,en;q=0.9"}


def pdftext(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        r = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace")


# (a) 호주
OUT.append("## (a) 호주 industry.gov.au — GitHub에서")
BASE = "https://www.industry.gov.au"
for path in ("/sites/default/files/adc/public-record/2026-09/698-13-submission-australian-industry-bluescope-steel-limited-submission-on-pms-in-the-korean-hrc-market-and-response-to-kg-dongbu-submission.pdf",
             "/sites/default/files/adc/public-record/2026-09/706-20-file-note-meeting-with-posco.pdf",
             "/australian-trade-remedies-commission/current-cases-and-electronic-public-record-epr/706"):
    try:
        r = requests.get(BASE + path, headers=UA, timeout=45)
        head = r.content[:5]
        OUT.append(f"- {path[-60:]}: HTTP {r.status_code} · {r.headers.get('content-type', '')[:40]} · {len(r.content)}B · 앞 {head!r} · server {r.headers.get('server', '')[:30]}")
        if head == b"%PDF-":
            t = pdftext(r.content)
            sents = [s.strip() for s in re.split(r"(?<=[.;])\s+", re.sub(r"\s+", " ", t)) if re.search(r"Korea|POSCO|KG Dongbu|Dongkuk|Hyundai", s)]
            OUT.append(f"   글자 {len(t)} · 쪽 {t.count(chr(12)) + 1} · 한국·출입처 문장 {len(sents)}")
            for s in sents[:5]:
                OUT.append("   · " + s[:260])
    except Exception as e:  # noqa: BLE001
        OUT.append(f"- {path[-60:]}: 실패 {type(e).__name__} {str(e)[:120]}")
    time.sleep(2)

# (b) CBSA Statement of reasons
OUT.append("## (b) CBSA Statement of reasons")
try:
    import cbsa_cases as c
    S = requests.Session()
    S.headers.update(c.HEADERS)
    sor = []
    for list_id, kind, url in c.LISTS:
        time.sleep(1.5)
        cases, total = c.parse_list(S.get(url, timeout=60).text, list_id, url)
        for x in cases:
            for d in x["docs"]:
                if re.search(r"statement of reasons", d["title"], re.I):
                    sor.append((d.get("date") or "", kind, x["title"][:70], d["title"][:80], d["url"]))
    sor.sort(reverse=True)
    OUT.append(f"한국 관련 사건의 Statement of reasons 문서 {len(sor)}건 · 주소 꼴: " + " ‖ ".join(sorted({re.sub(r'[^/]+$', '', u.replace('https://www.cbsa-asfc.gc.ca', ''))[:40] for *_, u in sor})[:8]))
    for d, kind, case, title, url in sor[:10]:
        OUT.append(f"- {d} · {kind} · {case} · {title} · {url[-55:]}")
    for d, kind, case, title, url in [x for x in sor if x[4].lower().endswith((".html", ".htm"))][:3]:
        time.sleep(2)
        r = S.get(url, timeout=60)
        html = c.main_of(r.text) if hasattr(c, "main_of") else r.text
        tables = re.findall(r"<table\b.*?</table>", html, re.S | re.I)
        OUT.append(f"### {d} {case} — HTTP {r.status_code} · {len(r.text)}자 · 표 {len(tables)}개 · {url}")
        for i, tb in enumerate(tables):
            cap = re.sub(r"<[^>]+>", " ", (re.search(r"<caption\b.*?</caption>", tb, re.S | re.I) or [""])[0] if re.search(r"<caption", tb, re.I) else "")
            rows = re.findall(r"<tr\b.*?</tr>", tb, re.S | re.I)
            cells = lambda row: [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()[:45] for x in re.findall(r"<t[hd]\b.*?</t[hd]>", row, re.S | re.I)]
            hit = [cells(x) for x in rows if re.search(r"Korea|POSCO|Hyundai|Dongkuk|SeAH|Hyosung|Iljin|LS |Nexteel|Husteel|Dongbu|%", re.sub(r"<[^>]+>", " ", x))]
            if not hit or not re.search(r"margin|subsid|dumping|normal value|export price|%", tb, re.I):
                continue
            OUT.append(f"  표{i} 줄 {len(rows)} · 제목 {re.sub(r'\s+', ' ', cap).strip()[:110]} · 머리 {cells(rows[0]) if rows else ''}")
            for h in hit[:6]:
                OUT.append("    " + " | ".join(h))
except Exception as e:  # noqa: BLE001
    OUT.append(f"실패 {type(e).__name__} {str(e)[:200]}")

# (c) CITT
OUT.append("## (c) CITT")
H = {"User-Agent": UA["User-Agent"], "Accept-Language": "en-CA,en;q=0.9"}
for url in ("https://www.citt-tcce.gc.ca/en", "https://www.citt-tcce.gc.ca/en/dumping-and-subsidizing", "https://www.citt-tcce.gc.ca/en/calendar",
            "https://www.citt-tcce.gc.ca/en/dumping-and-subsidizing/expiry-reviews", "https://decisions.citt-tcce.gc.ca/citt-tcce/a/en/nav_date.do",
            "https://www.citt-tcce.gc.ca/en/schedule-proceedings"):
    try:
        r = requests.get(url, headers=H, timeout=45, allow_redirects=True)
        text = r.text
        title = re.sub(r"\s+", " ", (re.search(r"<title>(.*?)</title>", text, re.S | re.I) or ["", ""])[1]).strip()[:70]
        links = sorted({(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()[:50], m.group(1)[:90]) for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', text, re.S | re.I)
                        if re.search(r"calendar|schedul|expiry|inquir|dumping|transformer|line pipe|korea", m.group(0), re.I)})
        OUT.append(f"- {url[-60:]}: HTTP {r.status_code} → {r.url[-60:]} · {len(text)}자 · 「{title}」 · Korea {len(re.findall('Korea', text))} · transformer {len(re.findall('(?i)transformer', text))} · 링크 {len(links)}")
        for name, href in links[:14]:
            OUT.append(f"    {name} → {href}")
    except Exception as e:  # noqa: BLE001
        OUT.append(f"- {url[-60:]}: 실패 {type(e).__name__} {str(e)[:120]}")
    time.sleep(2)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
