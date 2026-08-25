from __future__ import annotations
import json
from pathlib import Path

DATA=Path('data.json')
DATA_JS=Path('data.js')
IND=Path('industry.json')
if not DATA.exists() or not IND.exists():
    raise SystemExit('data.json or industry.json missing')
base=json.loads(DATA.read_text(encoding='utf-8'))
ind=json.loads(IND.read_text(encoding='utf-8')).get('items',[])

# Keep automotive from the main collector authoritative; add non-automotive industrial desk items.
merged=list(base)
seen={(x.get('sourceName'),x.get('title')) for x in base}
for x in ind:
    sig=(x.get('sourceName'),x.get('title'))
    if sig in seen:
        continue
    # Normalize industrial records so they satisfy the common feed contract.
    x.setdefault('score', min(99, 50 + int(x.get('signalCount') or 0) * 5))
    x.setdefault('priority', 'follow' if int(x.get('signalCount') or 0) >= 2 else 'normal')
    x.setdefault('tags', [x.get('category','산업')])
    x.setdefault('companies', [])
    x.setdefault('global', False)
    x.setdefault('summary', '')
    x.setdefault('pitchScore', x.get('score', 50))
    x.setdefault('pitchReasons', ['산업부 출입처 확대 레이더에서 확인'])
    merged.append(x)
    seen.add(sig)
merged.sort(key=lambda x:x.get('published',''), reverse=True)
DATA.write_text(json.dumps(merged,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
DATA_JS.write_text('window.ITEMS = '+json.dumps(merged,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
print(f'merged industrial radar: +{len(merged)-len(base)} / total {len(merged)}')
