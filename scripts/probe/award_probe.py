"""격리 탐침 31i: 국민연금 공사 현장 상세 — 기아 'LW 프로젝트'·KGM커머셜 '적층 2공정'·현대차 '0-프로젝트'·태광 'N-PJT' 등 현장 적용일·가입자(키 값 미출력)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kr_workforce_watch as w  # noqa: E402

api = w.Api((os.environ.get("KR_FUEL_API_KEY") or "").strip())
out = []
for term in ("LW 프로젝트", "LW프로젝트", "적층 2공정", "0-프로젝트", "O-프로젝트", "N-PJT", "GS칼텍스 프로젝트", "유틸리티설비 증설"):
    try:
        total, items = api.call("getBassInfoSearchV2", {"wkplNm": term})
    except w.ApiError as e:
        out.append(f"{term}: {e}")
        continue
    latest = max((x["dataCrtYm"] for x in items), default=None)
    months = sorted({x["dataCrtYm"] for x in items})
    cur = [x for x in items if x["dataCrtYm"] == latest]
    rows = []
    adpts = []
    for x in cur[:40]:
        try:
            _, d = api.call("getDetailInfoSearchV2", {"seq": x["seq"]}, rows=1)
        except w.ApiError:
            continue
        d0 = d[0] if d else {}
        adpts.append(d0.get("adptDt") or "")
        rows.append((d0.get("adptDt"), d0.get("jnngpCnt"), x["wkplNm"][:70], w.region_of(x), (x.get("wkplRoadNmDtlAddr") or "")[:25]))
    rows.sort()
    members = sum((r[1] or 0) for r in rows)
    out.append(f"{term}: 전체 {total}줄 · 달 {months[:1]}~{months[-1:]} · 최신 {latest} {len(cur)}곳 · 가입자 합 {members} · 적용 첫 {min(adpts) if adpts else None} 끝 {max(adpts) if adpts else None} · 예 {rows[:4]}")
blob = " ¶ ".join(x.replace("\n", " ").replace("::", ": :").replace("%", "pct") for x in out)
for i in range(0, min(len(blob), 13000), 1300):
    print(f"::notice title=aw-{i // 1300:02d}::{blob[i:i + 1300]}")
