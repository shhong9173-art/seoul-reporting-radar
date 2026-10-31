"""Probe 25: EDIS 새 화면에서 'API' 안내 주소와 키 발급 경로 찾기(공개 쪽 HTML·JS에서 경로 문자열만). 비밀값은 쓰지 않음. 저장하지 않음."""
import re
import requests

out = []
UA = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
s = requests.Session()
r = s.get("https://edis.usitc.gov/", headers=UA, timeout=60)
out.append(f"home HTTP {r.status_code} len={len(r.text)}")
scripts = re.findall(r'<script[^>]+src="([^"]+)"', r.text)
out.append("scripts: " + repr(scripts[:12]))
hrefs = sorted(set(re.findall(r'href="([^"]+)"', r.text)))
out.append("hrefs: " + repr([h for h in hrefs if not h.endswith((".css", ".ico", ".png"))][:40]))
found = set()
for src in scripts[:12]:
    u = src if src.startswith("http") else "https://edis.usitc.gov" + ("" if src.startswith("/") else "/") + src
    try:
        t = s.get(u, headers=UA, timeout=60).text
    except Exception as e:  # noqa: BLE001
        out.append(f"js {u}: {type(e).__name__}")
        continue
    for m in re.findall(r'["\'`](/?(?:data|api|external|edis)[A-Za-z0-9/_\-{}.:$?=&]*(?:secret|key|token|auth|login|api)[A-Za-z0-9/_\-{}.:$?=&]*)["\'`]', t, re.I):
        found.add(m)
    for m in re.findall(r'["\'`](https?://[^"\'`\s]*(?:api|swagger|doc)[^"\'`\s]*)["\'`]', t, re.I):
        found.add(m)
out.append("paths with key/token/auth/api: " + repr(sorted(found)[:60]))
for path in ("/data/api", "/api", "/data/swagger-ui.html", "/data/v3/api-docs", "/external/api", "/data/secretKey"):
    try:
        x = s.get("https://edis.usitc.gov" + path, headers=UA, timeout=30, allow_redirects=False)
        out.append(f"GET {path}: {x.status_code} {x.headers.get('content-type')} {x.headers.get('location', '')} {re.sub(r'\s+', ' ', x.text[:160])}")
    except Exception as e:  # noqa: BLE001
        out.append(f"GET {path}: {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:300])
