"""Probe 87: 출입처 공장 시·도 보도자료(투자협약 발표가 먼저 나오는 곳) — 울산·전남·충남·경북·경남 누리집이 GitHub에서 열리는지,
robots.txt, 첫 화면의 RSS·보도자료 링크(공개, 사이트당 두 번)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for name, home in [("울산", "https://www.ulsan.go.kr"), ("전남", "https://www.jeonnam.go.kr"), ("충남", "https://www.chungnam.go.kr"),
                   ("경북", "https://www.gb.go.kr"), ("경남", "https://www.gyeongnam.go.kr")]:
    try:
        rb = requests.get(home + "/robots.txt", headers=H, timeout=25)
        out.append(f"{name} robots HTTP {rb.status_code}: " + re.sub(r"\s+", " ", rb.text[:200]))
    except Exception as e:  # noqa: BLE001
        out.append(f"{name} robots {type(e).__name__}")
    try:
        r = requests.get(home, headers=H, timeout=25)
        links = sorted(set(re.findall(r'href="([^"]*(?:rss|RSS|Rss)[^"]*)"', r.text)))[:6]
        press = sorted(set(m.group(1) for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*보도자료', r.text)))[:4]
        out.append(f"{name} home HTTP {r.status_code} len {len(r.text)} rss {links} press {press}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{name} home {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
