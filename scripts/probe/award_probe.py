"""probe 247: 관보 문서 API가 게재 전(다음 호) 문서를 언제부터 보여 주는지. 공개 자료만, 저장 안 함."""
import datetime as dt, re

import requests

OUT = []
H = {"User-Agent": "seoul-reporting-radar probe (contact: github.com/shhong9173-art/seoul-reporting-radar)", "Accept": "application/json"}
try:
    now = dt.datetime.now(dt.timezone.utc)
    OUT.append("지금 " + now.isoformat(timespec="minutes"))
    pi = requests.get("https://www.federalregister.gov/api/v1/public-inspection-documents/current.json", headers=H, timeout=60).json()
    res = pi.get("results") or []
    by = {}
    for x in res:
        by.setdefault((x.get("publication_date"), x.get("filing_type")), []).append(x.get("document_number"))
    OUT.append("사전 공개본: " + " · ".join(f"게재 {k[0]} {k[1]} {len(v)}건" for k, v in sorted(by.items(), key=lambda kv: str(kv[0]))) + f" · regular 갱신 {pi.get('regular_filings_updated_at')} · special 갱신 {pi.get('special_filings_updated_at')}")
    for day in ("2026-11-13", "2026-11-16", "2026-11-17"):
        r = requests.get("https://www.federalregister.gov/api/v1/documents.json", params=[("conditions[publication_date][is]", day), ("per_page", "5"), ("fields[]", "document_number"), ("fields[]", "publication_date")], headers=H, timeout=60)
        j = r.json()
        OUT.append(f"문서 API 게재일 {day}: HTTP {r.status_code} count {j.get('count')}")
    # 무역 기관만, 게재일 11-16
    r = requests.get("https://www.federalregister.gov/api/v1/documents.json", params=[("conditions[publication_date][is]", "2026-11-16"), ("conditions[agencies][]", "international-trade-administration"), ("conditions[agencies][]", "international-trade-commission"), ("per_page", "100"), ("fields[]", "document_number"), ("fields[]", "title")], headers=H, timeout=60)
    docs = {d.get("document_number") for d in r.json().get("results") or []}
    pit = {x.get("document_number") for x in res if x.get("publication_date") == "2026-11-16" and any((a.get("slug") in ("international-trade-administration", "international-trade-commission")) for a in x.get("agencies") or [] if isinstance(a, dict))}
    OUT.append(f"무역 기관 게재일 11-16: 문서 API {len(docs)}건 · 사전 공개본 {len(pit)}건 · 둘 다 {len(docs & pit)}건 · 사전 공개본에만 {sorted(pit - docs)[:6]} · 문서 API에만 {sorted(docs - pit)[:6]}")
    # 문서 한 건의 메타(언제 만들어졌는지 단서)
    one = requests.get("https://www.federalregister.gov/api/v1/documents/2026-23258.json", headers=H, timeout=60)
    if one.status_code == 200:
        j = one.json()
        OUT.append("문서 2026-23258: " + " | ".join(f"{k}={str(j.get(k))[:80]}" for k in ("publication_date", "signing_date", "effective_on", "page_views", "start_page", "volume", "citation", "raw_text_url", "body_html_url", "public_inspection_pdf_url")))
    else:
        OUT.append(f"문서 2026-23258 HTTP {one.status_code}")
except Exception as e:
    OUT.append(f"실패 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
