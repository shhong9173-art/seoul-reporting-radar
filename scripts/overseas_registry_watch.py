"""해외 법인 등기 감시(영국 Companies House): 출입처 영문명이 들어간 새 영국 법인 설립 등기.

- Companies House 공개 API 고급 검색(회사명 포함·설립일 기간)으로 출입처 영문명 법인을 찾고, 새로 본 법인은
  '중요 지배 주주(PSC)' 목록을 읽어 출입처 본사(법인)가 지배 주주로 적혔는지 본다.
  PSC에 출입처 본사·계열 법인 = A, 이름만 같음(딜러·무관 회사일 수 있음) = C.
- 키: GitHub Secret COMPANIES_HOUSE_API_KEY(무료, developer.company-information.service.gov.uk에서 발급).
  없으면 '미설정'(0건이 아님).
- 결과는 기자 전용 저장소(overseas-registry)로만. 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "overseas_registry/v1"
API = "https://api.company-information.service.gov.uk"
SITE = "https://find-and-update.company-information.service.gov.uk/company/"
BASELINE_DAYS = 365
OVERLAP_DAYS = 7
KEEP_MAX = 300

# (출입처, 검색 낱말, 회사명 규칙, PSC(지배 주주) 이름 규칙)
COMPANIES = [
    ("현대차", "hyundai", r"\bhyundai\b", r"hyundai\s+motor\s+(?:company|co\b)|hyundai\s+motor\s+europe|hyundai\s+motor\s+uk"),
    ("기아", "kia", r"\bkia\b", r"kia\s+(?:corporation|motors?\s+corporation|europe|uk)"),
    ("현대모비스", "mobis", r"\bmobis\b", r"hyundai\s+mobis"),
    ("HD현대일렉트릭", "hd hyundai", r"\bhd\s+hyundai\b", r"hd\s+hyundai"),
    ("효성중공업(관련)", "hyosung", r"\bhyosung\b", r"hyosung"),
    ("LS전선", "ls cable", r"\bls\s+cable", r"ls\s+cable"),
    ("LS일렉트릭", "ls electric", r"\bls\s+electric", r"ls\s+electric"),
    ("대한전선", "taihan", r"\btaihan\b", r"taihan"),
    ("두산에너빌리티", "doosan", r"\bdoosan\b", r"doosan\s+(?:enerbility|heavy)"),
    ("포스코", "posco", r"\bposco\b", r"posco"),
    ("현대제철", "hyundai steel", r"\bhyundai\s+steel", r"hyundai\s+steel"),
    ("한화솔루션", "hanwha", r"\bhanwha\b", r"hanwha\s+(?:solutions|q\s*cells|qcells)"),
    ("고려아연", "korea zinc", r"\bkorea\s+zinc", r"korea\s+zinc"),
    ("한국타이어", "hankook", r"\bhankook\b", r"hankook\s+(?:tire|&\s*company)"),
    ("넥센타이어", "nexen", r"\bnexen\b", r"nexen\s+tire"),
    ("금호타이어", "kumho", r"\bkumho\b", r"kumho\s+tire"),
    ("GS칼텍스", "gs caltex", r"\bgs\s+caltex", r"gs\s+caltex"),
    ("OCI", "oci", r"^oci\b", r"\boci\s+(?:holdings|company|co\b)"),
    ("세아", "seah", r"\bseah\b", r"seah"),
]
RULES = [
    "영국 법인 설립 등기다. 출입처 본사가 지배 주주(PSC)로 적힌 것만 A. 이름만 같은 회사(딜러·무관 회사)는 C.",
    "설립 목적(SIC 코드)·주소는 등기 그대로. 사업 내용·투자 규모는 회사 확인.",
    "다른 나라(미국 주 등기 등)는 다루지 않는다.",
]


def norm_space(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


class Client:
    def __init__(self, key, get=None, sleep=time.sleep):
        self.key, self.sleep = key, sleep
        if get is None:
            import requests
            get = requests.get
        self.get = get

    def json(self, path, params=None):
        r = self.get(API + path, params=params, auth=(self.key, ""), headers={"Accept": "application/json"}, timeout=40)
        if r.status_code == 429:
            self.sleep(60)
            r = self.get(API + path, params=params, auth=(self.key, ""), headers={"Accept": "application/json"}, timeout=40)
        if r.status_code == 404:
            return {}
        if r.status_code in (401, 403):
            raise PermissionError(f"HTTP {r.status_code}")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        self.sleep(0.6)  # 600 requests / 5 min
        return r.json()


def search(client, term, since):
    out, start = [], 0
    while start < 1000:
        d = client.json("/advanced-search/companies", {"company_name_includes": term, "incorporated_from": since, "size": 100, "start_index": start})
        items = d.get("items") or []
        out += items
        if len(items) < 100:
            break
        start += 100
    return out


def psc_names(client, number):
    d = client.json(f"/company/{number}/persons-with-significant-control")
    return [norm_space(x.get("name")) for x in d.get("items") or [] if x.get("name")]


def run(key, *, now, previous=None, get=None, sleep=time.sleep):
    stamp = now.isoformat(timespec="seconds")
    baseline = not (isinstance(previous, dict) and previous.get("companies") is not None)
    if not key:
        return {"schema": SCHEMA, "generatedAt": stamp, "status": "unset", "companies": (previous or {}).get("companies") or [], "rules": RULES,
                "checks": [{"source": "영국 Companies House", "status": "unset", "error": "COMPANIES_HOUSE_API_KEY 없음(무료 발급)"}]}
    client = Client(key, get=get, sleep=sleep)
    floor = now - dt.timedelta(days=BASELINE_DAYS)
    try:
        last = dt.datetime.fromisoformat(str((previous or {}).get("lastSuccess")))
        since_dt = max(floor, last - dt.timedelta(days=OVERLAP_DAYS))
    except (TypeError, ValueError):
        since_dt = floor
    since = since_dt.date().isoformat()
    old = {x["id"]: x for x in (previous or {}).get("companies") or []}
    out = dict(old)
    checks = []
    for beat, term, name_rx, psc_rx in COMPANIES:
        try:
            rows = search(client, term, since)
        except PermissionError as e:
            return {"schema": SCHEMA, "generatedAt": stamp, "status": "unset", "companies": list(old.values()), "rules": RULES,
                    "lastSuccess": (previous or {}).get("lastSuccess"),
                    "checks": [{"source": "영국 Companies House", "status": "unset", "error": f"키 거부({e}) — COMPANIES_HOUSE_API_KEY 확인"}]}
        except Exception as e:  # noqa: BLE001
            checks.append({"source": f"영국 Companies House {term}", "status": "failed", "error": str(e)[:60] or type(e).__name__})
            continue
        kept = 0
        for x in rows:
            name = norm_space(x.get("company_name"))
            if not re.search(name_rx, name, re.I):
                continue
            num = str(x.get("company_number") or "")
            cid = f"ch:{num}"
            prev = old.get(cid)
            rec = {"id": cid, "company": beat, "name": name, "number": num, "status": x.get("company_status"),
                   "type": x.get("company_type"), "created": x.get("date_of_creation"), "sic": x.get("sic_codes") or [],
                   "address": norm_space(", ".join(v for v in (x.get("registered_office_address") or {}).values() if isinstance(v, str)))[:160],
                   "url": SITE + num}
            if prev and "psc" in prev:
                rec["psc"] = prev["psc"]
            else:
                try:
                    rec["psc"] = psc_names(client, num)
                except Exception as e:  # noqa: BLE001
                    rec["psc"], rec["pscError"] = [], str(e)[:40]
            rec["pscMatch"] = any(re.search(psc_rx, p, re.I) for p in rec["psc"])
            rec["tier"] = "A" if rec["pscMatch"] else "C"
            rec["firstSeen"] = prev["firstSeen"] if prev else stamp
            rec["baseline"] = bool(prev.get("baseline")) if prev else baseline
            rec["isNew"] = not prev and not baseline
            out[cid] = rec
            kept += 1
        checks.append({"source": f"영국 Companies House {term}", "status": "ok", "returned": len(rows), "matched": kept})
    for cid, x in out.items():
        if cid in old and x is old[cid]:
            x["isNew"] = False
    companies = sorted(out.values(), key=lambda x: (str(x.get("created") or ""), x["id"]), reverse=True)[:KEEP_MAX]
    failed = [c for c in checks if c["status"] == "failed"]
    status = "failed" if checks and len(failed) == len(checks) else "partial" if failed else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "companies": companies, "rules": RULES,
            "windowStart": since, "lastSuccess": stamp if status != "failed" else (previous or {}).get("lastSuccess")}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    key = os.environ.get("COMPANIES_HOUSE_API_KEY", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("overseas-registry", token)
        except private_store.StoreError as e:
            print(f"::warning title=overseas-registry-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(key, now=now, previous=previous)
    new = [x for x in doc["companies"] if x.get("isNew")]
    print(f"::notice title=overseas-registry::상태 {doc['status']} · 질의 {sum(1 for c in doc['checks'] if c['status'] == 'ok')}/{len(doc['checks'])} · "
          f"새 법인 {len(new)}(지배 주주 확인 {sum(1 for x in new if x.get('pscMatch'))}) · 보관 {len(doc['companies'])}")
    if not token:
        print("::warning title=overseas-registry-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("Companies House 전체 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("overseas-registry", doc, token)
    print(f"::notice title=overseas-registry-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
