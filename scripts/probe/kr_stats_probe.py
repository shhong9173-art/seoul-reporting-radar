"""Isolated probe: find KOSIS tables and ECOS item codes for beat statistics. Prints names/ids/counts only."""
import os
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
OUT = []
KOSIS = os.environ.get("KOSIS_API_KEY", "").strip()
ECOS = os.environ.get("ECOS_API_KEY", "").strip()


def note(*a):
    OUT.append(" ".join(str(x) for x in a).replace("\r", " ").replace("\n", " ").replace("%", "pct"))


def kosis_search(q):
    r = requests.get("https://kosis.kr/openapi/statisticsSearch.do", params={"method": "getList", "apiKey": KOSIS, "searchNm": q, "format": "json",
                     "jsonVD": "Y", "startCount": 1, "resultCount": 12, "sort": "RANK"}, headers=UA, timeout=40)
    try:
        j = r.json()
    except ValueError:
        note("KOSIS", q, r.status_code, r.text[:120])
        return
    if isinstance(j, dict):
        note("KOSIS", q, "dict", str(j)[:200])
        return
    note("KOSIS", q, len(j), " ; ".join(f"{x.get('ORG_ID')}/{x.get('TBL_ID')} {x.get('TBL_NM')} [{x.get('ORG_NM')}] {x.get('STRT_PRD_DE', '')}-{x.get('END_PRD_DE', '')}" for x in j[:8]))


def ecos_items(code, pat):
    r = requests.get(f"https://ecos.bok.or.kr/api/StatisticItemList/{ECOS}/json/kr/1/2000/{code}", headers=UA, timeout=40)
    j = r.json()
    rows = (j.get("StatisticItemList") or {}).get("row") or []
    hit = [x for x in rows if re.search(pat, x.get("ITEM_NAME", ""))]
    note("ECOS", code, len(rows), "hits", len(hit), " ; ".join(f"{x.get('GRP_NAME')}:{x.get('ITEM_CODE')}={x.get('ITEM_NAME')}({x.get('CYCLE')},{x.get('START_TIME')}-{x.get('END_TIME')})" for x in hit[:25]))


def ecos_tables(pat):
    r = requests.get(f"https://ecos.bok.or.kr/api/StatisticTableList/{ECOS}/json/kr/1/1000/", headers=UA, timeout=40)
    rows = (r.json().get("StatisticTableList") or {}).get("row") or []
    hit = [x for x in rows if re.search(pat, x.get("STAT_NAME", "")) and x.get("SRCH_YN") == "Y"]
    note("ECOS tables", pat, " ; ".join(f"{x.get('STAT_CODE')}={x.get('STAT_NAME')}({x.get('CYCLE')})" for x in hit[:20]))


def kosis_meta(org, tbl, pat):
    r = requests.get("https://kosis.kr/openapi/statisticsData.do", params={"method": "getMeta", "apiKey": KOSIS, "format": "json", "jsonVD": "Y",
                     "type": "ITM", "orgId": org, "tblId": tbl}, headers=UA, timeout=60)
    try:
        j = r.json()
    except ValueError:
        note("KOSIS meta", tbl, r.status_code, r.text[:150])
        return
    if isinstance(j, dict):
        note("KOSIS meta", tbl, str(j)[:200])
        return
    objs = {}
    for x in j:
        objs.setdefault(x.get("OBJ_ID"), []).append(x)
    note("KOSIS meta", tbl, "objs", {k: (len(v), v[0].get("OBJ_NM")) for k, v in objs.items()})
    hit = [x for x in j if re.search(pat, str(x.get("ITM_NM", "")))]
    note("KOSIS meta hits", tbl, " ; ".join(f"{x.get('OBJ_ID')}:{x.get('ITM_ID')}={x.get('ITM_NM')}({x.get('UNIT_NM', '')})" for x in hit[:40]))


def kosis_prd(org, tbl):
    r = requests.get("https://kosis.kr/openapi/statisticsData.do", params={"method": "getMeta", "apiKey": KOSIS, "format": "json", "jsonVD": "Y",
                     "type": "PRD", "orgId": org, "tblId": tbl}, headers=UA, timeout=60)
    note("KOSIS prd", tbl, r.text[:300])


PRODUCTS = r"승용|자동차|화물|타이어|열연|냉연|후판|강판|선재|철근|형강|강관|조강|선철|전기로|아연|동|전선|케이블|변압기|차단기|전동기|발전기|축전지|폴리|에틸렌|합성수지|조선|계"
for org, tbl in [("101", "DT_1F02012"), ("363", "TX_36301_A000")]:
    for fn in (lambda: kosis_meta(org, tbl, PRODUCTS), lambda: kosis_prd(org, tbl)):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            note("KOSIS", tbl, type(e).__name__)
for q in ["자동차 내수판매", "자동차산업 동향", "완성차 판매"]:
    try:
        kosis_search(q)
    except Exception as e:  # noqa: BLE001
        note("KOSIS", q, type(e).__name__)
PAT = r"철강|열연|냉연|후판|도금|선재|철근|봉강|강관|동괴|동선|나동|구리|아연|알루미늄|전선|케이블|변압기|전동기|발전기|개폐|승용차|화물자동차|자동차부품|타이어|축전지"
for code in ["404Y016", "402Y016", "401Y017"]:
    try:
        r = requests.get(f"https://ecos.bok.or.kr/api/StatisticItemList/{ECOS}/json/kr/1/5000/{code}", headers=UA, timeout=60)
        rows = (r.json().get("StatisticItemList") or {}).get("row") or []
        hit = [x for x in rows if re.search(PAT, x.get("ITEM_NAME", "")) and x.get("CYCLE") == "M"]
        note("ECOS", code, len(rows), "hits", len(hit), " ; ".join(f"{x.get('ITEM_CODE')}={x.get('ITEM_NAME')}({x.get('START_TIME')}-{x.get('END_TIME')},{x.get('UNIT_NAME')})" for x in hit[:45]))
    except Exception as e:  # noqa: BLE001
        note("ECOS", code, type(e).__name__)
for i in range(0, len(OUT), 2):
    print(f"::notice title=stats-{i // 2:02d}::" + " | ".join(OUT[i:i + 2])[:3900])
