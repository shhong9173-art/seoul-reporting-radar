"""Probe 97: EUIPO 상표 검색 API — (1) 공개 클라이언트 꾸러미(euipo-tm-client)에서 운영·시험 주소 확인, (2) 공유 비밀(EUIPO_CLIENT_ID/SECRET)이
들어갔는지(길이만), (3) 운영 토큰 발급 응답 코드만. 키·토큰 값은 남기지 않는다."""
import glob
import os
import re
import subprocess
import tarfile
import zipfile

import requests

out = []
CID = os.environ.get("EUIPO_CLIENT_ID", "").strip()
SEC = os.environ.get("EUIPO_CLIENT_SECRET", "").strip()
out.append(f"secrets: id length {len(CID)} · secret length {len(SEC)}")
d = "/tmp/euipo_pkg"
os.makedirs(d, exist_ok=True)
r = subprocess.run(["python", "-m", "pip", "download", "--no-deps", "euipo-tm-client", "-d", d], capture_output=True, text=True)
out.append("pip " + ("ok" if r.returncode == 0 else r.stderr[-200:]))
for f in glob.glob(d + "/*"):
    if f.endswith(".whl"):
        zipfile.ZipFile(f).extractall(d + "/x")
    elif f.endswith(".tar.gz"):
        tarfile.open(f).extractall(d + "/x")
urls = set()
for f in glob.glob(d + "/x/**/*.py", recursive=True):
    t = open(f, encoding="utf-8", errors="replace").read()
    urls.update(re.findall(r"https://[A-Za-z0-9.\-/_{}]+", t))
    for m in re.finditer(r"(token|scope|grant_type|X-IBM|headers)[^\n]{0,120}", t):
        out.append("  ctx " + m.group(0)[:140])
out.append("urls " + ", ".join(sorted(urls))[:900])
prod = sorted(u for u in urls if "euipo" in u and "sandbox" not in u)
tok = [u for u in prod if "token" in u or "auth" in u]
out.append(f"token candidates {tok[:4]}")
for u in tok[:2]:
    try:
        rr = requests.post(u, data={"grant_type": "client_credentials", "client_id": CID, "client_secret": SEC, "scope": "uid"}, timeout=40)
        body = rr.text
        for v in (CID, SEC):
            if v:
                body = body.replace(v, "<X>")
        ct = rr.headers.get("content-type", "")
        out.append(f"POST {u} -> HTTP {rr.status_code} " + (f"keys {sorted(rr.json().keys())}" if ct.startswith("application/json") else re.sub(r"\s+", " ", body[:160])))
    except Exception as e:  # noqa: BLE001
        out.append(f"POST {u} {type(e).__name__} {str(e)[:80]}")
text = "\n".join(out)
for v in (CID, SEC):
    if v:
        text = text.replace(v, "<X>")
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
