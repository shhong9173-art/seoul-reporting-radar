"""격리 탐침 11: 건축허가 감시의 주소 변환이 왜 0건인지. 공개 공장 주소 3곳으로 우체국·법정동·건축HUB를 한 번씩.
키 값은 출력하지 않는다(키 이름·HTTP 상태·응답 코드·소요 시간·공개 주소만). 응답 일부는 키 값을 지운 뒤 앞부분만."""
import os
import re
import sys
import time

sys.path.insert(0, "scripts")
import kr_building_watch as b
import requests

KEYS = b.resolve_keys(os.environ)
SECRETS = [v for _, v in KEYS] + [requests.utils.quote(v, safe="") for _, v in KEYS]
ROADS = ["충청남도 아산시 인주면 현대로 1077", "충청남도 당진시 송악읍 북부산업로 1228", "경상북도 포항시 남구 동해안로 6261"]
out = [f"keys={[n for n, _ in KEYS]}"]


def clean(t, n=220):
    t = t or ""
    for s in SECRETS:
        if s:
            t = t.replace(s, "<KEY>")
    t = re.sub(r"serviceKey=[^&\s\"'<]+", "serviceKey=<KEY>", t)
    return re.sub(r"\s+", " ", t)[:n]


def hit(name, key, url, params):
    t0 = time.time()
    try:
        r = requests.get(url, params={"serviceKey": key, **params}, headers=b.UA, timeout=40)
        return r, f"{name} HTTP {r.status_code} {time.time()-t0:.1f}s code={b.gateway_code(r.text)} ctype={r.headers.get('content-type','')[:30]} body={clean(r.text)}"
    except Exception as e:  # noqa: BLE001
        return None, f"{name} EXC {type(e).__name__} {time.time()-t0:.1f}s {clean(str(e), 120)}"


lnm = {}
for name, key in KEYS:
    for road in ROADS[:1]:
        _, line = hit(name, key, b.EPOST, {"searchSe": "road", "srchwrd": road, "countPerPage": 5, "currentPage": 1})
        out.append(f"epost[{road[-12:]}] {line}")
name, key = KEYS[0] if KEYS else ("", "")
for road in ROADS:
    for q in (road, re.sub(r"^\S+\s+\S+\s+(?:\S+[읍면]\s+)?", "", road)):
        r, line = hit(name, key, b.EPOST, {"searchSe": "road", "srchwrd": q, "countPerPage": 5, "currentPage": 1})
        found = None
        if r is not None and r.status_code == 200:
            try:
                found = b.epost_jibun(r.text)
            except Exception as e:  # noqa: BLE001
                found = f"ERR {e}"
        out.append(f"epost q='{q}' → lnm={found} :: {line[:160]}")
        if found and not str(found).startswith("ERR"):
            lnm[road] = found
            break
for road, j in lnm.items():
    sp = b.split_jibun(j)
    out.append(f"split {j} → {sp}")
    if not sp:
        continue
    for name, key in KEYS:
        r, line = hit(name, key, b.REGION, {"locatadd_nm": sp["dong"], "type": "json", "numOfRows": 20, "pageNo": 1})
        code = None
        if r is not None and r.status_code == 200:
            try:
                code = b.region_code(r.text, sp["dong"])
            except Exception as e:  # noqa: BLE001
                code = f"ERR {e}"
        out.append(f"region {sp['dong']} → {code} :: {line[:200]}")
        if code and not str(code).startswith("ERR"):
            r2, line2 = hit(name, key, b.ARCH, {"sigunguCd": code[:5], "bjdongCd": code[5:], "platGbCd": sp["platGbCd"], "bun": sp["bun"].zfill(4), "numOfRows": 5, "pageNo": 1, "_type": "json"})
            n = None
            if r2 is not None and r2.status_code == 200:
                try:
                    n = len(b.permits(r2.text))
                except Exception as e:  # noqa: BLE001
                    n = f"ERR {e}"
            out.append(f"arch {code} bun={sp['bun']} rows={n} :: {line2[:200]}")
            break
    break  # one parcel is enough for the shape

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
