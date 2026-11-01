"""Probe 81: 정책브리핑 보도자료 목록(korea.kr/briefing/pressReleaseList.do, robots 허용) — 부처 거르기 칸 이름·값(기후에너지환경부·공정위·산업통상부),
목록 행 형식(제목·부처·날짜·newsId) 확인. 공개 목록 제목만 몇 줄, 한 번(+거르기 시험 한 번)."""
import re

import requests

H = {"User-Agent": "newsroom-official-research/1.0 (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
r = requests.get("https://www.korea.kr/briefing/pressReleaseList.do", headers=H, timeout=30)
t = r.text
out.append(f"list HTTP {r.status_code} len {len(t)}")
for m in re.finditer(r'<input[^>]*(?:기후에너지환경부|공정거래위원회|산업통상부)[^>]*>|<input[^>]*value="[^"]*"[^>]*>\s*<label[^>]*>\s*(?:기후에너지환경부|공정거래위원회|산업통상부)', t):
    out.append("  input " + re.sub(r"\s+", " ", m.group(0))[:220])
for lab in ("기후에너지환경부", "공정거래위원회", "산업통상부"):
    i = t.find(lab)
    out.append(f"  ctx {lab}: " + re.sub(r"\s+", " ", t[max(0, i - 260):i + 40]) if i >= 0 else f"  {lab} not found")
names = sorted(set(re.findall(r'name="([A-Za-z_]+)"', t)))
out.append(f"  field names {names[:40]}")
items = re.findall(r'pressReleaseView\.do\?newsId=(\d+)', t)
out.append(f"  newsIds {len(items)} {items[:3]}")
li = t.find("pressReleaseView.do?newsId=")
out.append("  row html " + re.sub(r"\s+", " ", t[max(0, li - 200):li + 900])[:1100])
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
