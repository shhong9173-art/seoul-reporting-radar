"""Probe 42: 미국 노동부 API(OSHA) — 데이터셋 목록, 점검·위반·사고 필드 이름, 출입처 미국 법인 이름 패턴별 점검 건수·최근 개시일.
키·사업장 이름·주소는 출력하지 않는다(건수·필드·날짜만)."""
import json
import os
import time
import requests

KEY = os.environ.get("DOL_API_KEY", "").strip()
B = "https://apiprod.dol.gov/v4"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = [f"key set={bool(KEY)} len={len(KEY)}"]


def scrub(t):
    return t.replace(KEY, "<KEY>") if KEY else t


def get(path, **params):
    try:
        r = requests.get(B + path, params={**params, **({"X-API-KEY": KEY} if KEY else {})}, headers=H, timeout=60)
        return r
    except Exception as e:  # noqa: BLE001
        out.append(f"{path}: {type(e).__name__} {scrub(str(e))[:100]}")
        return None


r = get("/datasets")
if r is not None:
    try:
        j = r.json()
        ds = j.get("datasets") or j.get("data") or j
        osha = [d for d in (ds if isinstance(ds, list) else []) if "OSHA" in json.dumps(d)[:400]]
        out.append(f"datasets HTTP {r.status_code} total={len(ds) if isinstance(ds, list) else type(ds).__name__} osha={len(osha)}")
        for d in osha[:20]:
            out.append("   " + json.dumps({k: d.get(k) for k in ("name", "api_url", "agency", "frequency", "last_updated", "modified") if k in d}, ensure_ascii=False)[:220])
        if not osha and isinstance(ds, list) and ds:
            out.append("   sample keys " + str(sorted(ds[0])[:20]))
    except ValueError:
        out.append(f"datasets HTTP {r.status_code} non-JSON {scrub(r.text[:200])!r}")
time.sleep(1)
for ep in ("inspection", "violation", "accident", "accident_injury"):
    r = get(f"/get/OSHA/{ep}/json/metadata")
    if r is None:
        continue
    try:
        m = r.json()
        fields = [f.get("short_name") or f.get("name") or f.get("field") for f in (m if isinstance(m, list) else m.get("fields") or m.get("data") or [])] if not isinstance(m, dict) or "fields" in m or "data" in m else list(m)[:40]
        out.append(f"meta {ep}: HTTP {r.status_code} n={len(fields)} fields={fields[:45]}")
    except ValueError:
        out.append(f"meta {ep}: HTTP {r.status_code} head={scrub(r.text[:200])!r}")
    time.sleep(1)
# 최근 점검: 정렬·날짜 필드 확인
r = get("/get/OSHA/inspection/json", limit=3, sort="desc", sort_by="open_date")
if r is not None:
    try:
        j = r.json()
        rows = j.get("data") if isinstance(j, dict) else j
        out.append(f"inspection latest: HTTP {r.status_code} top-keys={list(j)[:6] if isinstance(j, dict) else 'list'} n={len(rows or [])} open_dates={[x.get('open_date') for x in rows or []]} load_dt={[x.get('load_dt') for x in rows or []][:1]}")
    except ValueError:
        out.append(f"inspection latest: HTTP {r.status_code} head={scrub(r.text[:300])!r}")
time.sleep(1)
for pat in ("%HYUNDAI%", "%KIA %", "%MOBIS%", "%MANDO%", "%HANWHA%", "%QCELLS%", "%HANKOOK%", "%KUMHO%", "%SEAH%", "%POSCO%", "%LS CABLE%",
            "%SUPERIOR ESSEX%", "%TAIHAN%", "%DOOSAN%", "%HYOSUNG%", "%HYUNDAI POWER%", "%KOREA ZINC%", "%WIA%"):
    f = json.dumps({"and": [{"field": "estab_name", "operator": "like", "value": pat}, {"field": "open_date", "operator": "gt", "value": "2024-01-01"}]})
    r = get("/get/OSHA/inspection/json", limit=500, sort="desc", sort_by="open_date", filter_object=f, fields="activity_nr,estab_name,open_date,site_state,insp_type,close_case_date")
    if r is None:
        continue
    try:
        j = r.json()
        rows = (j.get("data") if isinstance(j, dict) else j) or []
        dates = sorted(x.get("open_date") or "" for x in rows)
        out.append(f"{pat}: HTTP {r.status_code} n={len(rows)} names={len({x.get('estab_name') for x in rows})} states={sorted({x.get('site_state') for x in rows})[:8]} latest={dates[-1:] } types={sorted({x.get('insp_type') for x in rows})}")
    except ValueError:
        out.append(f"{pat}: HTTP {r.status_code} head={scrub(r.text[:200])!r}")
    time.sleep(0.7)
open("/tmp/probe_out.txt", "w").write("\n".join(out))
