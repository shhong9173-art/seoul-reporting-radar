"""Probe 97b: EUIPO 토큰 요청을 공개 꾸러미(euipo-tm-client)와 같은 형식으로 한 번. 꾸러미의 토큰 요청 코드 부분만 출력하고,
토큰이 나오면 상표 검색을 한 번(현대자동차 출원 5건, 건수·필드 이름만). 키·토큰 값은 남기지 않는다."""
import glob
import os
import re
import subprocess
import zipfile
import tarfile

import requests

out = []
CID = os.environ.get("EUIPO_CLIENT_ID", "").strip()
SEC = os.environ.get("EUIPO_CLIENT_SECRET", "").strip()
d = "/tmp/euipo_pkg"
os.makedirs(d, exist_ok=True)
subprocess.run(["python", "-m", "pip", "download", "--no-deps", "euipo-tm-client", "-d", d], capture_output=True, text=True)
for f in glob.glob(d + "/*"):
    if f.endswith(".whl"):
        zipfile.ZipFile(f).extractall(d + "/x")
    elif f.endswith(".tar.gz"):
        tarfile.open(f).extractall(d + "/x")
for f in glob.glob(d + "/x/**/*.py", recursive=True):
    t = open(f, encoding="utf-8", errors="replace").read()
    i = t.find('"grant_type"')
    if i >= 0:
        out.append(f"code {os.path.basename(f)}: " + re.sub(r"\s+", " ", t[max(0, i - 500):i + 400]))
    j = t.find("trademarks")
    if j >= 0 and "def search" in t:
        k = t.find("def search")
        out.append(f"search {os.path.basename(f)}: " + re.sub(r"\s+", " ", t[k:k + 700]))
try:
    rr = requests.post("https://auth.euipo.europa.eu/oidc/accessToken", data={"grant_type": "client_credentials", "scope": "uid"},
                       auth=(CID, SEC), headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=40)
    ct = rr.headers.get("content-type", "")
    out.append(f"token basic-auth HTTP {rr.status_code} ctype {ct[:40]} " + (f"keys {sorted(rr.json().keys())}" if ct.startswith("application/json") else re.sub(r"\s+", " ", rr.text[:200])))
    tok = rr.json().get("access_token") if ct.startswith("application/json") else None
    if tok:
        q = 'applicants.name=="*Hyundai Motor*"'
        sr = requests.get("https://api.euipo.europa.eu/trademark-search/trademarks", params={"query": q, "size": 5, "sort": "applicationDate:desc"},
                          headers={"Authorization": f"Bearer {tok}", "X-IBM-Client-Id": CID, "Accept": "application/json"}, timeout=40)
        sct = sr.headers.get("content-type", "")
        if sct.startswith("application/json"):
            j = sr.json()
            items = j.get("trademarks") or j.get("content") or []
            out.append(f"search HTTP {sr.status_code} keys {sorted(j.keys())[:12]} items {len(items)} total {j.get('totalElements')}")
            if items:
                out.append("  fields " + ", ".join(sorted(items[0].keys()))[:600])
        else:
            out.append(f"search HTTP {sr.status_code} " + re.sub(r"\s+", " ", sr.text[:200]))
except Exception as e:  # noqa: BLE001
    out.append(f"token {type(e).__name__} {str(e)[:100]}")
text = "\n".join(out)
for v in (CID, SEC):
    if v:
        text = text.replace(v, "<X>")
text = re.sub(r"eyJ[A-Za-z0-9_\-\.]{20,}", "<TOKEN>", text)
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
