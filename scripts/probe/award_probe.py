"""격리 탐침 13: 증축 허가의 '증축분 면적'을 주는 칸이 있는지. 건축HUB 건축인허가 기본개요의 모든 칸과
동별개요(getApDongOulnInfo)·층별개요(getApFlrOulnInfo)를 공개 공장 번지 4곳의 해당 허가로 본다. 키 값은 출력하지 않는다."""
import json
import os
import re
import sys
import time

sys.path.insert(0, "scripts")
import kr_building_watch as b
import requests

KEYS = b.resolve_keys(os.environ)
name, key = KEYS[0] if KEYS else ("", "")
REGION = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
BASE = "https://apis.data.go.kr/1613000/ArchPmsHubService/"
# (법정동, 본번, 허가일) — 10-29 첫 실행에서 본 증축 허가
TARGETS = [("충청북도 청주시 흥덕구 송정동", "0001", "20260826"), ("경기도 광명시 소하동", "0781", "20260812"),
           ("울산광역시 남구 매암동", "0393", "20260811"), ("경상북도 포항시 남구 대송면 송동리", "0857", "20260903")]
out = [f"keys={[n for n, _ in KEYS]}"]


def clean(t):
    t = str(t or "")
    for _, v in KEYS:
        t = t.replace(v, "<KEY>")
    return re.sub(r"\s+", " ", t)


def get(op, params):
    t0 = time.time()
    r = requests.get(BASE + op, params={"serviceKey": key, "_type": "json", "numOfRows": 100, "pageNo": 1, **params}, headers=b.UA, timeout=40)
    time.sleep(0.4)
    try:
        d = r.json()
    except ValueError:
        return None, f"{op} HTTP {r.status_code} {time.time()-t0:.1f}s non-json head={clean(r.text[:120])}"
    body = (d.get("response") or {}).get("body") or {}
    items = (body.get("items") or {}) if isinstance(body.get("items"), dict) else {}
    rows = items.get("item") or []
    rows = rows if isinstance(rows, list) else [rows]
    return rows, f"{op} HTTP {r.status_code} {time.time()-t0:.1f}s total={body.get('totalCount')} code={b.gateway_code(r.text)}"


for dong, bun, day in TARGETS:
    r = requests.get(REGION, params={"serviceKey": key, "locatadd_nm": dong, "type": "json", "numOfRows": 20, "pageNo": 1}, headers=b.UA, timeout=40)
    code = b.region_code(r.text, dong) if r.status_code == 200 else None
    out.append(f"== {dong} {bun} code={code}")
    if not code:
        continue
    p = {"sigunguCd": code[:5], "bjdongCd": code[5:], "platGbCd": "0", "bun": bun}
    rows, line = get("getApBasisOulnInfo", p)
    out.append(line)
    hit = [x for x in rows or [] if str(x.get("archPmsDay")) == day and x.get("archGbCdNm") == "증축"]
    if not hit:
        out.append("no target permit")
        continue
    t = hit[0]
    pk = str(t.get("mgmPmsrgstPk"))
    out.append("BASIS " + clean(json.dumps({k: v for k, v in t.items() if str(v).strip() not in ("", "0", "0.0", " ")}, ensure_ascii=False))[:1400])
    for op in ("getApDongOulnInfo", "getApFlrOulnInfo"):
        drows, dline = get(op, p)
        mine = [x for x in drows or [] if str(x.get("mgmPmsrgstPk")) == pk]
        out.append(f"{dline} rowsForPk={len(mine)}")
        for x in mine[:4]:
            out.append(op[5:9] + " " + clean(json.dumps({k: v for k, v in x.items() if str(v).strip() not in ("", "0", "0.0", " ")}, ensure_ascii=False))[:700])

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
