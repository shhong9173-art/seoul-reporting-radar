import json
from pathlib import Path

pitch_path = Path('pitch.json')
dart_path = Path('dart.json')

pitches = json.loads(pitch_path.read_text(encoding='utf-8')) if pitch_path.exists() else []
dart = json.loads(dart_path.read_text(encoding='utf-8')) if dart_path.exists() else {"items": []}
dart_items = dart.get('items', []) if isinstance(dart, dict) else []

for pitch in pitches:
    companies = set(pitch.get('companies') or [])
    matches = [d for d in dart_items if d.get('corpName') in companies]
    if not matches:
        pitch['dartSignals'] = []
        continue
    matches = matches[:8]
    pitch['dartSignals'] = matches
    pitch['dartDisclosureCount'] = len(matches)
    pitch['pitchScore'] = min(100, int(pitch.get('pitchScore', 0)) + min(8, len(matches) * 2))
    pitch['whyNow'] = (pitch.get('whyNow', '') + f' 최근 30일 DART 관련 공시 {len(matches)}건도 확인됩니다.').strip()
    questions = pitch.setdefault('questions', [])
    questions.insert(0, '최근 DART 공시의 투자·출자·생산·계약 내용을 원문과 대조해 숫자와 조건을 확인')

pitches.sort(key=lambda x: x.get('pitchScore', 0), reverse=True)
pitch_path.write_text(json.dumps(pitches, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f'DART enrichment: {len(pitches)} pitch items processed; {sum(1 for p in pitches if p.get("dartSignals"))} linked')
