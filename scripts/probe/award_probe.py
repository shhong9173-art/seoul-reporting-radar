"""probe 102: 한전 빅데이터 전자입찰(electContract) 응답 칸 — 개찰·종료 상태 행에 낙찰자·계약 칸이 있는지(칸 이름·채워진 수만)."""
import collections, json, os, re
import requests
OUT = []
def p(*a):
    OUT.append(" ".join(str(x) for x in a))
key = os.environ.get("KEPCO_API_KEY", "").strip()
p("key", bool(key))
import datetime as dt
end = dt.date(2026, 11, 2); beg = end - dt.timedelta(days=60)
r = requests.get("https://bigdata.kepco.co.kr/openapi/v1/electContract.do",
                 params={"noticeBeginDate": beg.strftime("%Y%m%d"), "noticeEndDate": end.strftime("%Y%m%d"), "apiKey": key, "returnType": "json"}, timeout=120)
p("HTTP", r.status_code, "len", len(r.text))
body = r.json()
data = body.get("data") or []
p("top keys", sorted(body.keys()), "rows", len(data))
states = collections.Counter(str(d.get("progressState")) for d in data)
p("states", dict(states))
filled = collections.Counter()
for d in data:
    for k, v in d.items():
        if v not in (None, "", [], {}):
            filled[k] += 1
p("keys(filled/rows)", ", ".join(f"{k}:{n}" for k, n in sorted(filled.items())))
allkeys = sorted({k for d in data for k in d})
p("all keys", allkeys)
for st in ("OpenTimed", "Final", "Fail"):
    rows = [d for d in data if str(d.get("progressState")) == st][:2]
    for d in rows:
        p(f"sample {st}:", json.dumps({k: (str(v)[:60] if v is not None else None) for k, v in d.items() if not re.search(r"filename|file", k)}, ensure_ascii=False)[:1200])
text = "\n".join(OUT)
open("/tmp/probe_out.txt", "w").write(text)
print(text)
