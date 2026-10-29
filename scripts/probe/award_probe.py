"""격리 탐침 21: 바레인 개찰 결과 검색 폼 — 입력 이름, 검색 버튼, 제출(postback) 뒤 결과 표 형식. 공개 페이지, 저장 없음."""
import re

import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
URL = "https://www.tenderboard.gov.bh/Tenders/OpenedBids/"
out = []


def text_of(html):
    t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html)
    t = re.sub(r"<[^>]+>", " ¦ ", t)
    return re.sub(r"(\s*¦\s*)+", " ¦ ", re.sub(r"\s+", " ", t))


s = requests.Session()
r = s.get(URL, headers=UA, timeout=40)
b = r.text
inputs = re.findall(r"<input[^>]*>", b)
names = []
for i in inputs:
    n = re.search(r'name="([^"]+)"', i)
    t = re.search(r'type="([^"]+)"', i)
    v = re.search(r'value="([^"]*)"', i)
    names.append((n.group(1) if n else None, t.group(1) if t else None, (v.group(1)[:30] if v else "")))
out.append(f"inputs={[(n, t, v if not (n or '').startswith('__') else len(v)) for n, t, v in names][:40]}")
selects = re.findall(r'<select[^>]*name="([^"]+)"', b)
out.append(f"selects={selects}")
buttons = re.findall(r'<(?:input|button)[^>]*(?:type="submit"|onclick="[^"]*")[^>]*>', b)[:10]
out.append(f"buttons={[x[:200] for x in buttons]}")
posts = re.findall(r"__doPostBack\('([^']*)'", b)[:10]
out.append(f"postbacks={posts}")
# find the block right after 'Find Opened Bids' in raw html to see ids
k = b.find("Find Opened Bids")
out.append("raw=" + re.sub(r"\s+", " ", b[k:k + 2500]).replace("<option", "\n<option")[:2500])
data = {n: v for n, t, v in [(re.search(r'name="([^"]+)"', i).group(1), None, (re.search(r'value="([^"]*)"', i) or [None, ""])[1]) for i in inputs if re.search(r'name="([^"]+)"', i)]}
btn = next((re.search(r'name="([^"]+)"', x).group(1) for x in buttons if re.search(r'name="([^"]+)"', x) and re.search(r'[Ss]earch|btn', x)), None)
out.append(f"btn={btn}")
if btn:
    r2 = s.post(URL, data=data, headers={**UA, "Referer": URL}, timeout=60)
    b2 = r2.text
    t2 = text_of(b2)
    j = t2.find("Find Opened Bids")
    out.append(f"post HTTP {r2.status_code} len={len(b2)} rows={b2.count('<tr')} BHD={b2.count('BHD')}")
    out.append("post text=" + t2[j + 2000:j + 6000])

packs, cur = [], ""
for x in out:
    x = x.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(x) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" ‖ " if cur else "") + x
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
