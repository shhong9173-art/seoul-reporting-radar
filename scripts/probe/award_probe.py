"""격리 탐침 14: (1) 동별개요에서 기아 소하동 781-1 증축 허가(PK)의 동 행이 있는지 — 전체 쪽, 칸 이름, PK별 행 수
(2) 빈 응답(HTTP 200·본문 없음)이 큰 응답 때문인지 — 같은 번지를 numOfRows 100/30/10으로 반복. 키 값은 출력하지 않는다."""
import json
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, "scripts")
import kr_building_watch as b
import requests

KEYS = b.resolve_keys(os.environ)
name, key = KEYS[0] if KEYS else ("", "")
BASE = "https://apis.data.go.kr/1613000/ArchPmsHubService/"
out = [f"keys={[n for n, _ in KEYS]}"]


def clean(t):
    t = str(t or "")
    for _, v in KEYS:
        t = t.replace(v, "<KEY>")
    return re.sub(r"\s+", " ", t)


def get(op, params, size=100, page=1):
    t0 = time.time()
    r = requests.get(BASE + op, params={"serviceKey": key, "_type": "json", "numOfRows": size, "pageNo": page, **params}, headers=b.UA, timeout=60)
    time.sleep(0.5)
    dt_ = time.time() - t0
    try:
        d = r.json()
    except ValueError:
        return None, None, f"{op} n={size} p={page} HTTP {r.status_code} {dt_:.1f}s len={len(r.content)} non-json head={clean(r.text[:80])}"
    body = (d.get("response") or {}).get("body") or {}
    items = (body.get("items") or {}) if isinstance(body.get("items"), dict) else {}
    rows = items.get("item") or []
    rows = rows if isinstance(rows, list) else [rows]
    return rows, int(body.get("totalCount") or 0), f"{op} n={size} p={page} HTTP {r.status_code} {dt_:.1f}s len={len(r.content)} total={body.get('totalCount')} rows={len(rows)}"


KIA = {"sigunguCd": "41210", "bjdongCd": "10400", "platGbCd": "0", "bun": "0781"}
PK = "1000000000000001012244"
dong = []
for page in range(1, 4):
    rows, total, line = get("getApDongOulnInfo", KIA, 100, page)
    out.append(line)
    if rows is None:
        break
    dong += rows
    if len(dong) >= (total or 0):
        break
if dong:
    out.append("dong keys=" + ",".join(sorted(dong[0].keys())))
    c = Counter(str(x.get("mgmPmsrgstPk")) for x in dong)
    out.append(f"dong rows={len(dong)} pks={len(c)} target={c.get(PK, 0)} top={c.most_common(3)}")
    for x in [x for x in dong if str(x.get("mgmPmsrgstPk")) == PK][:6]:
        out.append("DONG " + clean(json.dumps({k: v for k, v in x.items() if str(v).strip() not in ("", "0", "0.0", " ")}, ensure_ascii=False))[:600])
    if not c.get(PK):
        out.append("SAMPLE " + clean(json.dumps(dong[0], ensure_ascii=False))[:600])

# (2) empty-body pattern on parcels that came back empty in probe 13
for label, p in (("LS 송정동1", {"sigunguCd": "43113", "bjdongCd": "11600", "platGbCd": "0", "bun": "0001"}),
                 ("모비스 매암동393", {"sigunguCd": "31140", "bjdongCd": "11900", "platGbCd": "0", "bun": "0393"}),
                 ("동국 송동리857", {"sigunguCd": "47111", "bjdongCd": "31026", "platGbCd": "0", "bun": "0857"})):
    for size in (100, 100, 30, 10):
        _, _, line = get("getApBasisOulnInfo", p, size)
        out.append(f"{label} {line}")

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
