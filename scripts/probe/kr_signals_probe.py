"""One-off isolated probe (no repo writes, no private store). Prints status codes, counts and field names only."""
import os
import re
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
OUT = []


def note(*a):
    OUT.append(" ".join(str(x) for x in a).replace("\r", " ").replace("\n", " ").replace("%", "pct"))


def safe(label, fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001 — probe reports everything
        note(f"{label}: {type(e).__name__} {str(e)[:160]}")


def komis():
    s = requests.Session()
    r = s.get("https://www.komis.or.kr/Komis/RsrcPrice/BaseMetals", headers=UA, timeout=30)
    note("KOMIS page", r.status_code, len(r.text))
    h = {**UA, "X-Requested-With": "XMLHttpRequest", "Referer": "https://www.komis.or.kr/Komis/RsrcPrice/BaseMetals"}
    c = s.post("https://www.komis.or.kr/Komis/RsrcPrice/ajax/getMnrlPriceCrtr", data={"HP000": "HP001", "mnrkndUnqCd": "MNRL0023"}, headers=h, timeout=30)
    note("KOMIS crtr", c.status_code, c.text[:160])
    crtr = c.json()["data"][0]["cdKey"]
    form = {"mnrkndUnqRadioCd": "MNRL0023", "srchMnrkndUnqCd": "MNRL0023", "srchPrcCrtr": crtr, "srchAvgOpt": "DAY",
            "srchField": "year", "srchStartDate": "2025", "srchEndDate": "2026", "srchCompareMnrkndUnqCd": "", "lmeInvt": "Y"}
    p = s.post("https://www.komis.or.kr/Komis/RsrcPrice/ajax/getMnrlPrcByMnrkndUnqCd", data=form, headers=h, timeout=30)
    j = p.json()
    rows = j["data"]["defaultMnrl"]
    note("KOMIS price", p.status_code, "rows", len(rows), "first", rows[0] if rows else None, "last", rows[-1]["crtrYmd"] if rows else None,
         "info", j.get("dataAvg", {}).get("INFO"))
    m = s.post("https://www.komis.or.kr/Komis/RsrcPrice/ajax/getMnrlPrcByMnrkndUnqCd", data={**form, "srchAvgOpt": "MONTH", "srchField": "month",
               "srchStartDate": "202401", "srchEndDate": "202610"}, headers=h, timeout=30)
    mj = m.json()["data"]["defaultMnrl"]
    note("KOMIS month", m.status_code, "rows", len(mj), "first", mj[0] if mj else None)


def ftc():
    s = requests.Session()
    r = s.get("https://case.ftc.go.kr/ocp/co/ltfr.do", params={"startRceptDt": "2026-07-01", "endRceptDt": "2026-10-27", "pageIndex": 1}, headers=UA, timeout=30)
    rows = re.findall(r'name="csno" value="([^"]+)"[\s\S]*?name="apdate" value="([^"]*)"', r.text)
    note("FTC list", r.status_code, len(r.text), "rows", len(rows), rows[:3])
    last = re.search(r"fn_goPage\((\d+)\); return false;\">마지막", r.text)
    note("FTC last page", last.group(1) if last else None)
    doc = re.search(r'fn_htmlView\(this\);"[^>]*></a>\s*<input type="hidden" value="(\d+)">\s*<input type="hidden" value="(\d+)">', r.text)
    if doc:
        d = s.get("https://case.ftc.go.kr/com/dscv/dscvHtmlView.do", params={"docId": doc.group(1), "docCnvrMnNo": doc.group(2)}, headers=UA, timeout=40)
        t = re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", d.text))
        note("FTC doc", d.status_code, len(d.text), "피심인" in t.replace(" ", ""), "주문" in t)
    else:
        note("FTC doc: no htmlView ids")


def shape(name):
    v = os.environ.get(name, "").strip()
    return f"{name} {'set' if v else 'missing'} len={len(v)}"


def kepco():
    key = os.environ.get("KEPCO_API_KEY", "").strip()
    note(shape("KEPCO_API_KEY"))
    if not key:
        return
    r = requests.get("https://bigdata.kepco.co.kr/openapi/v1/electContract.do", params={"noticeBeginDate": "20261020", "noticeEndDate": "20261027",
                     "apiKey": key, "returnType": "json"}, headers=UA, timeout=60)
    try:
        j = r.json()
    except ValueError:
        note("KEPCO", r.status_code, "not json", len(r.text), re.sub(r"[A-Za-z0-9]{30,}", "<long>", r.text[:160]))
        return
    data = j.get("data") if isinstance(j, dict) else None
    if not isinstance(data, list):
        note("KEPCO", r.status_code, "keys", list(j)[:8] if isinstance(j, dict) else type(j).__name__, str(j)[:200])
        return
    first = data[0] if data else {}
    note("KEPCO", r.status_code, "rows", len(data), "fields", sorted(first)[:60])
    note("KEPCO sample", {k: str(first.get(k))[:60] for k in ("companyId", "no", "name", "presumedPrice", "presumedAmount", "noticeDate", "progressState", "purchaseType", "placeName", "competitionType", "bidType")})
    hit = [d for d in data if re.search(r"변압기|차단기|케이블|전선|GIS|개폐", str(d.get("name")))]
    note("KEPCO keyword rows", len(hit), [(str(d.get("name"))[:50], d.get("presumedPrice"), d.get("progressState")) for d in hit[:5]])


def kosis():
    key = os.environ.get("KOSIS_API_KEY", "").strip()
    note(shape("KOSIS_API_KEY"))
    if not key:
        return
    r = requests.get("https://kosis.kr/openapi/statisticsList.do", params={"method": "getList", "apiKey": key, "vwCd": "MT_ZTITLE", "parentListId": "",
                     "format": "json", "jsonVD": "Y"}, headers=UA, timeout=40)
    note("KOSIS list", r.status_code, len(r.text), re.sub(r"[A-Za-z0-9+/=]{30,}", "<long>", r.text[:200]))


def ecos():
    key = os.environ.get("ECOS_API_KEY", "").strip()
    note(shape("ECOS_API_KEY"))
    if not key:
        return
    r = requests.get(f"https://ecos.bok.or.kr/api/StatisticTableList/{key}/json/kr/1/3/", headers=UA, timeout=40)
    note("ECOS list", r.status_code, len(r.text), re.sub(r"[A-Za-z0-9]{20,}", "<long>", r.text[:240]))


def reach():
    for name, url in [("KAIDA", "https://www.kaida.co.kr/"), ("KAMA", "https://www.kama.or.kr/"), ("KOSA 철강협회", "https://www.kosa.or.kr/"),
                      ("산업부", "https://www.motie.go.kr/"), ("정책브리핑", "https://www.korea.kr/"), ("KOSIS", "https://kosis.kr/openapi/"),
                      ("ECOS", "https://ecos.bok.or.kr/api/"), ("현대차 IR", "https://www.hyundai.com/worldwide/ko/company/ir"),
                      ("기아 IR", "https://worldwide.kia.com/kr/company/ir"), ("open.law.go.kr", "https://www.law.go.kr/DRF/lawSearch.do?target=ftc&type=XML")]:
        try:
            r = requests.get(url, headers=UA, timeout=25)
            note(f"reach {name}", r.status_code, len(r.text), r.url[:80])
        except Exception as e:  # noqa: BLE001
            note(f"reach {name}", type(e).__name__)


for label, fn in [("KEPCO", kepco), ("KOSIS", kosis), ("ECOS", ecos)]:
    safe(label, fn)
for i in range(0, len(OUT), 6):
    print("::notice title=probe-" + str(i // 6) + "::" + " | ".join(OUT[i:i + 6])[:3800])
