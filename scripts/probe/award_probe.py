"""Probe 83: (1) 정책브리핑 보도자료 목록 repCodeType=A&repCode=A00019(기후에너지환경부) 원본 행 HTML 한 줄,
(2) 산업부 '2026년 10월 수출입 동향'(172360) 본문 중 품목 표 부분 — 10월 표 해석 실패 원인(공개 보도자료, 한 번씩)."""
import html
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
r = requests.get("https://www.korea.kr/briefing/pressReleaseList.do", params={"repCodeType": "A", "repCode": "A00019"}, headers=H, timeout=30)
t = r.text
i = t.find("pressReleaseView.do?newsId=")
out.append(f"korea filtered HTTP {r.status_code} ids {len(re.findall(r'pressReleaseView[.]do[?]newsId=', t))}")
out.append("  row " + re.sub(r"\s+", " ", t[max(0, i - 150):i + 700]))
r = requests.get("https://www.motir.go.kr/kor/article/ATCL3f49a5a8c/172360/view", headers=H, timeout=40)
body = re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", r.text)))
out.append(f"motir 172360 HTTP {r.status_code} len {len(body)}")
for pat in [r"\*\s*\d{1,2}월\s*수출", r"주요\s*품목별\s*수출액", r"자동차\(", r"석유화학"]:
    m = re.search(pat, body)
    out.append(f"  [{pat}] " + (body[max(0, m.start() - 80):m.start() + 700] if m else "없음"))
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
