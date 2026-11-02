"""probe 105: EUIPO 운영 토큰 한 번(11-02 정오 재시도). 되면 상표 검색: 현대자동차 최근 출원 5건(이름·출원일·상품류만). 키·토큰 값은 남기지 않는다."""
import os, re
import requests
out = []
CID = os.environ.get("EUIPO_CLIENT_ID", "").strip()
SEC = os.environ.get("EUIPO_CLIENT_SECRET", "").strip()
out.append(f"id len {len(CID)} secret len {len(SEC)}")
try:
    rr = requests.post("https://auth.euipo.europa.eu/oidc/accessToken", data={"grant_type": "client_credentials", "scope": "uid"},
                       auth=(CID, SEC), headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=40)
    ct = rr.headers.get("content-type", "")
    out.append(f"token HTTP {rr.status_code} ctype {ct[:40]} " + (f"keys {sorted(rr.json().keys())}" if ct.startswith("application/json") else re.sub(r"\s+", " ", rr.text[:160])))
    tok = rr.json().get("access_token") if ct.startswith("application/json") else None
    if tok:
        q = 'applicants.name=="*HYUNDAI MOTOR*"'
        sr = requests.get("https://api.euipo.europa.eu/trademark-search/trademarks", params={"query": q, "size": 10, "sort": "applicationDate:desc"},
                          headers={"Authorization": f"Bearer {tok}", "X-IBM-Client-Id": CID, "Accept": "application/json"}, timeout=40)
        sct = sr.headers.get("content-type", "")
        out.append(f"search HTTP {sr.status_code} ctype {sct[:30]}")
        if sct.startswith("application/json"):
            j = sr.json()
            items = j.get("trademarks") or j.get("content") or []
            out.append(f"  keys {sorted(j.keys())[:12]} items {len(items)} total {j.get('totalElements')}")
            if items:
                out.append("  fields " + ", ".join(sorted(items[0].keys()))[:700])
            for it in items[:5]:
                wv = (it.get("wordMarkSpecification") or {}).get("verbalElement") if isinstance(it.get("wordMarkSpecification"), dict) else None
                out.append(f"  - {it.get('applicationNumber')} {it.get('applicationDate')} {wv or it.get('markFeature')} classes {it.get('niceClasses')} status {it.get('status')} applicants {[a.get('name') for a in it.get('applicants') or [] if isinstance(a, dict)][:2]}")
        else:
            out.append("  " + re.sub(r"\s+", " ", sr.text[:200]))
except Exception as e:  # noqa: BLE001
    out.append(f"token {type(e).__name__} {str(e)[:100]}")
text = "\n".join(out)
for v in (CID, SEC):
    if v:
        text = text.replace(v, "<X>")
text = re.sub(r"eyJ[A-Za-z0-9_\-\.]{20,}", "<TOKEN>", text)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
