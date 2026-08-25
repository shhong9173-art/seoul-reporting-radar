import json
import os
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_KEY = os.environ.get("DART_API_KEY", "").strip()
OUT = "dart.json"
LOOKBACK_DAYS = 30
TARGET_NAMES = {
    "현대자동차","기아","현대모비스","현대위아","현대오토에버",
    "LG에너지솔루션","삼성SDI","SK이노베이션","LG이노텍","한온시스템",
    "HL만도","에스엘","한국타이어앤테크놀로지","금호타이어","세방전지",
    "삼성전기","포스코퓨처엠","엘앤에프","포스코인터내셔널"
}
KEYWORDS = [
    "시설투자","신규시설","유상증자","출자","타법인주식","지분","자회사",
    "생산","생산능력","공장","설비","투자","수주","공급","계약","배터리",
    "전기차","ESS","북미","미국","유럽","중국","AAM","로보택시",
    "사업보고서","분기보고서","반기보고서","주요사항보고서","영업양수도","합병","분할"
]

def get_json(url):
    req = Request(url, headers={"User-Agent":"auto-desk-radar/1.0"})
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    today = datetime.now(timezone.utc).date()
    begin = today - timedelta(days=LOOKBACK_DAYS)
    if not API_KEY:
        payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"lookbackDays":LOOKBACK_DAYS,"count":0,"items":[],"errors":[{"error":"DART_API_KEY is not set"}]}
        json.dump(payload,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
        return
    rows=[]
    errors=[]
    try:
        for page in range(1,4):
            params={"crtfc_key":API_KEY,"bgn_de":begin.strftime("%Y%m%d"),"end_de":today.strftime("%Y%m%d"),"page_no":str(page),"page_count":"100"}
            data=get_json("https://opendart.fss.or.kr/api/list.json?"+urlencode(params))
            status=str(data.get("status",""))
            if status not in {"000","013"}:
                raise RuntimeError(f"DART API status {status}: {data.get('message','')}")
            batch=data.get("list",[]) or []
            rows.extend(batch)
            if len(batch)<100: break
    except Exception as e:
        errors.append({"error":str(e)})
    items=[]
    for row in rows:
        corp=(row.get("corp_name") or "").strip()
        if corp not in TARGET_NAMES: continue
        report=(row.get("report_nm") or "").strip()
        if not any(k.lower() in report.lower() for k in KEYWORDS): continue
        receipt=row.get("rcept_no","")
        items.append({
            "corpName":corp,
            "corpCode":row.get("corp_code",""),
            "stockCode":row.get("stock_code",""),
            "corpClass":row.get("corp_cls",""),
            "receiptNo":receipt,
            "reportName":report,
            "reporter":row.get("flr_nm",""),
            "date":row.get("rcept_dt",""),
            "url":f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
            "signalText":f"{corp} {report}"
        })
    items.sort(key=lambda x:(x.get("date",""),x.get("corpName","")),reverse=True)
    payload={"generatedAt":datetime.now(timezone.utc).isoformat(),"lookbackDays":LOOKBACK_DAYS,"count":len(items),"items":items,"errors":errors}
    json.dump(payload,open(OUT,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
    print(f"DART radar: {len(items)} relevant disclosures")
    if errors: print(errors[0]["error"],file=sys.stderr)

if __name__=="__main__": main()
