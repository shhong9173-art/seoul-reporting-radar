"""Probe 80: 공정위 보도자료 목록 원본 HTML 두 줄(파서 시험 자료) + 정책브리핑 API policyNewsService2를 공유 키(KR_FUEL 대체)로 한 번.
공개 보도자료 목록 HTML만, 키 값은 남기지 않는다."""
import os
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
KEY = (os.environ.get("DATA_GO_KR_KEY") or os.environ.get("KR_FUEL_API_KEY") or "").strip()
out = [f"key length {len(KEY)}"]
for key, ctg in [("12", "01,02"), ("13", "03")]:
    r = requests.get("https://www.ftc.go.kr/www/selectBbsNttList.do", params={"bordCd": "3", "key": key, "searchCtgry": ctg}, headers=H, timeout=30)
    body = r.text.split("<tbody", 1)[-1].split("</tbody>", 1)[0]
    trs = re.split(r"(?=<tr[\s>])", body)
    out.append(f"ftc key={key} HTTP {r.status_code} total-marker {re.findall(r'총\s*<[^>]*>?\s*[\d,]+', r.text)[:2]}")
    for tr in trs[1:3]:
        out.append(re.sub(r"\n\s*", "\n", tr.strip())[:1800])
    pg = re.findall(r'pageIndex=(\d+)', r.text)
    out.append(f"  pageIndex refs {sorted(set(pg))[:12]}")
for op in ["policyNewsList"]:
    r = requests.get(f"https://apis.data.go.kr/1371000/policyNewsService2/{op}", params={"serviceKey": KEY, "startDate": "20261029", "endDate": "20261031"}, headers=H, timeout=40)
    t = r.text.replace(KEY, "<KEY>") if KEY else r.text
    out.append(f"api {op} HTTP {r.status_code} len {len(t)} head {re.sub(r'\\s+', ' ', t[:240])}")
text = "\n".join(out)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
