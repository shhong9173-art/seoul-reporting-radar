"""probe 180: 개인정보위 '결과의 공표' 상세 형식(회사·위반·처분), 금감원 제재내용공개 상세 PDF 형식(기관·임원 제재 줄) + 목록 쪽수 매개변수.
저장 안 함. 개인 이름처럼 보이는 2~3글자+직함/괄호는 ○○로 가린다."""
import io, re, time
from urllib.parse import urljoin
import requests

OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
MASK = re.compile(r"(?<![가-힣])[가-힣]{2,3}(?=\s*(?:\(|씨|님|前|전\s|대표|사장|회장|부회장|이사|감사|본부장|상무|전무|부장|팀장))")


def log(*a):
    OUT.append(MASK.sub("○○", " ".join(str(x) for x in a)))


def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=30, **kw)
        if "text" in r.headers.get("Content-Type", "") or "html" in r.headers.get("Content-Type", ""):
            r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else (r.apparent_encoding or "utf-8")
        return r
    except Exception as e:
        log("  FAIL", url[:100], type(e).__name__)
        return None


def text(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


t0 = time.time()
log("# 개인정보위 결과의 공표 상세")
base = "https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS258&mCode=C010040000&nttId="
for ntt in ("12608", "12454", "11778"):
    r = get(base + ntt)
    if r is None:
        continue
    h = r.text
    i = h.find("결과의 공표")
    body = text(h)
    j = body.find("처분")
    log(f"\n nttId={ntt} HTTP {r.status_code} {len(h)}B")
    # 본문 영역 후보
    for cls in re.findall(r'<div[^>]+class="([^"]*(?:view|cont|board)[^"]*)"', h)[:8]:
        log("  div class", cls[:60])
    k = body.find("제66조에 따른 결과의 공표", 0)
    k2 = body.find("제66조에 따른 결과의 공표", k + 10)
    log("  body excerpt:", body[k2 if k2 > 0 else k:][:1500])
    tables = re.findall(r"<table[^>]*>(.*?)</table>", h, re.S)
    log("  tables", len(tables))
    for tb in tables[:3]:
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)
        for tr in trs[:8]:
            cells = [text(c)[:50] for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            log("   tr", " | ".join(cells)[:300])
    files = re.findall(r'(fileDown\.do\?[^"\']+|/np/cmm/fms/FileDown\.do\?[^"\']+|atchFileId=[^"\'&]+[^"\']*)', h)
    log("  files", len(files), files[:3])
    names = re.findall(r'title="([^"]+\.(?:pdf|hwp|hwpx))"|>([^<>]+\.(?:pdf|hwp|hwpx))<', h)
    log("  file names", names[:4])

log("\n# 금감원 목록 쪽수")
fss = "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476&sdate=2020-01-01&edate=2026-11-05"
for p in (2, 100, 232):
    r = get(fss + f"&pageIndex={p}")
    if r is None:
        continue
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S)
    first = [text(c)[:30] for c in re.findall(r"<td[^>]*>(.*?)</td>", trs[1], re.S)] if len(trs) > 1 else None
    log(f"  page {p}: rows {len(trs) - 1} first {first}")

log("\n# 금감원 상세 PDF")
r = get("https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476")
views = re.findall(r'href="([^"]*openInfo/view\.do[^"]+)"', r.text) if r is not None else []
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None
for v in views[:3]:
    u = urljoin("https://www.fss.or.kr/", v.replace("&amp;", "&"))
    d = get(u)
    if d is None:
        continue
    h = d.text
    i = h.find(".pdf")
    seg = h[max(0, i - 1500):i + 200]
    hrefs = re.findall(r'href="([^"]+)"', seg)
    log(f"\n view {u[-60:]}")
    log("  pdf hrefs", [x[:160] for x in hrefs[-4:]])
    labels = re.findall(r">([^<>]{3,80}\.pdf)<", h)
    log("  pdf labels", labels[:3])
    dl = [x for x in hrefs if "down" in x.lower() or "file" in x.lower()]
    if dl and PdfReader:
        pu = urljoin(u, dl[-1].replace("&amp;", "&"))
        pr = get(pu)
        if pr is not None:
            log("  pdf HTTP", pr.status_code, pr.headers.get("Content-Type", "")[:40], len(pr.content))
            try:
                pdf = PdfReader(io.BytesIO(pr.content))
                txt = "\n".join((pg.extract_text() or "") for pg in pdf.pages[:4])
                log("  pages", len(pdf.pages), "chars", len(txt))
                t = re.sub(r"[ \t]+", " ", txt)
                for kw in ("제재대상", "제재조치", "기관", "임원", "직원", "대표이사", "문책", "주의적경고", "직무정지", "해임", "과태료", "과징금"):
                    k = t.find(kw)
                    log(f"   {kw}@{k}:", t[max(0, k - 40):k + 160].replace("\n", " / ") if k >= 0 else None)
            except Exception as e:
                log("  pdf parse fail", type(e).__name__)
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
