"""Probe: NTIS 공고 목록 제목과 상세 제목이 다른 사례(공개 자료). 저장하지 않음."""
import html
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pre_scoop_radar as p  # noqa: E402

out = []
diag = {"httpAttempts": 0, "retries": 0, "errors": []}
for term in ["배터리", "자동차"]:
    url = "https://www.ntis.go.kr/ThSearchResultAnnouncementList.do?" + urllib.parse.urlencode({"searchSentence": "", "searchWord": term, "sort": "SS01/DESC,RANK/DESC"})
    markup = p._ntis_fetch(url, diag, f"search:{term}")
    if markup is None:
        out.append(f"{term}: list failed {diag['errors'][-1:]}")
        continue
    links = []
    for m in re.finditer(r'<a\b[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', markup, re.I | re.S):
        href, title = html.unescape(m[1]), p.clean(m[2])
        if "/rndgate/eg/un/ra/view.do" in href:
            links.append((p._ntis_detail_url(href), title, m[0][:300]))
    out.append(f"{term}: {len(links)} links")
    for durl, ltitle, raw in links[:6]:
        dm = p._ntis_fetch(durl, diag, "detail")
        if dm is None:
            out.append(f"  detail failed {durl}")
            continue
        dtitle, fields, _ = p.parse_ntis_detail(dm)
        same = p._ntis_title_key(dtitle) == p._ntis_title_key(ltitle)
        out.append(f"  {'SAME' if same else 'DIFF'} {durl}\n   list: {ltitle!r}\n   detail: {dtitle!r}\n   date {fields.get('공고일')}")
        if not same:
            out.append(f"   raw list anchor: {raw!r}")
            h = re.search(r'<h1\b[^>]*ditail_tit[^>]*>(.*?)</h1>', dm, re.S | re.I)
            out.append(f"   raw h1: {h.group(0)[:400] if h else None!r}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:400])
