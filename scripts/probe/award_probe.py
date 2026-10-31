"""Probe 45: OSHA — 출입처 이름 like 5개씩 OR(주소 길이 403 회피), 호출 간 12초. 2025-01 이후 점검을 회사별 규칙으로 나눠
건수·점검 종류·위반 종류·벌금 합·사망 건수만. 사업장 이름·주소·서술·응답 원문은 출력하지 않는다."""
import collections
import json
import os
import re
import time
import requests

KEY = os.environ.get("DOL_API_KEY", "").strip()
B = "https://apiprod.dol.gov/v4/get/OSHA"
H = {"User-Agent": "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"}
out = []
RULES = [("현대차", r"HYUNDAI MOTOR (?:MANUFACTURING|GROUP METAPLANT|AMERICA)|\bHMGMA\b|\bHMMA\b"), ("현대차(관련 합작)", r"HL-?GA BATTERY"),
         ("기아", r"\bKIA (?:GEORGIA|MOTORS? MANUFACTURING|MANUFACTURING|AMERICA|MOTORS AMERICA)"), ("현대모비스", r"\bMOBIS\b"),
         ("현대위아", r"HYUNDAI WIA|\bWIA (?:AMERICA|ALABAMA|GEORGIA)"), ("HL만도", r"\bHL MANDO\b|\bMANDO (?:AMERICA|CORP|GEORGIA|ALABAMA)|HL KLEMOVE"),
         ("한국타이어", r"HANKOOK TIRE"), ("넥센타이어", r"NEXEN TIRE"), ("금호타이어", r"KUMHO TIRE"),
         ("포스코", r"\bPOSCO\b(?! ?(?:INTERNATIONAL|FUTURE))"), ("현대제철", r"HYUNDAI STEEL"), ("세아제강", r"SEAH STEEL|\bSEAH (?:USA|AMERICA)"),
         ("동국제강·동국씨엠", r"DONGKUK"), ("고려아연", r"KOREA ZINC"), ("HD현대일렉트릭", r"HYUNDAI POWER TRANSFORMERS|HD HYUNDAI ELECTRIC"),
         ("LS일렉트릭", r"\bLS ELECTRIC"), ("LS전선", r"\bLS CABLE|LS GREENLINK"), ("LS전선(자회사)", r"SUPERIOR ESSEX"), ("대한전선", r"TAIHAN"),
         ("두산에너빌리티", r"DOOSAN (?:ENERBILITY|HEAVY)"), ("한화솔루션", r"HANWHA Q ?CELLS|\bQCELLS\b|HANWHA SOLUTIONS|HANWHA ADVANCED MATERIALS"),
         ("OCI", r"MISSION SOLAR|\bOCI ENERGY"), ("효성중공업(관련)", r"HYOSUNG")]
LIKES = ["%HYUNDAI MOTOR%", "%HMGMA%", "%HL-GA%", "%HLGA%", "%KIA %", "%MOBIS%", "%HYUNDAI WIA%", "%WIA %", "%MANDO%", "%KLEMOVE%", "%HANKOOK%",
         "%NEXEN%", "%KUMHO%", "%POSCO%", "%HYUNDAI STEEL%", "%SEAH%", "%DONGKUK%", "%KOREA ZINC%", "%HYUNDAI POWER%", "%HD HYUNDAI%", "%LS ELECTRIC%",
         "%LS CABLE%", "%GREENLINK%", "%SUPERIOR ESSEX%", "%TAIHAN%", "%DOOSAN%", "%HANWHA%", "%QCELLS%", "%MISSION SOLAR%", "%OCI ENERGY%", "%HYOSUNG%"]


def call(ep, **params):
    time.sleep(12)
    t0 = time.time()
    r = requests.get(f"{B}/{ep}/json", params={**params, "X-API-KEY": KEY}, headers=H, timeout=120)
    took = time.time() - t0
    if r.status_code == 204:
        return 204, [], took
    if r.status_code != 200:
        return r.status_code, None, took
    return 200, (r.json() or {}).get("data") or [], took


rows, codes = [], []
for i in range(0, len(LIKES), 5):
    f = {"and": [{"field": "open_date", "operator": "gt", "value": "2025-01-01"}, {"or": [{"field": "estab_name", "operator": "like", "value": p} for p in LIKES[i:i + 5]]}]}
    code, rs, took = call("inspection", limit=5000, sort="desc", sort_by="open_date", filter_object=json.dumps(f),
                          fields="activity_nr,estab_name,open_date,insp_type,insp_scope,site_state,close_case_date,nr_in_estab")
    codes.append(f"{code}:{len(rs or [])}:{took:.0f}s")
    rows += rs or []
out.append(f"inspection chunks {codes} total={len(rows)} unique={len({x['activity_nr'] for x in rows})}")
seen, kept = set(), collections.defaultdict(list)
for x in rows:
    if x["activity_nr"] in seen:
        continue
    seen.add(x["activity_nr"])
    name = (x.get("estab_name") or "").upper()
    kept[next((c for c, rx in RULES if re.search(rx, name)), None)].append(x)
for c in [c for c, _ in RULES] + [None]:
    xs = kept.get(c, [])
    if xs:
        out.append(f"  {c or '규칙 밖(버림)'}: insp={len(xs)} names={len({x['estab_name'] for x in xs})} types={dict(collections.Counter(x.get('insp_type') for x in xs))} "
                   f"latest={max(x.get('open_date') or '' for x in xs)[:10]} open-case={sum(1 for x in xs if not x.get('close_case_date'))}")
ids = [x["activity_nr"] for c, xs in kept.items() if c for x in xs]
out.append(f"kept activity_nr {len(ids)}")
vs, inj = [], []
for i in range(0, len(ids), 40):
    code, v, took = call("violation", limit=5000, filter_object=json.dumps({"field": "activity_nr", "operator": "in", "value": ids[i:i + 40]}),
                         fields="activity_nr,citation_id,viol_type,issuance_date,initial_penalty,current_penalty,delete_flag,gravity")
    out.append(f"violation chunk {i}: HTTP {code} rows={len(v or [])} {took:.0f}s")
    vs += v or []
    code, j, took = call("accident_injury", limit=2000, filter_object=json.dumps({"field": "rel_insp_nr", "operator": "in", "value": ids[i:i + 40]}),
                         fields="summary_nr,rel_insp_nr,degree_of_inj")
    out.append(f"injury chunk {i}: HTTP {code} rows={len(j or [])} {took:.0f}s")
    inj += j or []
if vs:
    per = collections.defaultdict(float)
    for v in vs:
        per[v["activity_nr"]] += float(v.get("initial_penalty") or 0)
    out.append(f"violation: rows={len(vs)} types={dict(collections.Counter(v.get('viol_type') for v in vs))} insp-with-viol={len(per)} "
               f"penalty-sum={round(sum(per.values()))} max-insp={round(max(per.values()))} >=100k insp={sum(1 for p in per.values() if p >= 100000)} "
               f"latest-issuance={max(v.get('issuance_date') or '' for v in vs)[:10]} deleted={sum(1 for v in vs if v.get('delete_flag'))}")
out.append(f"injury: rows={len(inj)} insp={len({i['rel_insp_nr'] for i in inj})} degree={dict(collections.Counter(i.get('degree_of_inj') for i in inj))}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
