"""probe 178: (a) 본문 못 읽은 언론사 3곳 구조(텍스트 없이 태그·id·class·글자 수만), (b) 공식 제재 원천 — 개인정보위 처분·금감원 제재내용공개 목록 형식.
저장 안 함. 기사 본문·사람 이름은 찍지 않는다(목록은 기관·회사 이름이 든 공개 게시판 제목만 몇 줄)."""
import json, re, sys, time
from html.parser import HTMLParser
from urllib.parse import urljoin
import requests

sys.path.insert(0, "scripts")
OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}


def log(*a):
    OUT.append(" ".join(str(x) for x in a))


def get(url, **kw):
    try:
        r = requests.get(url, headers=UA, timeout=25, **kw)
        enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else (r.apparent_encoding or "utf-8")
        r.encoding = enc
        return r
    except Exception as e:
        log("  FAIL", url[:90], type(e).__name__)
        return None


class Struct(HTMLParser):
    """요소마다(id/class 있는 것) 안쪽 텍스트 길이를 센다 — 텍스트는 저장하지 않는다."""
    SKIP = {"script", "style", "noscript"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.done, self.ld = [], [], 0
        self.in_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("br", "img", "meta", "link", "hr", "input", "source", "wbr", "embed"):
            return
        self.in_ld = tag == "script" and (a.get("type") or "").lower() == "application/ld+json"
        self.stack.append([tag, a.get("id") or "", (a.get("class") or "")[:60], a.get("itemprop") or "", 0, 0])

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for el in self.stack[i:][::-1]:
                    self.done.append(el)
                del self.stack[i:]
                break
        self.in_ld = False

    def handle_data(self, d):
        if self.in_ld:
            self.ld += 1 if "articleBody" in d else 0
            return
        if self.stack and self.stack[-1][0] in self.SKIP:
            return
        n = len(d.strip())
        for el in self.stack:
            el[4] += n
        if self.stack and self.stack[-1][0] == "p":
            for el in self.stack:
                el[5] += 1


def structure(name, url):
    r = get(url)
    if r is None:
        return
    log(f"\n## {name} HTTP {r.status_code} {len(r.text)}B final={r.url[:80]} ctype={r.headers.get('Content-Type', '')[:40]}")
    s = Struct()
    s.feed(r.text)
    els = [e for e in s.done if (e[1] or e[2] or e[3]) and e[4] >= 300]
    els.sort(key=lambda e: e[4])
    # 글자가 많으면서 가장 안쪽(작은) 컨테이너들
    for e in els[:14]:
        log(f"  {e[0]} id={e[1]!r} class={e[2]!r} itemprop={e[3]!r} chars={e[4]} p={e[5]}")
    log(f"  ld+json articleBody 등장 {s.ld}")
    import executive_article_evidence as ae
    got = ae.extract_article(r.text)
    log(f"  현재 파서: {got.get('status')} len={len(got.get('body', ''))}")


def table_rows(html, n=4):
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for tr in rows:
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if cells:
            out.append(" | ".join(c[:40] for c in cells))
    return out[:n], len(rows)


def links(html, base, pat):
    out = []
    for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()
        if re.search(pat, t):
            out.append((t[:30], urljoin(base, href)[:140]))
    return list(dict.fromkeys(out))[:25]


def sanctions():
    log("\n# 개인정보위")
    for url in ("https://www.pipc.go.kr/np/", "https://www.pipc.go.kr/np/default/page.do?mCode=D040000000"):
        r = get(url)
        if r is None:
            continue
        log(f"  {url} HTTP {r.status_code} {len(r.text)}B")
        for t, u in links(r.text, url, r"의결|처분|공표|제재|심의"):
            log(f"   link {t} -> {u}")
    log("\n# 금감원 제재내용공개")
    for url in ("https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476",
                "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476&pageIndex=2"):
        r = get(url)
        if r is None:
            continue
        rows, n = table_rows(r.text, 6)
        log(f"  {url} HTTP {r.status_code} {len(r.text)}B rows={n}")
        for x in rows:
            log("   row", x[:200])
        for t, u in links(r.text, url, r".")[:0]:
            pass
        m = re.findall(r'href="([^"]*openInfo/view[^"]*)"', r.text)
        log("   view links", len(m), (m[:2] if m else ""))
        m2 = re.findall(r'(?:fileDown|download)[^"\']{0,120}', r.text)
        log("   file links", len(m2), m2[:2])
        tot = re.search(r"(총\s*[\d,]+\s*건|전체\s*[\d,]+)", r.text)
        log("   total", tot.group(0) if tot else None)


t = time.time()
structure("fnnews", "http://www.fnnews.com/news/202512172051198957")
structure("nocutnews", "https://www.nocutnews.co.kr/news/5779381")
structure("peoplewatch", "https://www.peoplewatch.co.kr/article/view/ppw202610200012")
try:
    sanctions()
except Exception as e:
    log("sanctions error", type(e).__name__, str(e)[:200])
log(f"\n{time.time() - t:.0f}s")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
