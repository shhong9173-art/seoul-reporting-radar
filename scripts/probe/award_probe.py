"""격리 탐침 12: 우체국 openapi.epost.go.kr:80 이 러너(해외 IP)에서 연결 시간 초과. 대안 확인.
(a) 공장등록 API 응답에 지번 주소 칸이 있는지(태그 이름만 + 공개 주소 1건)
(b) 접속 가능 여부만: epost https, 도로명주소(juso.go.kr) 검색 API(키 없이 → 오류 코드면 접속 가능), 브이월드
(c) 법정동코드·건축HUB를 키로 1회씩(응답 코드·건수만)
키 값은 출력하지 않는다."""
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, "scripts")
import kr_building_watch as b
import kr_official_watch as o
import requests

KEYS = b.resolve_keys(os.environ)
SECRETS = [v for _, v in KEYS] + [requests.utils.quote(v, safe="") for _, v in KEYS]
out = [f"keys={[n for n, _ in KEYS]}"]


def clean(t, n=200):
    t = t or ""
    for s in SECRETS:
        if s:
            t = t.replace(s, "<KEY>")
    t = re.sub(r"(serviceKey|confmKey|key)=[^&\s\"'<]+", r"\1=<KEY>", t)
    return re.sub(r"\s+", " ", t)[:n]


def reach(label, url, params=None, timeout=20):
    t0 = time.time()
    try:
        r = requests.get(url, params=params, headers=b.UA, timeout=timeout)
        out.append(f"reach {label}: HTTP {r.status_code} {time.time()-t0:.1f}s body={clean(r.text, 160)}")
    except Exception as e:  # noqa: BLE001
        out.append(f"reach {label}: EXC {type(e).__name__} {time.time()-t0:.1f}s")


name, key = KEYS[0] if KEYS else ("", "")
# (a) factory API: every tag name in the first item
try:
    r = requests.get(o.FACTORY_API, params={"serviceKey": key, "pageNo": 1, "numOfRows": 3, "type": "json", "cmpnyNm": "현대자동차"}, headers=b.UA, timeout=60)
    t = r.text.strip()
    tags = set()
    if t.startswith("{"):
        import json
        d = json.loads(t)
        items = (((d.get("response") or d).get("body") or {}).get("items") or {}).get("item") or []
        items = items if isinstance(items, list) else [items]
        if items:
            tags = set(items[0].keys())
            out.append("factory first item address-like: " + clean(str({k: v for k, v in items[0].items() if re.search(r"adres|addr|lnm|jibun|lc|ctprvn|signgu|emd|li|pnu", k, re.I)}), 400))
    else:
        root = ET.fromstring(t)
        it = next(root.iter("item"), None)
        if it is not None:
            tags = {c.tag for c in it}
            out.append("factory first item address-like: " + clean(str({c.tag: c.text for c in it if re.search(r"adres|addr|lnm|jibun|lc|ctprvn|signgu|emd|li|pnu", c.tag, re.I)}), 400))
    out.append(f"factory HTTP {r.status_code} tags={sorted(tags)}")
except Exception as e:  # noqa: BLE001
    out.append(f"factory EXC {type(e).__name__} {clean(str(e), 100)}")

# (b) reachability only
reach("epost https", "https://openapi.epost.go.kr/postal/retrieveNewAdressAreaCdService/retrieveNewAdressAreaCdService/getNewAddressListAreaCd")
reach("juso addrLinkApi (no key)", "https://business.juso.go.kr/addrlink/addrLinkApi.do", {"confmKey": "x", "currentPage": 1, "countPerPage": 1, "keyword": "현대로 1077", "resultType": "json"})
reach("vworld (no key)", "https://api.vworld.kr/req/address", {"service": "address", "request": "getcoord", "type": "road", "address": "충청남도 아산시 인주면 현대로 1077", "key": "x", "format": "json"})

# (c) region code + permits with the key
dong = "경상북도 포항시 남구 괴동동"
t0 = time.time()
try:
    r = requests.get(b.REGION, params={"serviceKey": key, "locatadd_nm": dong, "type": "json", "numOfRows": 20, "pageNo": 1}, headers=b.UA, timeout=40)
    code = b.region_code(r.text, dong) if r.status_code == 200 else None
    out.append(f"region HTTP {r.status_code} {time.time()-t0:.1f}s gw={b.gateway_code(r.text)} code={code} body={clean(r.text, 120) if not code else ''}")
except Exception as e:  # noqa: BLE001
    code = None
    out.append(f"region EXC {type(e).__name__} {time.time()-t0:.1f}s")
if code:
    t0 = time.time()
    try:
        r = requests.get(b.ARCH, params={"serviceKey": key, "sigunguCd": code[:5], "bjdongCd": code[5:], "platGbCd": "0", "bun": "0001", "numOfRows": 5, "pageNo": 1, "_type": "json"}, headers=b.UA, timeout=40)
        n = len(b.permits(r.text)) if r.status_code == 200 and r.text.strip().startswith("{") else None
        out.append(f"arch HTTP {r.status_code} {time.time()-t0:.1f}s gw={b.gateway_code(r.text)} rows={n} body={clean(r.text, 160) if n is None else ''}")
    except Exception as e:  # noqa: BLE001
        out.append(f"arch EXC {type(e).__name__} {time.time()-t0:.1f}s")

packs, cur = [], ""
for n in out:
    n = n.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(n) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + n
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
