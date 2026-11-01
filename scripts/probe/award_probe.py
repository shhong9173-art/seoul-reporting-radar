"""Probe 73: registry spellings of the new petrochemical/refining beats (11-01) in three public sources —
CleanSYS stack TMS, NPS workplace list, factory registration. Prints names as the registries write them
(public facility/company names) and counts; no keys."""
import collections
import os
import sys
import time

sys.path.insert(0, "scripts")
import kr_stack_watch as stacks  # noqa: E402
import kr_workforce_watch as wf  # noqa: E402
import kr_official_watch as off  # noqa: E402

KEY = (os.environ.get("DATA_GO_KR_KEY") or "").strip()
TERMS = ["엘지화학", "LG화학", "롯데케미칼", "금호석유화학", "에쓰-오일", "에쓰오일", "에스오일", "S-OIL",
         "현대오일뱅크", "에이치디현대오일뱅크", "HD현대오일뱅크", "에스케이이노베이션", "SK이노베이션"]
out = [f"key length {len(KEY)}"]

out.append("\n== CleanSYS (굴뚝)")
for t in TERMS:
    try:
        rows = stacks.fetch(t, KEY, sleep=time.sleep)
        names = collections.Counter(str(x.get("fact_manage_nm") or "").strip() for x in rows)
        out.append(f"{t}: {len(rows)} rows · " + " | ".join(f"{n}({c},{next((x.get('area_nm') for x in rows if x.get('fact_manage_nm') == n), '')})" for n, c in names.most_common(12)))
    except Exception as e:  # noqa: BLE001
        out.append(f"{t}: {type(e).__name__} {str(e)[:80]}")
    time.sleep(0.5)

out.append("\n== NPS (국민연금 사업장)")
api = wf.Api(KEY)
for t in TERMS:
    try:
        _, items = api.call("getBassInfoSearchV2", {"wkplNm": t}, page=1)
        names = collections.Counter(f"{str(x.get('wkplNm') or '').strip()}[{str(x.get('wkplRoadNmDtlAddr') or x.get('ldongAddrMgplDgCd') or '')[:12]}]" for x in items)
        out.append(f"{t}: {len(items)} rows · " + " | ".join(n for n, _ in names.most_common(10)))
    except Exception as e:  # noqa: BLE001
        out.append(f"{t}: {type(e).__name__} {str(e)[:80]}")
    time.sleep(0.5)

out.append("\n== 공장등록")
for t in ["엘지화학", "LG화학", "롯데케미칼", "금호석유화학", "에쓰-오일", "에쓰오일", "현대오일뱅크", "에이치디현대오일뱅크", "HD현대오일뱅크"]:
    try:
        text, err = off.call(off.FACTORY_API, {"serviceKey": KEY, "pageNo": 1, "numOfRows": 50, "type": "json", "cmpnyNm": t})
        if err:
            out.append(f"{t}: {err}")
            continue
        code, total, items = off.parse_factories(text)
        names = collections.Counter(f"{x['cmpnyNm']}[{x['rnAdres'][:14]}]" for x in items)
        out.append(f"{t}: total {total} · " + " | ".join(n for n, _ in names.most_common(10)))
    except Exception as e:  # noqa: BLE001
        out.append(f"{t}: {type(e).__name__} {str(e)[:120]}")
    time.sleep(0.5)

open("/tmp/probe_out.txt", "w").write("\n".join(out))
print("\n".join(out)[:600])
