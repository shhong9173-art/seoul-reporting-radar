"""격리 탐침 47c: 굴뚝 측정 — 출입처별 사업장 이름·배출구 수, 측정 시각 분포(멈춘 배출구), 0값 배출구, 쪽 넘김(키 값 미출력)."""
import datetime as dt
import json
import os
import time
from collections import Counter, defaultdict
from urllib.parse import quote

import requests

key = (os.environ.get("KR_FUEL_API_KEY") or "").strip()
BASE = "https://apis.data.go.kr/B552584/cleansys/rltmMesureResult"
KST = dt.timezone(dt.timedelta(hours=9))
now = dt.datetime.now(KST)
out = []


def get(params):
    r = requests.get(BASE, params={"serviceKey": key, "type": "json", **params}, timeout=60)
    d = json.loads(r.text)
    b = (d.get("response") or {}).get("body") or {}
    items = b.get("items") or []
    items = items.get("item") if isinstance(items, dict) else items
    return (d.get("response") or {}).get("header", {}).get("totalCount") or b.get("totalCount"), items if isinstance(items, list) else []


tot, a = get({"factManageNm": "현대제철", "numOfRows": 20, "pageNo": 1})
tot2, a2 = get({"factManageNm": "현대제철", "numOfRows": 20, "pageNo": 2})
out.append(f"쪽 넘김: total={tot} p1={len(a)} p2={len(a2)} 겹침={len({(x['fact_manage_nm'], x['stack_code']) for x in a} & {(x['fact_manage_nm'], x['stack_code']) for x in a2})}")
for term in ("현대제철", "포스코", "동국제강", "동국씨엠", "세아", "고려아연", "영풍", "엘에스엠앤엠", "LS", "오씨아이", "OCI", "한화솔루션", "지에스칼텍스", "GS칼텍스",
             "태광산업", "금호타이어", "한국타이어", "넥센타이어", "현대자동차", "기아", "케이지스틸", "KG스틸", "두산에너빌리티", "현대모비스", "디엘케미칼", "동성케미컬"):
    try:
        t0 = time.time()
        _, items = get({"factManageNm": term, "numOfRows": 500, "pageNo": 1})
    except Exception as e:  # noqa: BLE001
        out.append(f"{term}: {type(e).__name__}")
        continue
    by = defaultdict(list)
    for x in items:
        by[x.get("fact_manage_nm")].append(x)
    parts = []
    for name, xs in sorted(by.items()):
        ages = Counter()
        zero = 0
        for x in xs:
            try:
                age = (now - dt.datetime.strptime(x["mesure_dt"], "%Y-%m-%d %H:%M").replace(tzinfo=KST)).total_seconds() / 3600
            except (TypeError, ValueError):
                age = 9999
            ages["<3h" if age < 3 else "<24h" if age < 24 else "<7d" if age < 168 else ">=7d"] += 1
            vals = [x.get(f"{p}_mesure_value") for p in ("tsp", "sox", "nox", "hcl", "hf", "nh3", "co")]
            nums = [float(v) for v in vals if v not in (None, "")]
            if nums and max(nums) < 0.5:
                zero += 1
        oldest = min(x["mesure_dt"] for x in xs if x.get("mesure_dt"))
        parts.append(f"{name}[{xs[0].get('area_nm')}] 배출구 {len(xs)} 시각 {dict(ages)} 0값 {zero} 가장오래 {oldest}")
    out.append(f"{term} ({time.time() - t0:.0f}s): " + " | ".join(parts[:10]))
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
