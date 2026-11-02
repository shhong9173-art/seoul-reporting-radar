"""probe 99: 공장등록(B550624) API 응답 시간·형식 — 출입처 이름 1개로 몇 가지 변형. 건수·시간·결과코드만 출력."""
import os, time, re, requests
OUT = []
def p(*a):
    OUT.append(" ".join(str(x) for x in a))
key = (os.environ.get("CUSTOMS_API_KEY") or os.environ.get("KR_FUEL_API_KEY") or "").strip()
p("key len", len(key))
base = "https://apis.data.go.kr/B550624/fctryRegistInfo/getFctryPrdctnService_v2"
variants = [
    ("https rows10 json", base, {"pageNo": 1, "numOfRows": 10, "type": "json", "cmpnyNm": "현대자동차"}),
    ("https rows100 json", base, {"pageNo": 1, "numOfRows": 100, "type": "json", "cmpnyNm": "현대자동차"}),
    ("http rows10", base.replace("https://", "http://"), {"pageNo": 1, "numOfRows": 10, "cmpnyNm": "현대자동차"}),
    ("https rows10 noName", base, {"pageNo": 1, "numOfRows": 10}),
    ("https rows10 금호석유화학", base, {"pageNo": 1, "numOfRows": 10, "type": "json", "cmpnyNm": "금호석유화학"}),
]
for label, url, params in variants:
    t = time.time()
    try:
        r = requests.get(url, params={"serviceKey": key, **params}, timeout=(15, 150))
        txt = r.text
        code = re.search(r'"resultCode"\s*:\s*"?([^",}]+)|<resultCode>([^<]+)|<returnReasonCode>([^<]+)', txt)
        total = re.search(r'"totalCount"\s*:\s*(\d+)|<totalCount>(\d+)', txt)
        p(label, "HTTP", r.status_code, f"{time.time()-t:.1f}s", "len", len(txt), "code", code and next(g for g in code.groups() if g),
          "total", total and next(g for g in total.groups() if g), "head", re.sub(r"\s+", " ", txt[:120]) if not total else "")
    except Exception as e:
        p(label, "ERR", type(e).__name__, f"{time.time()-t:.1f}s")
    time.sleep(2)
for label, url in [("law.go.kr", "https://www.law.go.kr/DRF/lawSearch.do?OC=test&target=admrul&type=XML&query=%EC%A0%84%EA%B8%B0"),
                   ("gwanbo", "https://gwanbo.go.kr")]:
    t = time.time()
    try:
        r = requests.get(url, timeout=(15, 60))
        p(label, "HTTP", r.status_code, f"{time.time()-t:.1f}s", "len", len(r.text))
    except Exception as e:
        p(label, "ERR", type(e).__name__, f"{time.time()-t:.1f}s")
text = "\n".join(OUT)
open("probe_out.txt", "w").write(text)
print(text)
