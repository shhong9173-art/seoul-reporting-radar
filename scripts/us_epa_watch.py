"""미국 EPA 연비·인증 감시: 현대차·기아·제네시스의 새 EPA 등록(새 모델, 전기차 주행거리 변화).

- 원천: fueleconomy.gov 전체 차량 파일(vehicles.csv.zip, EPA 인증 연비·전기차 주행거리, 한 달 남짓마다 갱신). 등록일(createdOn)이 있다.
- 국내 연비 신고(한국에너지공단 수송에너지 누리집)는 해외 러너에서 접속이 거부돼(탐침 10-28 ConnectionError) 대신 미국 인증을 본다.
- 처음 보는 차량 ID만 새 등록. 그중 같은 회사에 이전 연식이 없는 모델(baseModel)은 '새 모델', 전기차는 같은 모델 직전 연식과
  주행거리가 다르면 '주행거리 변화', 나머지는 '연식 변경'. 첫 실행은 기준선.
- 결과는 기자 전용 저장소(us-epa)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "us_epa/v1"
DATA = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip"
PAGE = "https://www.fueleconomy.gov/feg/PowerSearch.do?action=noform&path=1&year1={year}&year2={year}&make={make}&baseModel={base}&srchtyp=ymm"
MAKES = {"Hyundai": "현대차", "Kia": "기아", "Genesis": "제네시스"}
KEEP_DAYS = 180
# NHTSA vPIC: makers register VIN decoding (model names) for coming model years before launch. Exact make IDs only —
# 'genesis'/'kia' name searches also return trailer and RV makers (탐침 10-29: GENESIS SUPREME RV, TEKIAR, MGS GRAND SPORT).
VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeIdYear/makeId/{mid}/modelyear/{year}?format=json"
VPIC_MAKES = {498: ("Hyundai", "현대차"), 499: ("Kia", "기아"), 5083: ("Genesis", "제네시스")}
VPIC_SOURCE = "NHTSA vPIC 모델명(VIN 등록)"
UA = "seoul-reporting-radar (github.com/shhong9173-art/seoul-reporting-radar)"


def created(v):
    """'Wed Sep 16 00:00:00 EDT 2026' → '2026-09-16'."""
    m = re.match(r"\w{3} (\w{3}) (\d{1,2}) [\d:]+ \w+ (\d{4})", str(v or ""))
    if not m:
        return None
    try:
        return dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%b %d %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 1)
    except (TypeError, ValueError):
        return None


def rows_of(raw):
    out = []
    for x in csv.DictReader(io.StringIO(raw)):
        if x.get("make") in MAKES and x.get("id"):
            out.append(x)
    return out


def classify(x, rows):
    base, year, make = x.get("baseModel") or x.get("model"), int(x.get("year") or 0), x.get("make")
    earlier = [r for r in rows if r.get("make") == make and (r.get("baseModel") or r.get("model")) == base and int(r.get("year") or 0) < year]
    if not earlier:
        return "새 모델", None
    if x.get("atvType") == "EV" and num(x.get("range")):
        prev_year = max(int(r.get("year") or 0) for r in earlier)
        prev = [num(r.get("range")) for r in earlier if int(r.get("year") or 0) == prev_year and r.get("atvType") == "EV" and num(r.get("range"))]
        if prev and num(x["range"]) not in prev:
            return "주행거리 변화", {"previousYear": prev_year, "previousRanges": sorted(set(prev))}
    return "연식 변경", None


def vpic_models(now, previous, get):
    """Model names registered with NHTSA for this and the next two model years; a name new to its maker is a lead."""
    prev = previous or {}
    seen = set(prev.get("vpicSeen") or [])
    baseline = "vpicSeen" not in prev
    stamp = now.isoformat(timespec="seconds")
    found = {}
    try:
        for mid, (make, _) in VPIC_MAKES.items():
            for year in (now.year, now.year + 1, now.year + 2):
                r = get(VPIC.format(mid=mid, year=year), headers={"User-Agent": UA}, timeout=40)
                if r.status_code != 200:
                    raise RuntimeError(f"HTTP {r.status_code}")
                for x in r.json().get("Results") or []:
                    if x.get("Make_ID") != mid or not x.get("Model_Name"):
                        continue
                    found.setdefault((make, str(x["Model_Name"]).strip()), set()).add(year)
    except Exception as e:  # noqa: BLE001
        return [], sorted(seen), {"source": VPIC_SOURCE, "status": "failed", "error": str(e)[:80] or type(e).__name__}
    keys = {f"{mk.lower()}|{md.lower()}" for mk, md in found}
    items = [x for x in prev.get("vpicModels") or [] if isinstance(x, dict) and x.get("id")]
    have = {x["id"] for x in items}
    if not baseline:
        for (make, model), years in sorted(found.items()):
            k = f"{make.lower()}|{model.lower()}"
            vid = f"vin:{k}"
            if k in seen or vid in have:
                continue
            mid = next(m for m, (mk, _) in VPIC_MAKES.items() if mk == make)
            items.append({"id": vid, "company": VPIC_MAKES[mid][1], "make": make, "model": model, "years": sorted(years),
                          "kind": "VIN 모델명 등록", "url": VPIC.format(mid=mid, year=min(years)), "firstSeen": stamp})
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    items = [x for x in items if str(x.get("firstSeen")) >= keep_from]
    for x in items:
        x["isNew"] = x["id"] not in have
    return items, sorted(seen | keys), {"source": VPIC_SOURCE, "status": "ok", "models": len(found)}


def run(*, now, previous=None, get=None):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    vpic_items, vpic_seen, vpic_check = vpic_models(now, previous, get)
    vpic = {"vpicModels": vpic_items, "vpicSeen": vpic_seen}
    prev_items = {x["id"]: x for x in (previous or {}).get("vehicles", []) if isinstance(x, dict) and x.get("id")}
    seen = set((previous or {}).get("seenIds") or [])
    baseline = not (previous or {}).get("seenIds")
    try:
        r = get(DATA, headers={"User-Agent": UA}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        rows = rows_of(z.read(z.namelist()[0]).decode("latin-1"))
        if not rows:
            raise RuntimeError("현대차·기아·제네시스 행 없음")
        check = {"source": "EPA fueleconomy.gov 차량 파일", "status": "ok", "rows": len(rows), "fileModified": getattr(r, "headers", {}).get("Last-Modified")}
    except Exception as e:
        return {"schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": [{"source": "EPA fueleconomy.gov 차량 파일", "status": "failed",
                "error": str(e)[:80] or type(e).__name__}, vpic_check], "vehicles": list(prev_items.values()), "seenIds": sorted(seen), **vpic,
                "rules": RULES, "confirmedScoops": 0}
    items = dict(prev_items)
    for x in rows:
        vid = f"epa:{x['id']}"
        if x["id"] in seen or baseline:
            continue
        kind, detail = classify(x, rows)
        items[vid] = {"id": vid, "company": MAKES[x["make"]], "make": x["make"], "year": x.get("year"), "model": x.get("model"),
                      "baseModel": x.get("baseModel") or x.get("model"), "atvType": x.get("atvType") or "", "vclass": x.get("VClass"),
                      "drive": x.get("drive"), "trany": x.get("trany"), "evMotor": x.get("evMotor") or "", "range": num(x.get("range")),
                      "comb": num(x.get("comb08")), "created": created(x.get("createdOn")), "kind": kind, **({"compare": detail} if detail else {}),
                      "url": PAGE.format(year=x.get("year"), make=x.get("make"), base=(x.get("baseModel") or x.get("model") or "").replace(" ", "+")),
                      "firstSeen": stamp}
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    vehicles = sorted((v for v in items.values() if (v.get("created") or v["firstSeen"][:10]) >= keep_from),
                      key=lambda v: (v.get("created") or "", v["id"]), reverse=True)
    for v in vehicles:
        v["isNew"] = v["id"] not in prev_items
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "complete", "checks": [check, vpic_check], "vehicles": vehicles[:300], **vpic,
            "seenIds": sorted(seen | {x["id"] for x in rows}), "baselineSince": (previous or {}).get("baselineSince") or stamp,
            "rules": RULES, "confirmedScoops": 0}


RULES = ["미국 EPA 인증 연비·전기차 주행거리 파일(fueleconomy.gov)에 처음 올라온 현대차·기아·제네시스 차량만. 첫 실행은 기준선.",
         "NHTSA vPIC에 현대차·기아·제네시스가 처음 등록한 모델명(VIN 해독용, 올해~2년 뒤 연식)은 'VIN 모델명 등록'. 이름 등록은 출시 확정이 아니다.",
         "'새 모델'은 같은 회사에 이전 연식이 없는 모델 이름, '주행거리 변화'는 전기차의 직전 연식 대비 EPA 주행거리 변화. 미국 사양이며 국내 인증·출시와 다를 수 있다.",
         "국내 연비 신고(에너지공단)는 kr_fuel(공공데이터포털 API)로 따로 본다. 조회 실패는 0건이 아니라 미확인."]


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("us-epa", token)
        except private_store.StoreError as e:
            print(f"::warning title=us-epa-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(now=now, previous=previous)
    kinds = {}
    for v in doc["vehicles"]:
        if v.get("isNew"):
            kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    vc = doc["checks"][1] if len(doc["checks"]) > 1 else {}
    print(f"::notice title=us-epa::상태 {doc['status']} · 현대차·기아·제네시스 행 {doc['checks'][0].get('rows')} · 새 등록 {kinds} · 보관 {len(doc['vehicles'])} · "
          f"vPIC {vc.get('status')} 모델 {vc.get('models')} · 새 모델명 {sum(1 for x in doc.get('vpicModels') or [] if x.get('isNew'))}")
    if not token:
        print("::warning title=us-epa-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("EPA 파일 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("us-epa", doc, token)
    print(f"::notice title=us-epa-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
