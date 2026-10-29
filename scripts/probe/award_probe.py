"""격리 탐침 31f: 국민연금 사업장 V2 — 대리점·정비점이 많은 출입처의 최신 달 자사 사업장 이름 찾기(키 값 미출력)."""
import json
import os
import re
import time
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/getBassInfoSearchV2"
out = []
DEALER = re.compile(r"/|-\(|\(일용\)|\(상용\)|점|대리점|서비스|써비스|정비|오토큐|판매|총판|부품|영업소|어린이집|새마을금고|신용협동조합|의원|식당|센터|센타|지정|카센|모터스|상사|공업사|아파트|더샵|주택|재개발|문고|건설")


def search(name, page):
    try:
        r = requests.get(BASE, params={"serviceKey": key, "pageNo": page, "numOfRows": 100, "dataType": "json", "wkplNm": name}, timeout=60)
        b = (json.loads(r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")).get("response") or {}).get("body") or {}
    except Exception as e:  # noqa: BLE001
        return None, [], type(e).__name__
    time.sleep(0.4)
    items = (b.get("items") or {}).get("item") if isinstance(b.get("items"), dict) else b.get("items")
    return b.get("totalCount"), (items if isinstance(items, list) else ([items] if items else [])), None


for term, maxp in (("현대자동차", 5), ("기아", 6), ("포스코", 3), ("한국지엠", 2), ("케이지모빌리티", 2), ("르노코리아", 2), ("한국타이어", 2), ("영풍", 2),
                   ("GS칼텍스", 1), ("지에스칼텍스", 1), ("OCI", 1), ("오씨아이홀딩스", 1), ("엘에스", 2), ("세아홀딩스", 1), ("에이치엘", 1), ("HL만도", 1)):
    names, latest, total, err = set(), None, None, None
    for p in range(1, maxp + 1):
        total, it, err = search(term, p)
        if not it:
            break
        latest = latest or it[0]["dataCrtYm"]
        cur = [x for x in it if x["dataCrtYm"] == latest]
        names |= {f"{x['wkplNm']}[{x['ldongAddrMgplDgCd']}{x['ldongAddrMgplSgguCd']}{'' if x['wkplJnngStcd'] == '1' else ',탈퇴'}]" for x in cur if not DEALER.search(x["wkplNm"])}
        if len(cur) < len(it):
            break
    out.append(f"{term}: total={total} 최신 {latest} 쪽 {p} err={err} 자사 후보 {sorted(names)[:30]}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
