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


def ecos_data(stat, item):
    r = requests.get(f"https://ecos.bok.or.kr/api/StatisticSearch/{ECOS}/json/kr/1/400/{stat}/M/202401/202612/{item}", headers=UA, timeout=60)
    j = r.json()
    rows = (j.get("StatisticSearch") or {}).get("row") or []
    note("ECOS data", stat, item, r.status_code, "rows", len(rows), "keys", sorted(rows[0]) if rows else str(j)[:150], "last", rows[-1] if rows else None)


def kosis_data(org, tbl, obj, itm="ALL", start="202401", end="202612"):
    r = requests.get("https://kosis.kr/openapi/Param/statisticsParameterData.do", params={"method": "getList", "apiKey": KOSIS, "itmId": itm, "objL1": obj,
                     "format": "json", "jsonVD": "Y", "prdSe": "M", "startPrdDe": start, "endPrdDe": end, "orgId": org, "tblId": tbl}, headers=UA, timeout=60)
    try:
        j = r.json()
    except ValueError:
        note("KOSIS data", tbl, obj, r.status_code, r.text[:160])
        return
    if isinstance(j, dict):
        note("KOSIS data", tbl, obj, str(j)[:200])
        return
    note("KOSIS data", tbl, obj, "rows", len(j), "keys", sorted(j[0]) if j else None, "first", {k: j[0].get(k) for k in ("PRD_DE", "DT", "UNIT_NM", "C1_NM", "ITM_ID", "ITM_NM")} if j else None,
         "items", sorted({(x.get("ITM_ID"), x.get("ITM_NM")) for x in j})[:8], "last", j[-1].get("PRD_DE") if j else None)


for fn in (lambda: ecos_data("404Y016", "30712502AA"), lambda: ecos_data("402Y016", "31211107AA"), lambda: kosis_data("363", "TX_36301_A000", "15363AA1AA"),
           lambda: kosis_data("101", "DT_1F02012", "24224208"), lambda: kosis_meta("101", "DT_1F02012", r".")):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        note("ERR", type(e).__name__, str(e)[:120])
for i in range(0, len(OUT), 2):
    print(f"::notice title=stats-{i // 2:02d}::" + " | ".join(OUT[i:i + 2])[:3900])
