"""probe 110: 건축인허가 기본개요의 주용도가 빈 허가(고려아연 8공장 부지 울주 온산읍 원산리 920, pk 1000000000000000989011)를
동별개요(getApDongOulnInfo)·층별개요(getApFlrOulnInfo)에서 찾을 수 있는지. 칸 이름·값(용도·면적)만."""
import json, os, re
import requests
OUT = []
def p(*a):
    OUT.append(" ".join(str(x) for x in a))
key = (os.environ.get("CUSTOMS_API_KEY") or os.environ.get("KR_FUEL_API_KEY") or "").strip()
r = requests.get("https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList",
                 params={"serviceKey": key, "locatadd_nm": "울산광역시 울주군 온산읍 원산리", "type": "json", "numOfRows": 10, "pageNo": 1}, timeout=40)
rows = []
try:
    body = r.json()
    for part in body.get("StanReginCd", []):
        rows += part.get("row", []) if isinstance(part, dict) else []
except Exception as e:
    p("region parse", type(e).__name__, r.text[:200])
code = next((x["region_cd"] for x in rows if str(x.get("locatadd_nm", "")).strip() == "울산광역시 울주군 온산읍 원산리"), None)
p("region", code)
if code:
    base = {"sigunguCd": code[:5], "bjdongCd": code[5:10], "platGbCd": "0", "bun": "0920", "ji": "0000", "numOfRows": 50, "pageNo": 1, "_type": "json"}
    for op in ("getApBasisOulnInfo", "getApDongOulnInfo", "getApFlrOulnInfo", "getApTitleInfo" ):
        try:
            rr = requests.get(f"https://apis.data.go.kr/1613000/ArchPmsHubService/{op}", params={"serviceKey": key, **base}, timeout=40)
            j = rr.json()
            items = (((j.get("response") or {}).get("body") or {}).get("items") or {})
            items = items.get("item") if isinstance(items, dict) else items
            items = items if isinstance(items, list) else ([items] if items else [])
            p(f"== {op} HTTP {rr.status_code} items {len(items)}")
            for it in items[:6]:
                small = {k: v for k, v in it.items() if re.search(r"Pk|Purps|Area|Nm|Day|dong|flr", k, re.I) and v not in (None, "", " ")}
                p("   ", json.dumps(small, ensure_ascii=False)[:500])
        except Exception as e:
            p(f"== {op} ERR", type(e).__name__, str(e)[:120], rr.text[:160] if 'rr' in dir() else "")
text = "\n".join(OUT)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
