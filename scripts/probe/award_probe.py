"""probe 240: CBSA 목록에서 사건 열쇠가 겹치는 곳(운영: 읽은 사건 94 · 저장 85). 공개 페이지만, 저장 안 함."""
import collections
import sys
import time

import requests

sys.path.insert(0, "scripts/probe")
import cbsa_cases as c  # noqa: E402

OUT = []
S = requests.Session()
S.headers.update(c.HEADERS)
for list_id, kind, url in c.LISTS:
    time.sleep(2)
    try:
        cases, total = c.parse_list(S.get(url, timeout=60).text, list_id, url)
        by = collections.defaultdict(list)
        for x in cases:
            by[x["key"]].append(x)
        dup = {k: v for k, v in by.items() if len(v) > 1}
        OUT.append(f"## {kind}: 사건 {total} · 한국 {len(cases)} · 열쇠 {len(by)} · 겹친 열쇠 {len(dup)}")
        for k, v in list(dup.items())[:8]:
            OUT.append(f"   [{k}] " + " ‖ ".join(f"{x['title'][:90]} · 문서 {len(x['docs'])} · 첫 주소 {(x['docs'][0]['url'] if x['docs'] else '')[-60:]}" for x in v)[:900])
        nokey = [x for x in cases if not x["key"].count("/") >= 2]
        OUT.append(f"   주소 꼴이 안 맞아 제목으로 만든 열쇠 {len(nokey)}: " + " ‖ ".join(f"{x['key'][:50]} ← {(x['docs'][0]['url'] if x['docs'] else '없음')[-70:]}" for x in nokey[:8])[:1300])
    except Exception as e:  # noqa: BLE001
        OUT.append(f"## {kind}: 실패 {type(e).__name__} {str(e)[:100]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
