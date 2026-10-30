"""Probe 13: 오만 송전망 OETC(Nama) 전자입찰 창구 — 공개 화면에 개찰(응찰 회사·응찰가)·낙찰이 있는지. 공개 자료, 저장하지 않음."""
import html
import re
import time
from urllib.parse import urljoin, urlparse
import requests

out = []
S = requests.Session()
S.headers.update({"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"})


def get(url):
    try:
        r = S.get(url, timeout=40, allow_redirects=True)
        out.append(f"\n## {url} -> HTTP {r.status_code} len {len(r.text)} final {r.url}")
        return r
    except Exception as e:  # noqa: BLE001
        out.append(f"\n## {url} -> {type(e).__name__} {str(e)[:150]}")
        return None
    finally:
        time.sleep(1.5)


def links(r, rx):
    found = []
    for href, label in re.findall(r"""<a[^>]+href=['"]([^'"]+)['"][^>]*>(.*?)</a>""", r.text, re.S | re.I):
        lab = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", label))).strip()
        if re.search(rx, href + " " + lab, re.I):
            found.append((urljoin(r.url, html.unescape(href)), lab[:60]))
    return list(dict.fromkeys(found))


def text(r, n=1500):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", r.text, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))[:n]


TENDER = r"tender|procure|e-?tender|ariba|supplier|vendor|bid|award|مناقص"
seen = set()
for start in ["https://www.omangrid.com/en/pages/home.aspx", "https://www.nama.om/", "https://nama.om/en"]:
    r = get(start)
    if not r:
        continue
    for host in {urlparse(r.url).scheme + "://" + urlparse(r.url).netloc}:
        rb = get(host + "/robots.txt")
        if rb is not None:
            out.append("robots: " + rb.text[:300].replace("\n", " / "))
    ls = links(r, TENDER)
    out.append(f"tender links: {ls[:20]}")
    for u, lab in ls[:6]:
        if u in seen or u.startswith(("mailto:", "javascript:")):
            continue
        seen.add(u)
        r2 = get(u)
        if not r2:
            continue
        out.append(f"[{lab}] text: {text(r2, 1200)}")
        out.append(f"  sub links: {links(r2, r'open|award|result|bid|tender|notice')[:15]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
