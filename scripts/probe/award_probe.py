"""Probe 90: 전남광주통합특별시 임시 누리집(jeonnam-gwangju.go.kr) 보도자료 게시판 찾기·robots, 경북 보도자료 목록 형식(공개, 한 번씩)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
for home in ("https://www.jeonnam-gwangju.go.kr", "https://jeonnam-gwangju.go.kr"):
    try:
        rb = requests.get(home + "/robots.txt", headers=H, timeout=25)
        out.append(f"jg robots {home} HTTP {rb.status_code}: " + re.sub(r"\s+", " ", rb.text[:200]))
        r = requests.get(home, headers=H, timeout=25)
        press = sorted(set(m.group(1) for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:<[^>]+>\s*)*보도', r.text)))[:6]
        out.append(f"jg home {home} HTTP {r.status_code} final {r.url[:80]} len {len(r.text)} press {press}")
        break
    except Exception as e:  # noqa: BLE001
        out.append(f"jg {home} {type(e).__name__} {str(e)[:60]}")
try:
    r = requests.get("https://www.gb.go.kr/page/10107/10004.do", headers=H, timeout=30)
    t = r.text
    i = t.find("/page/10107/10004.do?")
    k = [m.start() for m in re.finditer(r"2026-10-30", t)]
    out.append(f"gb HTTP {r.status_code} len {len(t)} view-links {len(re.findall(r'10004[.]do[?][^\"]*', t))}")
    if k:
        out.append("  ctx " + re.sub(r"\s+", " ", t[max(0, k[0] - 700):k[0] + 80]))
except Exception as e:  # noqa: BLE001
    out.append(f"gb {type(e).__name__}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
