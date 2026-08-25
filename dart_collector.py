import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("DART_API_KEY", "").strip()
OUT = "dart.json"

# Core Korean auto/battery/parts issuers. DART corp codes are resolved dynamically.
TARGET_NAMES = [
    "현대자동차", "기아", "현대모비스", "현대위아", "현대오토에버",
    "LG에너지솔루션", "삼성SDI", "SK이노베이션", "SK온", "LG이노텍",
    "한온시스템", "HL만도", "에스엘", "한국타이어앤테크놀로지", "금호타이어",
    "세방전지", "삼성전기", "두산밥캣", "만도", "포스코퓨처엠", "엘앤에프",
]

REPORT_KEYWORDS = [
    "시설투자", "신규시설", "유상증자", "출자", "타법인주식", "지분", "자회사",
    "생산", "생산능력", "공장", "설비", "투자", "수주", "공급", "계약", "배터리",
    "전기차", "ESS", "북미", "미국", "유럽", "중국", "AAM", "로보택시"
]


def get_json(url):
    req = Request(url, headers={"User-Agent": "auto-desk-radar/1.0"})
    with urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_corp_codes():
    if not API_KEY:
        return {}
    # list.json is used as a compact public endpoint helper when available.
    params = urlencode({"crtfc_key": API_KEY})
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?{params}"
    try:
        import zipfile
        import io
        from xml.etree import ElementTree as ET
        req = Request(url, headers={"User-Agent": "auto-desk-radar/1.0"})
        with urlopen(req, timeout=30) as r:
            raw = r.read()
        z = zipfile.ZipFile(io.BytesIO(raw))
        name = z.namelist()[0]
        data = z.read(name)
        root = ET.fromstring(data)
        found = {}
        for item in root.findall("list"):
            corp_name = (item.findtext("corp_name") or "").strip()
            corp_code = (item.findtext("corp_code") or "").strip()
            stock_code = (item.findtext("stock_code") or "").strip()
            if corp_name in TARGET_NAMES and corp_code:
                found[corp_name] = {"corp_code": corp_code, "stock_code": stock_code}
        return found
    except Exception as e:
        print(f"DART corp code lookup failed: {e}", file=sys.stderr)
        return {}


def materialize_for_corp(name, corp):
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp["corp_code"],
        "bgn_de": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "end_de": datetime.now(timezone.utc).strftime("%Y%m%d"),
        "page_no": "1",
        "page_count": "100",
    }
    # Use recent disclosures list. The API may return an empty list on weekends/holidays.
    url = "https://opendart.fss.or.kr/api/list.json?" + urlencode(params)
    try:
        data = get_json(url)
    except Exception as e:
        return {"corpName": name, "items": [], "error": str(e)}
    items = []
    for row in data.get("list", []) or []:
        title = (row.get("report_nm") or "").strip()
        if not any(k.lower() in title.lower() for k in REPORT_KEYWORDS):
            continue
        items.append({
            "corpName": name,
            "corpCode": corp["corp_code"],
            "stockCode": corp.get("stock_code", ""),
            "receiptNo": row.get("rcept_no", ""),
            "reportName": title,
            "reporter": row.get("flr_nm", ""),
            "date": row.get("rcept_dt", ""),
            "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row.get('rcept_no', '')}",
        })
    return {"corpName": name, "items": items}


def main():
    if not API_KEY:
        print("DART_API_KEY is not set", file=sys.stderr)
        json.dump([], open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return
    corps = fetch_corp_codes()
    all_items = []
    errors = []
    for name in TARGET_NAMES:
        if name not in corps:
            continue
        result = materialize_for_corp(name, corps[name])
        all_items.extend(result.get("items", []))
        if result.get("error"):
            errors.append({"corpName": name, "error": result["error"]})
    out = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "count": len(all_items),
        "items": all_items,
        "errors": errors,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"DART radar: {len(all_items)} relevant disclosures")


if __name__ == "__main__":
    main()
