"""Probe 26: EDIS API 토큰(Authorization: Bearer, 안내서 v1.1) — 첨부 목록·내려받기. 공개 로그라 내용은 적지 않음(상태·길이·쪽수·낱말 개수만).
토큰 값은 출력하지 않는다. 저장하지 않음."""
import io
import os
import re
import requests

out = []
tok = os.environ.get("EDIS_API_TOKEN", "").strip()
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
if not tok:
    out.append("EDIS_API_TOKEN 없음")
else:
    out.append(f"token len={len(tok)} parts={tok.count('.') + 1}")
    auth = {"Authorization": f"Bearer {tok}", **UA}
    a = requests.get("https://edis.usitc.gov/data/attachment/898408", headers=auth, timeout=60)
    out.append(f"attachment list: HTTP {a.status_code} type={a.headers.get('content-type')} len={len(a.text)} tags={sorted(set(re.findall(r'<([A-Za-z]+)>', a.text)))[:25]}")
    uris = re.findall(r"<downloadUri>(.*?)</downloadUri>", a.text)
    ids = re.findall(r"<id>(\d+)</id>", a.text)
    out.append(f"downloadUri={len(uris)} ids={len(ids)} pages_tag={re.findall(r'<pageCount>(\d+)</pageCount>', a.text)[:3]}")
    url = uris[0] if uris else (f"https://edis.usitc.gov/data/download/898408/{ids[0]}" if ids else None)
    if url:
        d = requests.get(url, headers=auth, timeout=120)
        out.append(f"download: HTTP {d.status_code} type={d.headers.get('content-type')} bytes={len(d.content)} pdf={d.content[:5] == b'%PDF-'}")
        if d.content[:5] == b"%PDF-":
            import pypdf
            pdf = pypdf.PdfReader(io.BytesIO(d.content))
            text = " ".join((p.extract_text() or "") for p in pdf.pages)
            out.append(f"pages={len(pdf.pages)} chars={len(text)} " + " ".join(f"[{w}]={len(re.findall(w, text, re.I))}" for w in
                       ("with prejudice", "without prejudice", "refil", "Hanwha", "Section 232", "public interest", "invalid")))
        noauth = requests.get(url, headers=UA, timeout=60)
        out.append(f"(비교) 토큰 없이: HTTP {noauth.status_code}")
    else:
        out.append("body: " + re.sub(r"\s+", " ", a.text[:300]))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
