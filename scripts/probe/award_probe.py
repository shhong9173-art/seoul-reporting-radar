"""Probe 43: OSHA — 출입처 미국 법인 이름 규칙(회사별) 한 번의 OR 질의로 2025-01 이후 점검, 위반·사고 연결. 호출 간 8초(429 방지).
회사별 건수·점검 종류·위반 종류·벌금 합·사망 건수만. 사업장 이름·주소·서술은 출력하지 않는다."""
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
    time.sleep(8)
    r = requests.get(f"{B}/{ep}/json", params={**params, "X-API-KEY": KEY}, headers=H, timeout=90)
    if r.status_code == 204:
        return 204, []
    if r.status_code != 200:
        return r.status_code, None
    return 200, (r.json() or {}).get("data") or []


f = {"and": [{"field": "open_date", "operator": "gt", "value": "2025-01-01"}, {"or": [{"field": "estab_name", "operator": "like", "value": p} for p in LIKES]}]}
code, rows = call("inspection", limit=5000, sort="desc", sort_by="open_date", filter_object=json.dumps(f),
                  fields="activity_nr,estab_name,open_date,insp_type,insp_scope,site_state,close_case_date,naics_code,nr_in_estab")
out.append(f"inspection OR query: HTTP {code} rows={len(rows or [])}")
kept = collections.defaultdict(list)
for x in rows or []:
    name = (x.get("estab_name") or "").upper()
    hit = next((c for c, rx in RULES if re.search(rx, name)), None)
    kept[hit].append(x)
for c in [c for c, _ in RULES] + [None]:
    xs = kept.get(c, [])
    if not xs:
        continue
    out.append(f"  {c or '규칙 밖(버림)'}: insp={len(xs)} names={len({x['estab_name'] for x in xs})} types={dict(collections.Counter(x.get('insp_type') for x in xs))} "
               f"latest={max(x.get('open_date') or '' for x in xs)[:10]} open={sum(1 for x in xs if not x.get('close_case_date'))}")
ids = [x["activity_nr"] for c, xs in kept.items() if c for x in xs]
out.append(f"kept activity_nr {len(ids)}")
if ids:
    code, vs = call("violation", limit=5000, filter_object=json.dumps({"field": "activity_nr", "operator": "in", "value": ids[:400]}),
                    fields="activity_nr,citation_id,viol_type,issuance_date,initial_penalty,current_penalty,standard,delete_flag,gravity")
    vs = vs or []
    out.append(f"violation: HTTP {code} rows={len(vs)} types={dict(collections.Counter(v.get('viol_type') for v in vs))} "
               f"insp-with-viol={len({v['activity_nr'] for v in vs})} penalty-sum={round(sum(float(v.get('initial_penalty') or 0) for v in vs))} "
               f"max-insp-penalty={round(max([sum(float(v.get('initial_penalty') or 0) for v in vs if v['activity_nr'] == a) for a in {v['activity_nr'] for v in vs}] or [0]))} "
               f"latest-issuance={max([v.get('issuance_date') or '' for v in vs] or [''])[:10]} deleted={sum(1 for v in vs if v.get('delete_flag'))}")
    code, inj = call("accident_injury", limit=2000, filter_object=json.dumps({"field": "rel_insp_nr", "operator": "in", "value": ids[:400]}),
                     fields="summary_nr,rel_insp_nr,degree_of_inj,nature_of_inj,event_type")
    inj = inj or []
    out.append(f"accident_injury: HTTP {code} rows={len(inj)} insp={len({i['rel_insp_nr'] for i in inj})} degree={dict(collections.Counter(i.get('degree_of_inj') for i in inj))}")
    if inj:
        sums = list({i["summary_nr"] for i in inj})[:100]
        code, acc = call("accident", limit=500, filter_object=json.dumps({"field": "summary_nr", "operator": "in", "value": sums}),
                         fields="summary_nr,event_date,fatality,event_keyword")
        acc = acc or []
        out.append(f"accident: HTTP {code} rows={len(acc)} fatality={dict(collections.Counter(a.get('fatality') for a in acc))} latest-event={max([a.get('event_date') or '' for a in acc] or [''])[:10]}")
open("/tmp/probe_out.txt", "w").write("\n".join(out))
