"""미국 OSHA(산업안전보건청) 점검·위반 감시: 출입처 미국 법인·공장의 새 점검(사망·중대사고·사고·민원·회부)과 위반 통지·사고 요약.

- 원천: 미국 노동부 데이터 API(https://apiprod.dol.gov/v4/get/OSHA/<inspection|violation|accident_injury|accident>/json,
  키 DOL_API_KEY, 무료). 탐침 10-31: 매일 적재(최근 개시 10-27·적재 10-30), 빠르게 10번 넘게 부르면 429, 주소가 길면(like 31개 OR) 403 —
  그래서 사업장 이름 like 5개씩 OR로 나눠 묻고 호출 사이 12초를 둔다.
- 사업장 이름(estab_name)을 회사별 규칙으로 거른다. like 검색에는 현대·기아 딜러, 이름 일부가 겹친 업체가 섞인다(탐침: 87건 중 48건 규칙 밖).
  규칙 밖 이름은 기자 전용 문서에 남겨 빠진 출입처가 없는지 볼 수 있게 한다.
- 등급: 새 점검 — 사망·중대사고(M)·사고(A) A, 민원(B)·회부(C) B, 나머지 C. 새 위반 통지 — 고의(W)·반복(R) 또는 벌금 합 10만 달러 이상 A,
  중대(S) B, 나머지 C. 사망 사고 요약 A, 나머지 사고 요약 B. 첫 실행은 기준선(1년 치 이력은 목록에만).
- OSHA 자료는 점검 개시 며칠 뒤에 올라오고, 위반 통지는 개시 뒤 최대 6개월, 사고 서술은 조사가 끝난 뒤에 나온다. 벌금은 최초 부과액이며
  이의 제기·합의로 바뀐다(current_penalty).
- 결과는 기자 전용 저장소(us-osha)로만. 공개 로그는 건수만(사업장 이름·주소·서술은 찍지 않는다). 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "us_osha/v1"
API = "https://apiprod.dol.gov/v4/get/OSHA"
UA = "seoul-reporting-radar research (github.com/shhong9173-art/seoul-reporting-radar)"
GAP = 12            # 호출 사이 초(429 방지)
CHUNK = 5           # like 몇 개씩 OR로 묶을지(주소 길이 403 방지)
ID_CHUNK = 40       # 위반·사고 조회 때 점검 번호 몇 개씩
WINDOW_DAYS = 400   # 개시일 몇 일 전까지 묻나
PENALTY_A = 100_000
RECENT_DAYS = 60    # 이보다 오래된 개시·통지는 '새로 본' 것이어도 이벤트로 올리지 않는다(이름 규칙을 넓혀 옛 점검이 처음 잡힌 경우)
# 출입처 미국 법인 이름 규칙(사업장 이름은 대문자). 딜러('… HYUNDAI', '… KIA')·이름 일부 겹침은 버린다.
RULES = [("현대차", r"HYUNDAI MOTOR (?:MANUFACTURING|GROUP METAPLANT|AMERICA)|\bHMGMA\b|\bHMMA\b"),
         ("현대차(관련 합작)", r"HL-?GA BATTERY"),
         ("기아", r"\bKIA (?:GEORGIA|MOTORS? MANUFACTURING|MANUFACTURING|AMERICA|MOTORS AMERICA)"),
         ("현대모비스", r"\bMOBIS\b"), ("현대위아", r"HYUNDAI WIA|\bWIA (?:AMERICA|ALABAMA|GEORGIA)"),
         ("HL만도", r"\bHL MANDO\b|\bMANDO (?:AMERICA|CORP|GEORGIA|ALABAMA)|HL KLEMOVE"),
         ("한국타이어", r"HANKOOK TIRE"), ("넥센타이어", r"NEXEN TIRE"), ("금호타이어", r"KUMHO TIRE"),
         ("포스코", r"\bPOSCO\b(?! ?(?:INTERNATIONAL|FUTURE))"), ("현대제철", r"HYUNDAI STEEL"),
         ("세아제강", r"SEAH STEEL|\bSEAH (?:USA|AMERICA)"), ("동국제강·동국씨엠", r"DONGKUK"), ("고려아연", r"KOREA ZINC"),
         ("HD현대일렉트릭", r"HYUNDAI POWER TRANSFORMERS|HD HYUNDAI ELECTRIC"), ("LS일렉트릭", r"\bLS ELECTRIC"),
         ("LS전선", r"\bLS CABLE|LS GREENLINK"), ("LS전선(자회사)", r"SUPERIOR ESSEX"), ("대한전선", r"TAIHAN"),
         ("두산에너빌리티", r"DOOSAN (?:ENERBILITY|HEAVY)"),
         ("한화솔루션", r"HANWHA Q ?CELLS|\bQCELLS\b|HANWHA SOLUTIONS|HANWHA ADVANCED MATERIALS"),
         ("OCI", r"MISSION SOLAR|\bOCI ENERGY"), ("효성중공업(관련)", r"HYOSUNG"),
         # 11-01 기자 명시: 석유화학(미국 사업장 — LG화학 테네시 양극재, 롯데케미칼 루이지애나)
         ("LG화학", r"\bLG CHEM\b"), ("롯데케미칼", r"LOTTE CHEMICAL")]
LIKES = ["%HYUNDAI MOTOR%", "%HMGMA%", "%HL-GA%", "%HLGA%", "%KIA %", "%MOBIS%", "%HYUNDAI WIA%", "%WIA %", "%MANDO%", "%KLEMOVE%",
         "%HANKOOK%", "%NEXEN%", "%KUMHO%", "%POSCO%", "%HYUNDAI STEEL%", "%SEAH%", "%DONGKUK%", "%KOREA ZINC%", "%HYUNDAI POWER%",
         "%HD HYUNDAI%", "%LS ELECTRIC%", "%LS CABLE%", "%GREENLINK%", "%SUPERIOR ESSEX%", "%TAIHAN%", "%DOOSAN%", "%HANWHA%", "%QCELLS%",
         "%MISSION SOLAR%", "%OCI ENERGY%", "%HYOSUNG%", "%LG CHEM%", "%LOTTE CHEM%"]
INSP_FIELDS = "activity_nr,estab_name,site_address,site_city,site_state,site_zip,open_date,insp_type,insp_scope,close_case_date,naics_code,nr_in_estab"
ADDR_CHUNK = 8      # 공장 주소 몇 개씩 in으로 묻나
SITES_MAX = 80
VIOL_FIELDS = "activity_nr,citation_id,viol_type,issuance_date,initial_penalty,current_penalty,standard,delete_flag"
INSP_TYPE = {"A": "사고", "B": "민원", "C": "회부", "D": "모니터링", "E": "변경 신청", "F": "후속", "G": "관련(비계획)", "H": "정기(계획)",
             "I": "기타(비계획)", "J": "관련(계획)", "K": "기타(계획)", "L": "기타", "M": "사망·중대사고"}
VIOL_TYPE = {"S": "중대", "W": "고의", "R": "반복", "O": "기타", "U": "미분류"}
DETAIL = "https://www.osha.gov/ords/imis/establishment.inspection_detail?id={nr}"


def norm_addr(a):
    a = re.sub(r"\s+", " ", str(a or "").upper()).strip(" ,.")
    return "" if not a or a.startswith(("PO BOX", "P.O.", "P O BOX")) or len(a) < 6 else a


def company_of(name):
    n = (name or "").upper()
    return next((c for c, rx in RULES if re.search(rx, n)), None)


def day(v):
    return str(v or "")[:10]


class Api:
    def __init__(self, key, get, sleep):
        self.key, self.get, self.sleep, self.calls, self.first = key, get, sleep, 0, True

    def __call__(self, ep, **params):
        """(행 목록, 오류). 204는 0건. 429는 30초 뒤 한 번 다시."""
        for attempt in (1, 2):
            if not self.first:
                self.sleep(GAP if attempt == 1 else 30)
            self.first = False
            self.calls += 1
            try:
                r = self.get(f"{API}/{ep}/json", params={**params, "X-API-KEY": self.key}, headers={"User-Agent": UA}, timeout=120)
            except Exception as e:  # noqa: BLE001
                return None, type(e).__name__
            if r.status_code == 204:
                return [], None
            if r.status_code == 429 and attempt == 1:
                continue
            if r.status_code != 200:
                return None, f"HTTP {r.status_code}"
            try:
                return (r.json() or {}).get("data") or [], None
            except ValueError:
                return None, "JSON 아님"
        return None, "HTTP 429"


def collect_rows(api, since):
    rows, errors = {}, []
    for i in range(0, len(LIKES), CHUNK):
        f = {"and": [{"field": "open_date", "operator": "gt", "value": since},
                     {"or": [{"field": "estab_name", "operator": "like", "value": p} for p in LIKES[i:i + CHUNK]]}]}
        data, err = api("inspection", limit=5000, sort="desc", sort_by="open_date", filter_object=json.dumps(f), fields=INSP_FIELDS)
        if err:
            errors.append(f"점검 {i // CHUNK + 1}묶음 {err}")
            continue
        for x in data:
            rows.setdefault(str(x.get("activity_nr")), x)
    return rows, errors


def site_rows(api, since, sites):
    """출입처 공장 주소(이름 규칙으로 잡힌 점검의 site_address)에서 열린 다른 사업장 점검 — 하도급·협력사·건설 현장.
    탐침 10-31: 하도급사 이름으로 열린 공장 안 점검은 이름 검색에 안 잡힌다(HMGMA·조지아 배터리 공장 건설 현장 등)."""
    rows, errors = {}, []
    raw = sorted({v["raw"] for v in sites.values() if v.get("raw")})
    for i in range(0, len(raw), ADDR_CHUNK):
        f = {"and": [{"field": "open_date", "operator": "gt", "value": since},
                     {"field": "site_address", "operator": "in", "value": raw[i:i + ADDR_CHUNK]}]}
        data, err = api("inspection", limit=5000, sort="desc", sort_by="open_date", filter_object=json.dumps(f), fields=INSP_FIELDS)
        if err:
            errors.append(f"공장 주소 {i // ADDR_CHUNK + 1}묶음 {err}")
            continue
        for x in data:
            rows.setdefault(str(x.get("activity_nr")), x)
    return rows, errors


def by_ids(api, ep, field, ids, fields):
    out, errors = [], []
    for i in range(0, len(ids), ID_CHUNK):
        data, err = api(ep, limit=5000, filter_object=json.dumps({"field": field, "operator": "in", "value": ids[i:i + ID_CHUNK]}),
                        **({"fields": fields} if fields else {}))
        if err:
            errors.append(f"{ep} {err}")
            continue
        out += data
    return out, errors


def viol_tier(vs):
    kinds = {v["type"] for v in vs}
    total = sum(v["initialPenalty"] for v in vs)
    if kinds & {"W", "R"} or total >= PENALTY_A:
        return "A"
    return "B" if "S" in kinds else "C"


def money(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def run(*, now, key, previous=None, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    had_state = bool(previous and previous.get("inspections") is not None)
    prev = {x["id"]: x for x in (previous or {}).get("inspections", []) if isinstance(x, dict) and x.get("id")}
    api = Api(key, get, sleep)
    since = (now.date() - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    rows, errors = collect_rows(api, since)
    kept, dropped = {}, {}

    def record(nr, x, company, **extra):
        return {"id": nr, "company": company, "estab": x.get("estab_name"), "address": x.get("site_address"), "city": x.get("site_city"),
                "state": x.get("site_state"), "opened": day(x.get("open_date")), "type": x.get("insp_type"),
                "typeName": INSP_TYPE.get(x.get("insp_type"), x.get("insp_type")), "scope": x.get("insp_scope"),
                "closed": day(x.get("close_case_date")) or None, "naics": x.get("naics_code"), "employees": x.get("nr_in_estab"),
                "url": DETAIL.format(nr=nr), **extra}

    for nr, x in rows.items():
        c = company_of(x.get("estab_name"))
        if not c:
            dropped[x.get("estab_name") or "?"] = dropped.get(x.get("estab_name") or "?", 0) + 1
            continue
        kept[nr] = record(nr, x, c)
    # 출입처 공장 주소: 이번에 잡힌 점검 + 지난 실행에서 쌓인 주소(하도급 점검은 주소로만 잡힌다)
    sites = {k: v for k, v in ((previous or {}).get("sites") or {}).items() if isinstance(v, dict)}
    for x in kept.values():
        a = norm_addr(x.get("address"))
        if a:
            sites[a] = {"raw": x.get("address"), "company": x["company"], "city": x.get("city"), "state": x.get("state"),
                        "lastSeen": max(x["opened"], (sites.get(a) or {}).get("lastSeen") or "")}
    sites = dict(sorted(sites.items(), key=lambda kv: kv[1].get("lastSeen") or "", reverse=True)[:SITES_MAX])
    contractor_rows, serr = site_rows(api, since, sites) if sites else ({}, [])
    errors += serr
    for nr, x in contractor_rows.items():
        if nr in kept or company_of(x.get("estab_name")):
            continue
        owner = sites.get(norm_addr(x.get("site_address")))
        if owner:
            kept[nr] = record(nr, x, owner["company"], atSite=True)
    ids = sorted(kept)
    viols, verr = by_ids(api, "violation", "activity_nr", [int(i) for i in ids], VIOL_FIELDS) if ids else ([], [])
    injuries, ierr = by_ids(api, "accident_injury", "rel_insp_nr", [int(i) for i in ids], "summary_nr,rel_insp_nr,degree_of_inj") if ids else ([], [])
    summaries = sorted({str(i.get("summary_nr")) for i in injuries if i.get("summary_nr")})
    accidents, aerr = by_ids(api, "accident", "summary_nr", [int(s) for s in summaries], "summary_nr,event_date,event_desc,fatality,abstract_text") if summaries else ([], [])
    errors += verr + ierr + aerr
    acc = {str(a.get("summary_nr")): a for a in accidents}
    for x in kept.values():
        vs = [{"citation": v.get("citation_id"), "type": v.get("viol_type"), "typeName": VIOL_TYPE.get(v.get("viol_type"), v.get("viol_type")),
               "issued": day(v.get("issuance_date")), "initialPenalty": money(v.get("initial_penalty")), "currentPenalty": money(v.get("current_penalty")),
               "standard": v.get("standard")}
              for v in viols if str(v.get("activity_nr")) == x["id"] and not (v.get("delete_flag") or "").strip()]
        x["violations"] = sorted(vs, key=lambda v: (v["issued"], v["citation"] or ""))
        x["penaltyInitial"] = round(sum(v["initialPenalty"] for v in vs))
        x["penaltyCurrent"] = round(sum(v["currentPenalty"] for v in vs))
        sums = sorted({str(i.get("summary_nr")) for i in injuries if str(i.get("rel_insp_nr")) == x["id"]})
        x["accidents"] = [{"summary": s, "date": day(acc.get(s, {}).get("event_date")), "fatality": str(acc.get(s, {}).get("fatality") or "").strip() in ("1", "X", "Y", "True", "true"),
                           "desc": acc.get(s, {}).get("event_desc"), "abstract": str(acc.get(s, {}).get("abstract_text") or "")[:600]} for s in sums]
        old = prev.get(x["id"], {})
        x["firstSeen"] = old.get("firstSeen") or stamp
        # [신규]는 이번에 처음 본 것 중 개시가 최근인 것만(공장 주소 질의를 새로 붙여 처음 잡힌 옛 하도급 점검은 아님 — 운영 11-01)
        x["isNew"] = had_state and not old and x["opened"] >= (now.date() - dt.timedelta(days=RECENT_DAYS)).isoformat()
    chunks = len(range(0, len(LIKES), CHUNK))
    insp_errors = sum(1 for e in errors if e.startswith("점검 "))
    inspections_failed = insp_errors >= chunks and not rows
    if inspections_failed and prev:
        kept = {k: dict(v, stale=True) for k, v in prev.items()}
    elif prev:
        # 이번에 안 돌아온 지난 점검(묶음 실패 또는 원천에서 빠짐)은 지우지 않고 표시만
        for k, v in prev.items():
            if k not in kept and str(v.get("opened") or "") > since:
                kept[k] = dict(v, notReturned=stamp if not insp_errors else v.get("notReturned"), stale=bool(insp_errors))
    # 이벤트: 새 점검, 새 위반 통지(점검별 이번에 처음 본 인용 번호), 새 사고 요약
    keep_from = (now - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    seen = {e["id"] for e in events}
    fresh = []
    recent = (now.date() - dt.timedelta(days=RECENT_DAYS)).isoformat()
    if had_state and not inspections_failed:
        for x in kept.values():
            if x.get("stale") or x.get("notReturned"):
                continue
            old = prev.get(x["id"])
            where = f"{x['estab']} ({x['city'] or '?'}, {x['state'] or '?'})"
            if x.get("atSite"):
                where = f"{x['estab']} — 출입처 공장 주소({x['address'] or '?'}, {x['city'] or '?'}, {x['state'] or '?'})의 하도급·협력사"
            if not old and x["opened"] >= recent:
                t = "A" if x["type"] in ("M", "A") else "C" if x.get("atSite") else "B" if x["type"] in ("B", "C") else "C"
                fresh.append({"id": f"osha:insp:{x['id']}", "kind": "점검 개시", "tier": t, "company": x["company"], "inspection": x["id"],
                              "text": f"OSHA 점검 개시 {x['opened']} · {x['typeName']}({x['type']}) · {where} · 범위 {x['scope'] or '?'}"
                                      f"{' · 종업원 ' + str(x['employees']) + '명' if x.get('employees') else ''}", "url": x["url"], "detectedAt": stamp})
            old_cits = {v.get("citation") for v in (old or {}).get("violations", [])}
            new_v = [v for v in x["violations"] if v["citation"] not in old_cits and v["issued"] >= recent]
            if new_v:
                kinds = sorted({v["typeName"] for v in new_v})
                total = round(sum(v["initialPenalty"] for v in new_v))
                vt = viol_tier(new_v)
                fresh.append({"id": f"osha:viol:{x['id']}:{max(v['issued'] for v in new_v)}", "kind": "위반 통지",
                              "tier": ("B" if vt == "A" else "C") if x.get("atSite") else vt,
                              "company": x["company"], "inspection": x["id"],
                              "text": f"OSHA 위반 통지 {max(v['issued'] for v in new_v)} · {len(new_v)}건({'·'.join(kinds)}) · 최초 벌금 합 ${total:,} · {where} · "
                                      f"점검 개시 {x['opened']}({x['typeName']}) · 기준 {', '.join(sorted({str(v['standard']) for v in new_v if v['standard']}))[:120]}",
                              "url": x["url"], "detectedAt": stamp})
            old_acc = {a.get("summary") for a in (old or {}).get("accidents", [])}
            for a in x["accidents"]:
                if a["summary"] in old_acc or (a["date"] and a["date"] < (now.date() - dt.timedelta(days=180)).isoformat()):
                    continue
                fresh.append({"id": f"osha:acc:{a['summary']}", "kind": "사고 요약", "tier": "A" if a["fatality"] else "B", "company": x["company"],
                              "inspection": x["id"], "text": f"OSHA 사고 요약 {a['date'] or '?'}{' · 사망' if a['fatality'] else ''} · {where} · "
                                                             f"{(a['desc'] or '')[:160]}", "url": x["url"], "detectedAt": stamp})
    events += [e for e in fresh if e["id"] not in seen]
    events.sort(key=lambda e: e["detectedAt"], reverse=True)
    status = "failed" if inspections_failed else "partial" if errors else "ok"
    check = {"source": "미국 OSHA(노동부 API)", "status": status, "returned": len(rows), "kept": len(kept), "calls": api.calls,
             **({"error": "; ".join(errors[:4])} if errors else {})}
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "partial" if status != "ok" else "complete", "checks": [check],
            "baselineSince": (previous or {}).get("baselineSince") or stamp, "since": since,
            "inspections": sorted(kept.values(), key=lambda x: (x["opened"], x["id"]), reverse=True),
            "events": events[:300], "dropped": sorted(dropped.items(), key=lambda kv: -kv[1])[:120], "sites": sites,
            "rules": ["OSHA 점검은 위반 확정이 아니다. 위반은 통지(citation)로, 벌금은 최초 부과액이며 이의 제기·합의로 바뀐다.",
                      "사업장 이름 규칙으로 출입처 미국 법인을 고른다(딜러·이름 겹침 제외). 하도급·협력사 점검은 출입처 점검에 나온 공장 주소와 같은 주소로 열린 것만 잡는다 — 주소 표기가 다르면 빠진다.",
                      "공장 주소의 하도급·협력사 점검은 그 회사(하도급사) 점검이다. 출입처 책임으로 쓰지 않는다. 사망·중대사고만 A.",
                      "점검은 개시 며칠 뒤, 위반 통지는 최대 6개월 뒤, 사고 서술은 조사가 끝난 뒤에 자료에 올라온다.",
                      "사망·중대사고 점검(M)은 사고가 났다는 뜻이지 회사 책임이 확정된 것이 아니다. 사망자·경위는 OSHA 원문·현지 보도로 확인한다.",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="미국 OSHA 점검·위반 감시(기자 전용 저장소로)").parse_args()
    now = dt.datetime.now(KST)
    key = os.environ.get("DOL_API_KEY", "").strip()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not key:
        sys.exit("DOL_API_KEY 미설정 — 실행하지 않음(0건 아님)")
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("us-osha", token)
        except private_store.StoreError as e:
            print(f"::warning title=us-osha-state::이전 상태 조회 실패({e}) — 신규 표시는 다음 실행부터")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    t0 = time.monotonic()
    doc = run(now=now, key=key, previous=previous)
    c = doc["checks"][0]
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=us-osha::{c['status']} · 조회 {c['returned']}건 중 출입처 {c['kept']}건 · 호출 {c['calls']}번 · {round(time.monotonic() - t0)}초 · "
          f"이번 이벤트 {len(new)}(A {sum(1 for e in new if e['tier'] == 'A')}·B {sum(1 for e in new if e['tier'] == 'B')})"
          f"{' · ' + c['error'][:200] if c.get('error') else ''}")
    if not token:
        print("::warning title=us-osha-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if c["status"] == "failed":
        sys.exit("점검 조회 전부 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("us-osha", doc, token)
    print(f"::notice title=us-osha-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
