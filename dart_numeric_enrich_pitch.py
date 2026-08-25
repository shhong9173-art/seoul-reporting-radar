from __future__ import annotations

import json
import re
from pathlib import Path

PITCH = Path("pitch.json")
NUMERIC = Path("dart_numeric.json")

pitches = json.loads(PITCH.read_text(encoding="utf-8")) if PITCH.exists() else []
rows = json.loads(NUMERIC.read_text(encoding="utf-8")).get("items", []) if NUMERIC.exists() else []

def tokens(s: str) -> set[str]:
    return set(re.findall(r"[가-힣A-Za-z0-9]{2,}", str(s or "").lower()))

for pitch in pitches:
    companies = set(pitch.get("companies") or [])
    theme_tokens = tokens(" ".join(pitch.get("themes") or [])) | tokens(pitch.get("headline", ""))
    matched = []
    for row in rows:
        if row.get("corpName") not in companies:
            continue
        # Require either a shared theme word or a material numeric document.
        report_tokens = tokens(row.get("reportName", ""))
        signal = theme_tokens & report_tokens
        nums = row.get("numbers") or []
        if signal or nums:
            matched.append(row)
    matched = matched[:6]
    pitch["dartNumericSignals"] = matched
    pitch["dartNumericCount"] = sum(len(x.get("numbers") or []) for x in matched)
    if matched:
        pitch["pitchScore"] = min(100, int(pitch.get("pitchScore", 0)) + min(10, pitch["dartNumericCount"]))
        numeric_text = []
        for m in matched:
            for n in (m.get("numbers") or [])[:6]:
                numeric_text.append(n)
        pitch["dartNumbers"] = list(dict.fromkeys(numeric_text))[:15]
        pitch["whyNow"] = (pitch.get("whyNow", "") + f" DART 원문에서 {len(pitch['dartNumbers'])}개 수치 신호를 추가 확인했습니다.").strip()
        pitch.setdefault("questions", []).insert(0, "DART 원문 수치가 기사에 나온 투자·생산·계약 숫자와 일치하는지 대조")

pitches.sort(key=lambda x: x.get("pitchScore", 0), reverse=True)
PITCH.write_text(json.dumps(pitches, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"DART numeric enrichment: {sum(bool(p.get('dartNumericSignals')) for p in pitches)} pitch items linked")
