"""격리 탐침 17: NHTSA 결함조사(ODI) 파일 — 최근 120일 출입처 브랜드 조사와 조사 원문 링크 형식. 공개 자료만."""
import datetime as dt
import sys
import time

import requests

sys.path.insert(0, "scripts")
import nhtsa_investigations as n

out = []
t0 = time.time()
raw = n.fetch_zip()
data = n.parse_zip_data(raw, lookback=120)
out.append(f"zip={len(raw)} scanned={data['scannedRecords']} items={len(data['items'])} secs={time.time()-t0:.0f}")
for x in data["items"][:25]:
    models = sorted({f"{v['make']} {v['model']} {v['modelYear']}" for v in x["vehicles"]})[:4]
    out.append(f"{x['actionNumber']} open={x['openedDate']} close={x['closedDate']} ref={x['longRunningOpenReferenceOnly']} type={x['discoveryType'][-20:]} "
               f"owner={x['coveredIssuerRelation'][:12]} comp={x['component'][:40]} subj={x['subject'][:80]} models={models} camp={x['recallCampaigns'][:2]}")
act = next((x["actionNumber"] for x in data["items"] if not x["longRunningOpenReferenceOnly"]), None)
if act:
    for label, url in [("page", f"https://www.nhtsa.gov/recalls?nhtsaId={act}"),
                       ("issues", f"https://api.nhtsa.gov/safetyIssues/byNhtsaId?nhtsaId={act}"),
                       ("inv api", f"https://api.nhtsa.gov/investigations?nhtsaId={act}")]:
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "seoul-reporting-radar"})
            out.append(f"{label} {act}: HTTP {r.status_code} len={len(r.text)} head={r.text[:300]!r}")
        except Exception as e:  # noqa: BLE001
            out.append(f"{label}: EXC {type(e).__name__}")

packs, cur = [], ""
for s in out:
    s = s.replace("\n", " ").replace("::", ": :").replace("%", "pct")
    if len(cur) + len(s) + 3 > 3800:
        packs.append(cur); cur = ""
    cur += (" | " if cur else "") + s
packs.append(cur)
for i, p in enumerate(packs[:10]):
    print(f"::notice title=aw-{i:02d}::{p}")
