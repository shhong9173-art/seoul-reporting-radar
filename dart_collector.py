import io
import json
import os
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("DART_API_KEY", "").strip()
OUT = "dart.json"
LOOKBACK_DAYS = 30
TARGET_NAMES = [
    "현대자동차", "기아", "현대모비스", "현대위아", "현대오토에버",
    "LG에너지솔루션", "삼성SDI", "SK이노베이션", "LG이노텍", "한온시스템",
    "HL만도", "에스엘", "한국타이어앤테크놀로지", "금호타이어", "세방전지",
    "삼성전기", "포스코퓨처엠", "엘앤에프", "포스코인터내셔널",
    "포스코홀딩스", "포스코", "현대제철", "동국제강", "세아제강",
    "고려아연", "영풍", "풍산", "두산에너빌리티", "HD현대일렉트릭",
    "엘에스일렉트릭", "효성중공업", "일진전기", "가온전선", "대한전선",
    "LS전선아시아", "GS", "GS칼텍스", "한화솔루션", "OCI홀딩스",
    "씨에스윈드", "LG화학", "롯데케미칼", "금호석유화학", "효성첨단소재",
    "코오롱인더", "LS MnM"
]
KEYWORDS = [
    "시설투자", "신규시설", "유상증자", "출자", "타법인주식", "지분", "자회사",
    "생산", "생산능력", "생산중단", "공장", "설비", "투자", "수주", "공급", "계약",
    "배터리", "전기차", "ESS", "북미", "미국", "유럽", "중국", "AAM", "로보택시",
    "철강", "제철", "열연", "냉연", "후판", "철근", "아연", "구리", "니켈", "비철",
    "변압기", "차단기", "전력기기", "HVDC", "해저케이블", "초고압케이블", "전력망",
    "풍력", "해상풍력", "태양광", "재생에너지", "석유화학", "화학", "소재", "구조조정",
    "반덤핑", "관세", "통상", "사업보고서", "분기보고서", "반기보고서", "주요사항보고서",
    "영업양수도", "합병", "분할"
]

def fetch_bytes(url, timeout=25):
    req = Request(url, headers={"User-Agent": "auto-desk-radar/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read()

def get_json(url):
    return json.loads(fetch_bytes(url, timeout=20).decode("utf-8"))

def fetch_corp_codes():
    if not API_KEY:
        return {}
    try:
        raw = fetch_bytes(
            "https://opendart.fss.or.kr/api/corpCode.xml?" + urlencode({"crtfc_key": API_KEY}),
            timeout=40,
        )
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            data = z.read(z.namelist()[0])
        from xml.etree import ElementTree as ET
        root = ET.fromstring(data)
        wanted = set(TARGET_NAMES)
        found = {}
        for item in root.findall("list"):
            name = (item.findtext("corp_name") or "").strip()
            if name not in wanted:
                continue
            code = (item.findtext("corp_code") or "").strip()
            stock = (item.findtext("stock_code") or "").strip()
            if code:
                found[name] = {"corp_code": code, "stock_code": stock}
        return found
    except Exception as e:
        print(f"DART corp code lookup failed: {e}", file=sys.stderr)
        return {}

def fetch_company(name, corp):
    today = datetime.now(timezone.utc).date()
    begin = today - timedelta(days=LOOKBACK_DAYS)
    params = {
        "crtfc_key": API_KEY,
        "corp_code": corp["corp_code"],
        "bgn_de": begin.strftime("%Y%m%d"),
        "end_de": today.strftime("%Y%m%d"),
        "page_no": "1",
        "page_count": "100",
    }
    try:
        data = get_json("https://opendart.fss.or.kr/api/list.json?" + urlencode(params))
        if str(data.get("status")) not in {"000", "013"}:
            return {"name": name, "items": [], "error": f"status {data.get('status')}: {data.get('message','')}"}
        items = []
        for row in data.get("list", []) or []:
            report = (row.get("report_nm") or "").strip()
            if not any(k.lower() in report.lower() for k in KEYWORDS):
                continue
            receipt = row.get("rcept_no", "")
            items.append({
                "corpName": name,
                "corpCode": corp["corp_code"],
                "stockCode": corp.get("stock_code", ""),
                "corpClass": row.get("corp_cls", ""),
                "receiptNo": receipt,
                "reportName": report,
                "reporter": row.get("flr_nm", ""),
                "date": row.get("rcept_dt", ""),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
                "signalText": f"{name} {report}",
            })
        return {"name": name, "items": items}
    except Exception as e:
        return {"name": name, "items": [], "error": str(e)}

def main():
    if not API_KEY:
        payload = {"generatedAt": datetime.now(timezone.utc).isoformat(), "lookbackDays": LOOKBACK_DAYS, "count": 0, "items": [], "errors": [{"error": "DART_API_KEY is not set"}]}
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return
    corps = fetch_corp_codes()
    if not corps:
        payload = {"generatedAt": datetime.now(timezone.utc).isoformat(), "lookbackDays": LOOKBACK_DAYS, "count": 0, "items": [], "errors": [{"error": "No target corp codes resolved"}]}
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print("DART radar: 0 relevant disclosures", file=sys.stderr)
        return
    all_items, errors = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_company, name, corps[name]): name for name in corps}
        for fut in as_completed(futures):
            result = fut.result()
            all_items.extend(result.get("items", []))
            if result.get("error"):
                errors.append({"corpName": result.get("name"), "error": result["error"]})
    all_items.sort(key=lambda x: (x.get("date", ""), x.get("corpName", "")), reverse=True)
    dedup, seen = [], set()
    for row in all_items:
        key = row.get("receiptNo") or (row.get("corpName"), row.get("reportName"), row.get("date"))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(row)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "lookbackDays": LOOKBACK_DAYS,
        "targetCorpCount": len(corps),
        "count": len(dedup),
        "items": dedup,
        "errors": errors,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"DART radar: {len(dedup)} relevant disclosures across {len(corps)} target companies")

if __name__ == "__main__": main()
