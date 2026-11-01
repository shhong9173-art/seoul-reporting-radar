"""Probe 78: 부처 보도자료 원천 — 정책브리핑 RSS가 7-1 중단돼, 부처 자체 게시판·공공데이터포털 정책브리핑 API 실제 주소를 한 번씩 본다(공개 보도자료).
공정위·산업통상부·기후에너지환경부 robots.txt와 보도자료 목록 첫 쪽, data.go.kr 정책브리핑 API 안내 쪽의 요청 주소만."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []


def get(url, **kw):
    try:
        r = requests.get(url, headers=H, timeout=30, **kw)
        return r
    except Exception as e:  # noqa: BLE001
        out.append(f"  ERR {url} {type(e).__name__} {str(e)[:80]}")
        return None


for host in ["https://www.ftc.go.kr", "https://www.motir.go.kr", "https://www.me.go.kr"]:
    r = get(host + "/robots.txt")
    if r is not None:
        out.append(f"robots {host} HTTP {r.status_code}: " + re.sub(r"\s+", " ", r.text[:300]))

r = get("https://www.ftc.go.kr/www/index.do")
if r is not None:
    out.append(f"ftc home HTTP {r.status_code} len {len(r.text)}")
    links = set(re.findall(r'href="([^"]*(?:rss|Rss|RSS|bordCd|selectReport|selectBbs)[^"]*)"', r.text))
    for h in sorted(links)[:25]:
        out.append(f"  ftc link {h[:140]}")
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>\s*([^<]{0,20}보도[^<]{0,20})<', r.text):
        out.append(f"  ftc 보도 {m.group(2).strip()} -> {m.group(1)[:140]}")

r = get("https://www.motir.go.kr/kor/article/ATCL3f49a5a8c")
if r is not None:
    out.append(f"motir list HTTP {r.status_code} len {len(r.text)}")
    rows = re.findall(r'href="(/kor/article/ATCL3f49a5a8c/(\d+)/view[^"]*)"', r.text)
    out.append(f"  motir rows {len(rows)} first ids {[x[1] for x in rows[:5]]}")
    for h in sorted(set(re.findall(r'href="([^"]*(?:rss|RSS|Rss)[^"]*)"', r.text)))[:10]:
        out.append(f"  motir rss href {h[:140]}")
    dates = re.findall(r"20\d\d[-.]\d\d[-.]\d\d", r.text)
    out.append(f"  motir dates {dates[:6]}")

for did in ["15095335"]:
    r = get(f"https://www.data.go.kr/data/{did}/openapi.do")
    if r is not None:
        paths = sorted(set(re.findall(r"apis\.data\.go\.kr/1371000/[A-Za-z0-9_/]+", r.text)))
        out.append(f"datago {did} HTTP {r.status_code} paths {paths[:10]}")
        ops = sorted(set(re.findall(r'"(/[A-Za-z]+List)"', r.text)))
        out.append(f"  ops {ops[:10]}")

r = get("https://www.data.go.kr/tcs/dss/selectDataSetList.do", params={"keyword": "정책브리핑 보도자료", "dType": "API"})
if r is not None:
    hits = re.findall(r'/data/(\d{8})/openapi\.do[^>]*>\s*(?:<[^>]+>\s*)*([^<]{3,80})', r.text)
    out.append(f"datago search HTTP {r.status_code} hits {len(hits)}")
    for did, title in hits[:12]:
        out.append(f"  {did} {title.strip()[:70]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
