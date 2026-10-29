"""격리 탐침 31e: 국민연금 사업장 V2 — 정렬·보관 개월 수, 출입처별 이름 낱말로 잡히는 자사 사업장 이름(빗금 없는 것)과 공사 현장 수(키 값 미출력)."""
import json
import os
import time
from collections import Counter
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/getBassInfoSearchV2"
out = []
t_start = time.time()


def search(name, page=1, rows=100):
    t0 = time.time()
    try:
        r = requests.get(BASE, params={"serviceKey": key, "pageNo": page, "numOfRows": rows, "dataType": "json", "wkplNm": name}, timeout=60)
        b = (json.loads(r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")).get("response") or {}).get("body") or {}
    except Exception as e:  # noqa: BLE001
        return None, [], f"{type(e).__name__}"
    time.sleep(0.4)
    items = (b.get("items") or {}).get("item") if isinstance(b.get("items"), dict) else b.get("items")
    items = items if isinstance(items, list) else ([items] if items else [])
    return b.get("totalCount"), items, f"{time.time() - t0:.1f}s"


months = Counter()
seqs = []
for p in (1, 2, 3):
    tot, it, el = search("현대자동차", p)
    months.update(x["dataCrtYm"] for x in it)
    seqs += [x["seq"] for x in it]
    out.append(f"현대자동차 p{p} total={tot} n={len(it)} {el} 월={sorted(Counter(x['dataCrtYm'] for x in it).items())}")
out.append(f"seq 내림차순={seqs == sorted(seqs, reverse=True)} 월 순서={[x['dataCrtYm'] for x in []]}")
tot, it, el = search("현대제철(주)", 1)
out.append("현대제철(주) " + " | ".join(f"{x['wkplNm']}·{x['dataCrtYm']}" for x in it))
TERMS = ["현대모비스", "현대위아", "에이치엘만도", "한국지엠", "케이지모빌리티", "르노코리아", "한국타이어", "넥센타이어", "금호타이어",
         "포스코", "현대제철", "케이지스틸", "세아제강", "동국제강", "동국씨엠", "고려아연", "영풍", "에이치디현대일렉트릭", "엘에스일렉트릭",
         "대한전선", "엘에스전선", "엘에스엠앤엠", "두산에너빌리티", "지에스칼텍스", "한화솔루션", "오씨아이", "태광산업", "동성케미컬", "디엘케미칼", "기아"]
for t in TERMS:
    if time.time() - t_start > 900:
        out.append("시간 한도 — 나머지 생략")
        break
    tot, it, el = search(t, 1)
    if not it:
        out.append(f"{t}: total={tot} {el}")
        continue
    latest = max(x["dataCrtYm"] for x in it)
    cur = [x for x in it if x["dataCrtYm"] == latest]
    own = sorted({x["wkplNm"] for x in cur if "/" not in x["wkplNm"] and x["wkplJnngStcd"] == "1"})
    sites = sum(1 for x in cur if "/" in x["wkplNm"])
    out.append(f"{t}: total={tot} {el} 최신 {latest} {len(cur)}줄(공사·용역 빗금 {sites}) 자사형 {own[:10]}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
