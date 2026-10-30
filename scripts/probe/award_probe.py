"""probe: CleanSYS 실시간 측정(rltmMesureResult) 응답 칸 전부·배출허용기준 칸·기준 초과 행(공개 자료). 키 값은 출력하지 않는다. 호출 3회."""
import json
import os
import re

import requests

KEY = (os.environ.get("DATA_GO_KR_KEY") or os.environ.get("KR_FUEL_API_KEY") or "").strip()
API = "https://apis.data.go.kr/B552584/cleansys/rltmMesureResult"
out = []
P = ("tsp", "sox", "nox", "hcl", "hf", "nh3", "co")


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


for term in ("영풍", "현대제철", "고려아연"):
    try:
        r = requests.get(API, params={"serviceKey": KEY, "type": "json", "numOfRows": 1000, "pageNo": 1, "factManageNm": term}, timeout=60)
        d = json.loads(r.text)
        items = ((d.get("response") or {}).get("body") or {}).get("items") or []
        out.append(f"== {term} HTTP {r.status_code} items {len(items)}")
        if items:
            out.append("keys " + ", ".join(sorted(items[0].keys())))
            out.append("row0 " + json.dumps({k: v for k, v in items[0].items()}, ensure_ascii=False)[:900])
            nonnull = {}
            for x in items:
                for k, v in x.items():
                    if v not in (None, "", "-"):
                        nonnull[k] = nonnull.get(k, 0) + 1
            out.append("nonnull " + json.dumps(nonnull, ensure_ascii=False))
            vals = {}
            for x in items:
                for k, v in x.items():
                    if not re.search(r"_(mesure_value|stdr_value)$", k) and k not in ("fact_manage_nm", "stack_code", "area_nm", "mesure_dt"):
                        vals.setdefault(k, set()).add(str(v)[:20])
            out.append("other-values " + json.dumps({k: sorted(v)[:8] for k, v in vals.items()}, ensure_ascii=False))
            exc = []
            for x in items:
                for p in P:
                    m, s = num(x.get(f"{p}_mesure_value")), num(x.get(f"{p}_exhst_perm_stdr_value"))
                    if m is not None and s and m > s:
                        exc.append(f"{x.get('fact_manage_nm')} #{x.get('stack_code')} {p} {m}>{s} @{x.get('mesure_dt')}")
            out.append(f"exceed {len(exc)}: " + " | ".join(exc[:10]))
            near = sorted(((num(x.get(f'{p}_mesure_value')) or 0) / (num(x.get(f'{p}_exhst_perm_stdr_value')) or 1e9), p, x.get('fact_manage_nm'), x.get('stack_code'))
                          for x in items for p in P if num(x.get(f"{p}_exhst_perm_stdr_value")))
            out.append("top ratios " + "; ".join(f"{a:.2f} {p} {n} #{c}" for a, p, n, c in near[-6:]))
    except Exception as e:  # noqa: BLE001
        out.append(f"ERR {term} {type(e).__name__} {str(e)[:120]}".replace(KEY, "***") if KEY else f"ERR {term} {type(e).__name__}")
blob = "\n".join(out).replace(KEY, "***") if KEY else "\n".join(out)
open("/tmp/probe_out.txt", "w").write(blob)
print("total chars", len(blob))
