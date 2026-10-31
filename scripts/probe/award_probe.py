"""Probe 24: EDIS 로그인 인증(EDIS3 안내서: POST /data/secretKey/{username}, password 폼 → secretKey, Authorization: Basic base64(user:key)).
공개 로그라 내용은 적지 않는다 — 상태 코드·길이·쪽수·낱말 개수만. 아이디·비밀번호·키 값은 출력하지 않는다. 저장하지 않음."""
import base64
import io
import os
import re
import requests

out = []
user, pw = os.environ.get("EDIS_USERNAME", "").strip(), os.environ.get("EDIS_PASSWORD", "")
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
if not user or not pw:
    out.append(f"비밀값 없음: username={'있음' if user else '없음'} password={'있음' if pw else '없음'}")
else:
    r = requests.post(f"https://edis.usitc.gov/data/secretKey/{user}", data={"password": pw}, headers=UA, timeout=60)
    key = (re.search(r"<secretKey>(.*?)</secretKey>", r.text, re.S) or [None, ""])[1].strip()
    err = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))[:160] if not key else ""
    out.append(f"secretKey: HTTP {r.status_code} type={r.headers.get('content-type')} key_len={len(key)} {('err=' + err) if err else ''}")
    if key:
        auth = {"Authorization": "Basic " + base64.b64encode(f"{user}:{key}".encode()).decode(), **UA}
        for doc in ("898408",):
            a = requests.get(f"https://edis.usitc.gov/data/attachment/{doc}", headers=auth, timeout=60)
            ids = re.findall(r"<id>(\d+)</id>", a.text)
            out.append(f"attachment list {doc}: HTTP {a.status_code} ids={len(ids)} tags={sorted(set(re.findall(r'<([A-Za-z]+)>', a.text)))[:20]}")
            if ids:
                d = requests.get(f"https://edis.usitc.gov/data/download/{doc}/{ids[0]}", headers=auth, timeout=120)
                out.append(f"download: HTTP {d.status_code} type={d.headers.get('content-type')} bytes={len(d.content)} pdf={d.content[:5] == b'%PDF-'}")
                if d.content[:5] == b"%PDF-":
                    import pypdf
                    pdf = pypdf.PdfReader(io.BytesIO(d.content))
                    text = " ".join((p.extract_text() or "") for p in pdf.pages)
                    out.append(f"pages={len(pdf.pages)} chars={len(text)} " + " ".join(f"{w}:{len(re.findall(w, text, re.I))}" for w in
                               ("with prejudice", "without prejudice", "refil", "Hanwha", "Section 232", "public interest", "invalid")))
        anon = requests.get("https://edis.usitc.gov/data/download/898408/1", headers=UA, timeout=60)
        out.append(f"(비교) 로그인 없이 내려받기: HTTP {anon.status_code}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
