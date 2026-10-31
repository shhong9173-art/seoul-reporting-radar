"""Probe 18: 현대모비스 20261028000138 정정 표 '분할반대의사통지 접수기간' 칸의 원문 XML — '09일종료일'처럼 붙는 까닭(칸 안 줄바꿈 표기).
OpenDART document.xml(공개 원문). 키는 출력하지 않는다. 저장하지 않음."""
import io
import os
import re
import zipfile
import requests

out = []
key = os.environ.get("DART_API_KEY", "").strip()
if not key:
    out.append("DART_API_KEY 없음")
else:
    r = requests.get("https://opendart.fss.or.kr/api/document.xml", params={"crtfc_key": key, "rcept_no": "20261028000138"}, timeout=60)
    out.append(f"HTTP {r.status_code} len {len(r.content)} type {r.headers.get('content-type')}")
    try:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for name in z.namelist():
            raw = z.read(name)
            text = raw.decode("utf-8", "replace")
            out.append(f"== {name} {len(raw)} bytes")
            for word in ("분할반대의사통지 접수기간", "반대의사통지"):
                i = text.find(word)
                if i >= 0:
                    seg = text[i - 200:i + 900]
                    out.append("raw@" + word + ": " + repr(seg))
                    break
            out.append("entities: " + repr(sorted(set(re.findall(r"&[A-Za-z#0-9]+;", text)))[:20]))
            out.append("tags: " + repr(sorted(set(t.upper() for t in re.findall(r"</?([A-Za-z][A-Za-z0-9_-]*)", text)))[:60]))
    except zipfile.BadZipFile:
        out.append("not zip: " + r.text[:200])
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
