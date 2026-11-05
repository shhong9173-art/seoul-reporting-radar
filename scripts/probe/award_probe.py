"""probe 179: 공식 제재 원천 형식 — 개인정보위 '결과의 공표'(BS258)·'의결사항'(agenda), 금감원 제재내용공개 상세·과거 범위.
저장 안 함. 공개 게시판의 기관·회사 이름과 제목 몇 줄만(개인 이름 찍지 않음 — 금감원 상세는 '대표'·'임원' 낱말 주변 구조만)."""
import re, time
from urllib.parse import urljoin
import requests

OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=25, **kw)
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else (r.apparent_encoding or "utf-8")
        return r
    except Exception as e:
        log("  FAIL", url[:100], type(e).__name__)
        return None


def text(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()


def rows(html, n=6):
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for tr in trs:
        cells = [text(c)[:60] for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        hrefs = re.findall(r'href="([^"]+)"', tr) + re.findall(r"onclick=\"([^\"]{0,120})\"", tr)
        if cells:
            out.append(" | ".join(cells) + ("  ⟶ " + hrefs[0][:150] if hrefs else ""))
    return out[:n], len(trs)


def lis(html, n=8):
    # 게시판이 표가 아니라 목록(ul/li)일 때
    items = re.findall(r"<li[^>]*>(.*?)</li>", html, re.S)
    out = []
    for li in items:
        t = text(li)
        if 15 < len(t) < 300 and re.search(r"20\d{2}[.\-]\d{2}", t):
            h = re.findall(r'href="([^"]+)"', li) + re.findall(r"onclick=\"([^\"]{0,120})\"", li)
            out.append(t[:160] + ("  ⟶ " + h[0][:150] if h else ""))
    return out[:n]


t0 = time.time()
log("# 개인정보위 결과의 공표 BS258")
base = "https://www.pipc.go.kr/np/cop/bbs/selectBoardList.do?bbsId=BS258&mCode=C010040000"
for url in (base, base + "&pageIndex=2"):
    r = get(url)
    if r is None:
        continue
    rs, n = rows(r.text)
    log(f"  {url[-40:]} HTTP {r.status_code} {len(r.text)}B tr={n}")
    for x in rs:
        log("   row", x[:260])
    for x in lis(r.text):
        log("   li", x[:260])
    tot = re.search(r"(총\s*[\d,]+\s*건|전체\s*[\d,]+\s*건|Total\s*[\d,]+)", r.text)
    log("   total", tot.group(0) if tot else None)
    m = re.findall(r'(selectBoardArticle\.do[^"\']+|fn_\w+\(\s*[\'"]?\d+[^)]*\))', r.text)
    log("   detail refs", len(m), m[:3])

log("\n# 개인정보위 의결사항 agenda")
for url in ("https://www.pipc.go.kr/np/default/agenda.do?mCode=E030010000",
            "https://www.pipc.go.kr/np/default/agenda.do?mCode=E030010000&pageIndex=2"):
    r = get(url)
    if r is None:
        continue
    rs, n = rows(r.text)
    log(f"  {url[-45:]} HTTP {r.status_code} {len(r.text)}B tr={n}")
    for x in rs:
        log("   row", x[:260])
    for x in lis(r.text):
        log("   li", x[:260])
    tot = re.search(r"(총\s*[\d,]+\s*건|전체\s*[\d,]+\s*건)", r.text)
    log("   total", tot.group(0) if tot else None)
    m = re.findall(r'(agendaView\.do[^"\']+|agenda\w*\.do\?[^"\']+|fn_\w+\([^)]{0,80}\))', r.text)
    log("   detail refs", len(m), list(dict.fromkeys(m))[:4])
    m2 = re.findall(r'(fileDown\w*\.do[^"\']*|/np/[^"\']*[Ff]ile[^"\']*)', r.text)
    log("   file refs", len(m2), list(dict.fromkeys(m2))[:3])

log("\n# 금감원 제재내용공개 — 과거 범위·상세")
fss = "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476"
for sd in ("2014-01-01", "2020-01-01"):
    r = get(fss + f"&sdate={sd}&edate=2026-11-05&pageIndex=1")
    if r is None:
        continue
    rs, n = rows(r.text, 2)
    log(f"  sdate={sd} HTTP {r.status_code} first:", rs[1][:120] if len(rs) > 1 else rs)
    last = re.findall(r"pageIndex=(\d+)", r.text)
    log("   max pageIndex seen", max(map(int, last)) if last else None)
    cnt = re.search(r"(총\s*[\d,]+\s*건|[\d,]+\s*건)", r.text)
    log("   count", cnt.group(0) if cnt else None)
r = get(fss)
views = re.findall(r'href="([^"]*openInfo/view\.do[^"]+)"', r.text) if r is not None else []
for v in views[:3]:
    u = urljoin(fss, v.replace("&amp;", "&"))
    d = get(u)
    if d is None:
        continue
    body = text(d.text)
    log(f"\n  view HTTP {d.status_code} {len(d.text)}B")
    i = body.find("제재대상기관")
    log("   around 제재대상기관:", body[i:i + 300] if i >= 0 else None)
    for kw in ("기관", "임원", "직원", "대표", "과태료", "과징금", "문책", "주의적경고", "견책"):
        log(f"   kw {kw}: {body.count(kw)}")
    files = re.findall(r'(fileDown[^"\']{0,160}|\.pdf[^"\']{0,40}|\.hwp[^"\']{0,40})', d.text)
    log("   files", len(files), files[:3])
    trs, n = rows(d.text, 12)
    log("   tr", n)
    for x in trs:
        log("    ", re.sub(r"[가-힣]{2,3}\s*(?=\()", "○○", x)[:200])
log(f"\n{time.time() - t0:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
