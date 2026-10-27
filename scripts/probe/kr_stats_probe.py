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


for q in ["광업제조업동향", "자동차 생산 내수 수출", "조강 생산", "철강 생산", "전선", "수입차", "산업별 생산지수"]:
    try:
        kosis_search(q)
    except Exception as e:  # noqa: BLE001
        note("KOSIS", q, type(e).__name__)
for pat in ["생산자물가", "수출물가", "수입물가"]:
    try:
        ecos_tables(pat)
    except Exception as e:  # noqa: BLE001
        note("ECOS tables", pat, type(e).__name__)
for code in ["404Y014", "402Y014", "401Y015"]:
    try:
        ecos_items(code, r"철강|열연|냉연|후판|강판|선재|철근|동|구리|아연|알루미늄|전선|케이블|변압기|전동기|발전기|승용차|자동차|타이어|폴리|합성수지|원유")
    except Exception as e:  # noqa: BLE001
        note("ECOS", code, type(e).__name__)
for i in range(0, len(OUT), 3):
    print(f"::notice title=stats-{i // 3:02d}::" + " | ".join(OUT[i:i + 3])[:3900])
