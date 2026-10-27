import json
import os
import re
import requests

UA = {"User-Agent": "Mozilla/5.0"}
K = os.environ.get("KOSIS_API_KEY", "").strip()
OUT = []


def note(*a):
    OUT.append(" ".join(str(x) for x in a).replace("\r", " ").replace("\n", " ").replace("%", "pct"))


def search(q):
    r = requests.get("https://kosis.kr/openapi/statisticsSearch.do", params={"method": "getList", "apiKey": K, "searchNm": q, "format": "json", "jsonVD": "Y",
                     "startCount": 1, "resultCount": 10, "sort": "RANK"}, headers=UA, timeout=40)
    j = r.json()
    note("S", q, " ; ".join(f"{x.get('ORG_ID')}/{x.get('TBL_ID')} {x.get('TBL_NM')} [{x.get('ORG_NM')}] {x.get('STRT_PRD_DE', '')}-{x.get('END_PRD_DE', '')}" for x in (j if isinstance(j, list) else [])[:8]))


def meta(org, tbl):
    r = requests.get("https://kosis.kr/openapi/statisticsData.do", params={"method": "getMeta", "apiKey": K, "format": "json", "jsonVD": "Y", "type": "ITM",
                     "orgId": org, "tblId": tbl}, headers=UA, timeout=40)
    j = r.json()
    note("M", tbl, " ; ".join(f"{x.get('OBJ_ID')}:{x.get('ITM_ID')}={x.get('ITM_NM')}" for x in (j if isinstance(j, list) else [])[:40]))
    r = requests.get("https://kosis.kr/openapi/statisticsData.do", params={"method": "getMeta", "apiKey": K, "format": "json", "jsonVD": "Y", "type": "PRD",
                     "orgId": org, "tblId": tbl}, headers=UA, timeout=40)
    note("P", tbl, r.text[:200])


for q in ["자동차 생산 내수 수출 업체별", "자동차 판매 실적", "완성차 내수", "자동차 생산대수"]:
    try:
        search(q)
    except Exception as e:  # noqa: BLE001
        note("S", q, type(e).__name__)
for org, tbl in [("115", "DT_115036_A051"), ("115", "DT_115036_A012")]:
    try:
        meta(org, tbl)
    except Exception as e:  # noqa: BLE001
        note("M", tbl, type(e).__name__)
for name, url in [("KAMA 통계", "https://www.kama.or.kr/MainController?cmd=KAMA_STAT"), ("현대차 판매", "https://www.hyundai.com/worldwide/ko/company/ir/ir-resources/sales-results")]:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        note("R", name, r.status_code, len(r.text), re.findall(r"(판매실적|월간|자동차산업 동향|xlsx|\.pdf)", r.text)[:8])
    except Exception as e:  # noqa: BLE001
        note("R", name, type(e).__name__)
for i in range(0, len(OUT), 3):
    print(f"::notice title=auto-{i // 3:02d}::" + " | ".join(OUT[i:i + 3])[:3900])
