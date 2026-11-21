"""한전 전력데이터개방포털 electContract 응답 칸 이름(값은 안 찍음) — 개찰·낙찰 칸이 있는지(요청 1번)"""
import os, collections, requests, datetime as dt
key = os.environ.get("KEPCO_API_KEY", "").strip()
now = dt.date.today()
r = requests.get("https://bigdata.kepco.co.kr/openapi/v1/electContract.do", params={"noticeBeginDate": (now - dt.timedelta(days=30)).strftime("%Y%m%d"),
                 "noticeEndDate": now.strftime("%Y%m%d"), "apiKey": key, "returnType": "json"}, timeout=90)
print("status", r.status_code)
data = r.json().get("data") or []
print("rows", len(data))
keys = collections.Counter(k for d in data for k in d)
print(sorted(keys))
st = collections.Counter(str(d.get("progressState")) for d in data)
print(st)
filled = collections.Counter(k for d in data for k, v in d.items() if v not in (None, "", 0, "0"))
print("filled", sorted(filled.items()))
