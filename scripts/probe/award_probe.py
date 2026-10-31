"""Probe 52: 무공해차 통합누리집(ev.or.kr) — robots.txt, 첫 화면의 보조금·차종 관련 .do 경로 목록만(내용은 찍지 않음)."""
import re
import time
import requests

H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for url in ("https://ev.or.kr/robots.txt", "https://ev.or.kr/", "https://ev.or.kr/nportal/main.do"):
    time.sleep(3)
    try:
        r = requests.get(url, headers=H, timeout=40)
    except Exception as e:  # noqa: BLE001
        out.append(f"{url}: {type(e).__name__}")
        continue
    if url.endswith("robots.txt"):
        out.append(f"robots HTTP {r.status_code}: {r.text[:400]!r}")
        continue
    paths = sorted(set(re.findall(r"""['"(](/nportal/[A-Za-z0-9_/]+\.do)""", r.text)))
    out.append(f"{url}: HTTP {r.status_code} final={r.url} len={len(r.text)} .do paths={len(paths)}")
    for p in paths:
        if re.search(r"(?i)supprt|subsid|car|price|model|vhcl|buy", p):
            out.append("   " + p)
open("/tmp/probe_out.txt", "w").write("\n".join(out))
