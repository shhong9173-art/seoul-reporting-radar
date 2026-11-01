"""Probe 84: 산업부 '2026년 10월 수출입 동향'(172360) 본문 — 총 수출·수입 문장과 자동차 문장 형식(공개 보도자료, 한 번)."""
import html
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
r = requests.get("https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172360/view", headers=H, timeout=40)
body = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", r.text)))
out.append(f"HTTP {r.status_code} len {len(body)}")
for pat in [r"수입\s*[\d,.]+\s*억", r"무역\s*수지|수지\s*[\d,.]+", r"자동차\s*\(", r"자동차부품\s*\(", r"철강\s*\(", r"석유제품\s*\("]:
    for m in list(re.finditer(pat, body))[:2]:
        out.append(f"  [{pat}] ..." + body[max(0, m.start() - 160):m.start() + 160])
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
