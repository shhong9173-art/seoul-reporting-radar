"""격리 탐침 31d: 국민연금 사업장 V2 — 한 쪽 최대 줄 수·정렬, 지난달(dataCrtYm) 조회와 seq 유지 여부, 출입처 본사 사업장 가입자 수(키 값 미출력)."""
import json
import os
import time
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
BASE = "https://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2/"
out = []


def call(op, params, rows=100, page=1):
    t0 = time.time()
    r = requests.get(BASE + op, params={"serviceKey": key, "pageNo": page, "numOfRows": rows, "dataType": "json", **params}, timeout=60)
    body = r.text.replace(key, "<KEY>").replace(quote(key, safe=""), "<KEY>")
    time.sleep(0.6)
    try:
        b = (json.loads(body).get("response") or {}).get("body") or {}
    except ValueError:
        out.append(f"{op} {params} HTTP {r.status_code} 비JSON {body[:200]!r}")
        return None, []
    items = (b.get("items") or {}).get("item") if isinstance(b.get("items"), dict) else b.get("items")
    items = items if isinstance(items, list) else ([items] if items else [])
    out.append(f"{op} {params} rows={rows} p{page} total={b.get('totalCount')} n={len(items)} {time.time() - t0:.1f}s")
    return b, items


_, a = call("getBassInfoSearchV2", {"wkplNm": "현대자동차"}, rows=1000)
seqs = [x["seq"] for x in a]
out.append(f"정렬: seq desc={seqs == sorted(seqs, reverse=True)} asc={seqs == sorted(seqs)} 첫={seqs[:3]} 끝={seqs[-3:]} 월={sorted(set(x['dataCrtYm'] for x in a))} 가입={sum(1 for x in a if x['wkplJnngStcd'] == '1')}/탈퇴={sum(1 for x in a if x['wkplJnngStcd'] == '2')}")
plain = [x for x in a if "/" not in x["wkplNm"]]
out.append("빗금 없는 이름 " + " | ".join(f"{x['wkplNm']}·{x['bzowrRgstNo']}·{x['wkplJnngStcd']}·{x['ldongAddrMgplDgCd']}{x['ldongAddrMgplSgguCd']}" for x in plain[:25]))
_, prev = call("getBassInfoSearchV2", {"wkplNm": "현대자동차", "dataCrtYm": "202608"}, rows=1000)
pm = {x["wkplNm"]: x for x in prev}
same = [(x["wkplNm"], x["seq"], pm[x["wkplNm"]]["seq"]) for x in a if x["wkplNm"] in pm][:5]
out.append(f"202608 조회: 월={sorted(set(x['dataCrtYm'] for x in prev))} 같은 이름 seq 비교={same}")
for nm in ("현대자동차(주)", "현대자동차주식회사", "기아(주)", "현대제철(주)", "주식회사 포스코", "고려아연(주)"):
    _, it = call("getBassInfoSearchV2", {"wkplNm": nm}, rows=50)
    top = [x for x in it if x["wkplJnngStcd"] == "1"][:6]
    det = []
    for x in top[:4]:
        _, d = call("getDetailInfoSearchV2", {"seq": x["seq"]}, rows=1)
        _, p = call("getPdAcctoSttusInfoSearchV2", {"seq": x["seq"]}, rows=1)
        det.append(f"{x['wkplNm'][:30]}·{x['bzowrRgstNo']}·{x['ldongAddrMgplDgCd']}{x['ldongAddrMgplSgguCd']}·가입자 {d[0].get('jnngpCnt') if d else '?'}·적용 {d[0].get('adptDt') if d else '?'}·취득 {p[0].get('nwAcqzrCnt') if p else '?'}·상실 {p[0].get('lssJnngpCnt') if p else '?'}")
    out.append(f"{nm}: " + " | ".join(det))
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
