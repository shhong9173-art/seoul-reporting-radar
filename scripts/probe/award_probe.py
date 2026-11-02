"""Probe 97c: EUIPO 운영 토큰 주소가 GitHub 러너에서 502만 주는 원인 가르기 — 운영 auth 호스트 GET, 시험(sandbox) 토큰 주소 POST(운영 키라 401이 정상),
운영 API 호스트 GET 각 한 번. 응답 코드·서버 머리글만."""
import os
import re

import requests

CID = os.environ.get("EUIPO_CLIENT_ID", "").strip()
SEC = os.environ.get("EUIPO_CLIENT_SECRET", "").strip()
out = []
for method, url, kw in [("GET", "https://auth.euipo.europa.eu/oidc/.well-known/openid-configuration", {}),
                        ("POST", "https://auth-sandbox.euipo.europa.eu/oidc/accessToken", {"data": {"grant_type": "client_credentials", "client_id": CID, "client_secret": SEC, "scope": "uid"}}),
                        ("GET", "https://api.euipo.europa.eu/trademark-search/trademarks", {"params": {"size": 10}}),
                        ("POST", "https://auth.euipo.europa.eu/oidc/accessToken", {"data": {"grant_type": "client_credentials", "client_id": CID, "client_secret": SEC, "scope": "uid"}})]:
    try:
        r = requests.request(method, url, timeout=40, headers={"Content-Type": "application/x-www-form-urlencoded"} if method == "POST" else {}, **kw)
        hdr = {k: v for k, v in r.headers.items() if k.lower() in ("server", "via", "x-cache", "cf-ray", "x-global-transaction-id", "content-type", "x-akamai-transformed", "x-request-id")}
        body = r.text
        for v in (CID, SEC):
            if v:
                body = body.replace(v, "<X>")
        out.append(f"{method} {url} -> HTTP {r.status_code} hdr {hdr} body {re.sub(r'\\s+', ' ', body[:160])}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{method} {url} {type(e).__name__} {str(e)[:100]}")
text = "\n".join(out)
for v in (CID, SEC):
    if v:
        text = text.replace(v, "<X>")
open("/tmp/probe_out.txt", "w").write(text)
print(text[:600])
