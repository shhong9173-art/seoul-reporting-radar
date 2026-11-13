"""probe 229: Signa 검색의 새 옵션(11-14 답장) — phrase 맞춤, owner_id 목록, filing_bases, offices, updated_at, /v1/offices.
공개 로그에는 건수·필드 이름·시각만(상표 이름·출원인 이름은 찍지 않는다). 검색 4번 = 40크레딧."""
import collections
import datetime as dt
import os
import re

import requests

KEY = os.environ.get("SIGNA_API_KEY", "").strip()
OUT = []
H = {"Authorization": f"Bearer {KEY}", "Accept": "application/json", "User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"}
SINCE = (dt.date.today() - dt.timedelta(days=120)).isoformat()
RECENT = (dt.date.today() - dt.timedelta(days=4)).isoformat()


def credit_headers(r):
    return {k: v for k, v in r.headers.items() if re.search(r"credit|ratelimit|rate-limit", k, re.I)}


def search(label, **params):
    r = requests.get("https://api.signa.so/v1/trademarks", params=params, headers=H, timeout=60)
    OUT.append(f"## {label}: HTTP {r.status_code} · 머리글 {credit_headers(r)}")
    if r.status_code != 200:
        OUT.append("   본문 앞: " + re.sub(r"\s+", " ", r.text)[:200])
        return []
    b = r.json() or {}
    rows = b.get("data") or []
    OUT.append(f"   최상위 {sorted(b.keys())} · 줄 {len(rows)} · has_more {b.get('has_more')} · pagination {sorted((b.get('pagination') or {}).keys())} total {(b.get('pagination') or {}).get('total_count')}")
    if rows:
        keys = collections.Counter(k for x in rows for k in x.keys())
        OUT.append("   줄 필드: " + ", ".join(f"{k}({n})" for k, n in sorted(keys.items())))
        okeys = collections.Counter(k for x in rows for o in x.get("owners") or [] for k in o.keys())
        OUT.append(f"   owners 필드: {dict(okeys)} · 서로 다른 owner id {len({o.get('id') for x in rows for o in x.get('owners') or []})} · entity_id {len({o.get('entity_id') for x in rows for o in x.get('owners') or [] if o.get('entity_id')})}")
        bkeys = collections.Counter(k for x in rows for fb in x.get("filing_bases") or [] for k in fb.keys())
        btypes = collections.Counter(fb.get("basis_type") for x in rows for fb in x.get("filing_bases") or [])
        OUT.append(f"   filing_bases 있는 줄 {sum(1 for x in rows if x.get('filing_bases'))} · 필드 {dict(bkeys)} · 종류 {dict(btypes)}")
        OUT.append(f"   관청 {dict(collections.Counter(x.get('office_code') for x in rows))} · 경로 {dict(collections.Counter(x.get('filing_route') for x in rows))} · 출원일 {min(str(x.get('filing_date')) for x in rows)}~{max(str(x.get('filing_date')) for x in rows)}")
        OUT.append(f"   relationships 있는 줄 {sum(1 for x in rows if x.get('relationships'))} · updated_at 있는 줄 {sum(1 for x in rows if x.get('updated_at'))}")
    return rows


if not KEY:
    OUT.append("## SIGNA_API_KEY 없음")
else:
    a = search("1 phrase 'Hyundai Motor' US,EM", owner_name="Hyundai Motor", owner_name_match="phrase", offices="US,EM", filing_date_gte=SINCE, sort="-filing_date", limit=100, include_total="true")
    b = search("2 phrase 'KG Mobility' US,EM", owner_name="KG Mobility", owner_name_match="phrase", offices="US,EM", filing_date_gte=SINCE, sort="-filing_date", limit=100, include_total="true")
    if b:
        names = {str(o.get("name") or "") for x in b for o in x.get("owners") or []}
        OUT.append(f"   KG Mobility phrase: 출원인 이름 {len(names)}종 · 'KG Mobility' 든 이름 {sum(1 for n in names if re.search(r'KG\s*Mobility', n, re.I))} · 'Co. KG' 든 이름 {sum(1 for n in names if re.search(r'Co\.?\s*KG', n))}")
    ids = sorted({o.get("id") for x in a + b for o in x.get("owners") or [] if o.get("id") and re.search(r"hyundai motor|kg\s*mobility", str(o.get("name") or ""), re.I)})
    OUT.append(f"## 모은 owner id {len(ids)}개 · 꼴 {sorted({re.sub(r'[A-Za-z0-9]', 'x', i[4:])[:6] + '…' for i in ids})[:2]} 머리 {sorted({i[:4] for i in ids})}")
    if ids:
        c = search("3 owner_id 목록 US,EM", owner_id=",".join(ids[:45]), offices="US,EM", filing_date_gte=SINCE, sort="-filing_date", limit=100, include_total="true")
        got = {o.get("id") for x in c for o in x.get("owners") or []}
        OUT.append(f"   목록 조회 줄의 owner id가 물은 목록 안 {len(got & set(ids))}/{len(got)} · 1·2번 줄과 겹치는 출원번호 {len({x.get('application_number') for x in c} & {x.get('application_number') for x in a + b})}/{len({x.get('application_number') for x in a + b})}")
        search("4 같은 목록 + updated_at_gte 4일", owner_id=",".join(ids[:45]), offices="US,EM", filing_date_gte=SINCE, updated_at_gte=RECENT, sort="-filing_date", limit=100, include_total="true")
    r = requests.get("https://api.signa.so/v1/offices", headers=H, timeout=40)
    OUT.append(f"## /v1/offices: HTTP {r.status_code} · 머리글 {credit_headers(r)}")
    if r.status_code == 200:
        body = r.json() or {}
        rows = body.get("data") if isinstance(body, dict) else body
        rows = rows if isinstance(rows, list) else []
        OUT.append(f"   관청 {len(rows)}곳 · 필드 {sorted(rows[0].keys()) if rows else []}")
        for x in rows:
            code = x.get("code") or x.get("office_code") or x.get("id")
            if code in ("US", "EM", "WO", "KR"):
                OUT.append(f"   {code}: last_synced_at {x.get('last_synced_at')} · " + ", ".join(f"{k}={x.get(k)}" for k in x if re.search(r"sync|fresh|lag|updated", k) and k != "last_synced_at"))
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
