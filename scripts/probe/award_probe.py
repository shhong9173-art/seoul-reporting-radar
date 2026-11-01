"""Probe 75: 나주시 새올 고시·공고 목록(LG화학 나주공장 시) — GitHub 러너에서 열리는지, 줄 수·최근 제목 몇 줄(공개 공고).
운영 지자체 감시와 같은 코드(main의 kr_local_notice_watch 복사본)로 읽는다. 한 번만."""
import sys
import time

sys.path.insert(0, "scripts/probe")
import klnw_main as w  # noqa: E402
import requests  # noqa: E402

out = []
for city, base in [("나주시", "https://eminwon.naju.go.kr")]:
    t0 = time.time()
    try:
        rows, note = w.fetch_city(city, base, requests.post, time.sleep)
        out.append(f"{city}: {len(rows)}줄 · {time.time() - t0:.1f}초 · note {note}")
        for r in rows[:6]:
            out.append(f"  {r.get('date')} | {r.get('title', '')[:60]} | 분류 {w.classify(r.get('title', ''))}")
    except Exception as e:  # noqa: BLE001
        out.append(f"{city}: {type(e).__name__} {str(e)[:120]} · {time.time() - t0:.1f}초")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
