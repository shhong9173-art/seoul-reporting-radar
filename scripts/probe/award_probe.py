"""probe 230: Signa 마드리드 지정 줄 → 기초출원(relationships, 상세 조회)과 크레딧. 공개 로그에는 필드 이름·관청 코드·날짜·건수만
(상표 이름·출원인·번호는 찍지 않는다). 검색 2번(20크레딧) + 상세 조회 2~3번."""
import collections
import datetime as dt
import os
import re

import requests

KEY = os.environ.get("SIGNA_API_KEY", "").strip()
OUT = []
H = {"Authorization": f"Bearer {KEY}", "Accept": "application/json", "User-Agent": "seoul-reporting-radar/1.0 (+https://github.com/shhong9173-art/seoul-reporting-radar)"}
SINCE = (dt.date.today() - dt.timedelta(days=500)).isoformat()
BASE = "https://api.signa.so/v1/trademarks"


def credits(r):
    return {k: v for k, v in r.headers.items() if re.search(r"credit", k, re.I)}


def shape(v):
    if v is None:
        return "null"
    if isinstance(v, str):
        return "날짜" if re.match(r"\d{4}-\d{2}-\d{2}", v) else f"글자{len(v)}"
    return type(v).__name__


def rels(x):
    out = []
    for e in x.get("relationships") or []:
        out.append("{" + ", ".join(f"{k}={e[k] if k in ('type', 'direction', 'target_office_code') else (e[k][:10] if isinstance(e[k], str) and re.match(r'\d{4}-\d{2}-\d{2}', e[k]) else shape(e[k]))}" for k in sorted(e)) + "}")
    return out


def detail(label, tid):
    r = requests.get(f"{BASE}/{tid}", headers=H, timeout=60)
    OUT.append(f"## 상세 {label}: HTTP {r.status_code} · 크레딧 {credits(r)}")
    if r.status_code != 200:
        OUT.append("   본문 앞: " + re.sub(r"\s+", " ", r.text)[:160])
        return {}
    b = r.json() or {}
    x = b.get("data") if isinstance(b.get("data"), dict) else b
    OUT.append(f"   office_code {x.get('office_code')} · scope_kind {x.get('scope_kind')} · filing_route {x.get('filing_route')} · origin_office_code {x.get('origin_office_code')} · "
               f"filing_date {x.get('filing_date')} · designation_date {x.get('designation_date')} · registration_date {x.get('registration_date')} · intl_registration_date {x.get('intl_registration_date')} · priority_date {x.get('priority_date')}")
    OUT.append(f"   relationships {len(x.get('relationships') or [])}건: " + " ; ".join(rels(x))[:900])
    OUT.append(f"   coverage {len(x.get('coverage') or [])}곳 · 필드 중 basic·origin·priority 든 것: {sorted(k for k in x if re.search(r'basic|origin|priorit|relation', k))}")
    return x


if not KEY:
    OUT.append("## SIGNA_API_KEY 없음")
else:
    r = requests.get(BASE, params={"owner_name": "POSCO", "owner_name_match": "phrase", "offices": "EM,US", "filing_route": "madrid_designation", "filing_date_gte": SINCE,
                                   "sort": "-filing_date", "limit": 20, "include_total": "true"}, headers=H, timeout=60)
    OUT.append(f"## 1 POSCO 마드리드 지정(EM·US, 500일): HTTP {r.status_code} · 크레딧 {credits(r)}")
    rows = (r.json() or {}).get("data") or [] if r.status_code == 200 else []
    OUT.append(f"   줄 {len(rows)} · 관청 {dict(collections.Counter(x.get('office_code') for x in rows))} · origin_office_code {dict(collections.Counter(x.get('origin_office_code') for x in rows))} · "
               f"ir_number 있는 줄 {sum(1 for x in rows if x.get('ir_number'))} · relationships 열쇠 있는 줄 {sum(1 for x in rows if 'relationships' in x)} · scope_kind {dict(collections.Counter(x.get('scope_kind') for x in rows))}")
    for x in rows[:3]:
        OUT.append(f"   줄: office {x.get('office_code')} · filing_date {x.get('filing_date')} · designation_date {x.get('designation_date')} · registration_date {x.get('registration_date')} · priority_date {x.get('priority_date')} · origin {x.get('origin_office_code')} · ir_number {shape(x.get('ir_number'))} · application_number {shape(x.get('application_number'))}")
    if rows:
        d = detail("지정 줄", rows[0]["id"])
        ir = rows[0].get("ir_number")
        if ir:
            g = requests.get(BASE, params={"ir_number": ir, "limit": 10}, headers=H, timeout=60)
            OUT.append(f"## 2 ir_number 조회(묶음): HTTP {g.status_code} · 크레딧 {credits(g)}")
            fam = (g.json() or {}).get("data") or [] if g.status_code == 200 else []
            OUT.append(f"   줄 {len(fam)} · " + " | ".join(f"office {x.get('office_code')} scope {x.get('scope_kind')} route {x.get('filing_route')} coverage {len(x.get('coverage') or [])} origin {x.get('origin_office_code')} filing {x.get('filing_date')} reg {x.get('registration_date')}" for x in fam[:4]))
            parent = next((x for x in fam if x.get("office_code") == "WO"), fam[0] if fam else None)
            if parent and parent.get("id") != rows[0]["id"]:
                detail("국제등록(WO) 줄", parent["id"])
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
