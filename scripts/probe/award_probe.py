"""Probe 10: 오만 입찰위원회(Esnad, etendering.tenderboard.gov.om)가 개찰 결과(응찰 회사·응찰가)를 로그인 없이 공개하는지 — 공개 자료, 저장하지 않음."""
import re
import time
import requests

out = []
S = requests.Session()
S.headers.update({"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"})
BASE = "https://etendering.tenderboard.gov.om"


def show(label, url, n=1500, **kw):
    try:
        r = S.get(url, timeout=40, **kw)
        t = r.text
        out.append(f"\n## {label} {url} -> HTTP {r.status_code} len {len(t)} type {r.headers.get('content-type')} final {r.url}")
        return t
    except Exception as e:  # noqa: BLE001
        out.append(f"\n## {label} {url} -> {type(e).__name__} {str(e)[:120]}")
        return ""
    finally:
        time.sleep(1.0)


rb = show("robots", BASE + "/robots.txt")
out.append(rb[:600])
home = show("home", BASE + "/product/publicDash")
out.append("scripts: " + " | ".join(sorted(set(re.findall(r"""<script[^>]+src=['"]([^'"]+)""", home)))[:40]))
out.append("hrefs: " + " | ".join(sorted(set(h for h in re.findall(r"""href=['"]([^'"#]+)""", home) if not h.startswith("http")))[:80]))
out.append("onclick/js: " + " | ".join(sorted(set(re.findall(r"""(?:onclick|action)=['"]([^'"]{3,160})""", home)))[:60]))
kw = sorted(set(re.findall(r"[\w/.?=&-]*(?:[Oo]pen(?:ed|ing)|[Aa]ward|[Bb]idder|[Qq]uot|viewFlag)[\w/.?=&-]*", home)))
out.append("keywords: " + " | ".join(kw[:120]))
for path in ["/product/publicDash?viewFlag=OpenedTenders", "/product/publicDash?viewFlag=AwardedTenders", "/product/publicDash?viewFlag=NewTenders",
             "/product/opening/OpeningReportPublic", "/product/nicgep/app?page=FrontEndTendersByOrganisation&service=page"]:
    t = show("try", BASE + path)
    body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    out.append(txt[:700])
    out.append("links: " + " | ".join(sorted(set(re.findall(r"""href=['"]([^'"#]{4,160})""", t)))[:40]))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
