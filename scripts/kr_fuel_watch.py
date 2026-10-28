"""국내 자동차 표시연비 신고 감시: 출입처 브랜드(국산 5사·수입 법인)의 새 연비 신고.

- 원천: 공공데이터포털 '한국에너지공단_자동차 표시연비 목록 조회 서비스'(데이터 15139827, 개발계정 자동승인·일 10,000회)
  GET apis.data.go.kr/B553530/CAREFF/CAREFF_LIST — 업체명·모델명·출시년도·연료·배기량·변속기·표시/도심/고속 연비·CO2·등급·
  1회 충전 주행거리·등록일(DATA_REG_DT). 에너지공단 누리집(bpms.kemco.or.kr)은 해외 러너에서 접속이 안 돼 이 API를 쓴다.
- 전체 목록을 1,000행씩 받아 업체명·모델명으로 출입처 브랜드만 고른다. 처음 보는 행(사양 묶음)만 새 신고. 첫 실행은 기준선.
- 분류: 같은 업체에 처음 보는 모델명이면 '새 모델명', 전기차 1회 충전 주행거리가 같은 모델명의 이전 행과 다르면 '주행거리 변화',
  나머지는 '사양·연식 추가'. 한 번에 너무 많이 바뀌면(자료 일괄 갱신) 모두 참고로만 둔다.
- 연비 신고는 출시 전에 나오는 경우가 많지만 출시 확정이 아니다. 결과는 기자 전용 저장소(kr-fuel)로만, 공개 로그는 건수만.
- 키가 이 데이터에 활용신청되지 않았으면 '미설정(활용신청 필요)'로 남긴다 — 0건이 아니다.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_fuel/v1"
API = "https://apis.data.go.kr/B553530/CAREFF/CAREFF_LIST"
DATASET = "https://www.data.go.kr/data/15139827/openapi.do"
SOURCE = "에너지공단 자동차 표시연비(공공데이터포털 15139827)"
ROWS = 1000
MAX_PAGES = 40
KEEP_DAYS = 180
BULK_LIMIT = 150
FIELDS = ["COMP_NM", "MODEL_NM", "YEAR", "CAR_KIND", "CAR_TYPE", "FUEL_NM", "ENGINE_DISPLACEMENT", "GEAR_TYPE",
          "DISPLAY_EFF", "URBAN_EFF", "HIGHWAY_EFF", "CO2_OUTPUT", "GRADE", "RANGE_PER_CHARGE", "ESTIMATED_FUEL_COST", "DATA_REG_DT"]
# 행을 가르는 칸(등록일은 빼서 일괄 재등록에 흔들리지 않게).
KEY_FIELDS = [f for f in FIELDS if f not in ("DATA_REG_DT", "ESTIMATED_FUEL_COST")]
AUDI_MODEL = re.compile(r"(^|[\s(])(A[1-8]|Q[2-8]|S[3-8]|RS\s?\d|e-tron|TT)(\b|$)", re.I)
# (출입처 이름, 업체명·모델명 규칙). 순서대로 첫 일치. 제네시스는 현대차 브랜드.
BRANDS = [
    ("현대차", re.compile(r"현대자동차|현대차|HYUNDAI|제네시스|GENESIS", re.I)),
    ("기아", re.compile(r"^\s*(\(주\)|㈜|주식회사)?\s*기아|KIA", re.I)),
    ("KG모빌리티", re.compile(r"KG\s*모빌리티|케이지모빌리티|KG\s*MOBILITY|쌍용자동차", re.I)),
    ("르노코리아", re.compile(r"르노", re.I)),
    ("한국GM", re.compile(r"한국지엠|한국GM|지엠코리아|쉐보레|CHEVROLET|캐딜락|CADILLAC|GMC", re.I)),
    ("메르세데스-벤츠 코리아", re.compile(r"벤츠|메르세데스|MERCEDES", re.I)),
    ("BMW코리아", re.compile(r"비엠더블유|BMW", re.I)),
    ("폭스바겐그룹", re.compile(r"폭스바겐|VOLKSWAGEN|아우디|AUDI", re.I)),
    ("혼다코리아", re.compile(r"혼다|HONDA", re.I)),
]
GATEWAY = re.compile(r"<(returnReasonCode|returnAuthMsg|errMsg|resultCode|resultMsg)>\s*([^<]{1,120})<")
NOT_REGISTERED = re.compile(r"(^|\D)(30|20)(\D|$)|SERVICE_KEY_IS_NOT_REGISTERED|SERVICE ACCESS DENIED|등록되지 않은|접근 거부")


class NotApproved(RuntimeError):
    pass


def company_of(row):
    comp, model = str(row.get("COMP_NM") or ""), str(row.get("MODEL_NM") or "")
    for name, rx in BRANDS:
        if rx.search(comp) or (name in ("현대차",) and re.search(r"제네시스|GENESIS", model, re.I)):
            if name == "폭스바겐그룹":
                return "아우디코리아" if re.search(r"아우디|AUDI", comp + " " + model, re.I) or AUDI_MODEL.search(model) else "폭스바겐코리아"
            return name
    return None


def ymd(v):
    d = re.sub(r"\D", "", str(v or ""))
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else None


def num(v):
    try:
        f = float(str(v).replace(",", ""))
        return int(f) if f.is_integer() else round(f, 1)
    except (TypeError, ValueError):
        return None


def row_key(row):
    raw = "|".join(str(row.get(f) or "").strip() for f in KEY_FIELDS)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def parse(text):
    """(resultCode, totalCount, rows). Gateway refusals come back as XML even with apiType=JSON."""
    t = (text or "").strip()
    if t.startswith("{"):
        d = json.loads(t)
        resp = d.get("response", d)
        header, body = resp.get("header") or {}, resp.get("body") or {}
        if not header and "OpenAPI_ServiceResponse" in d:
            h = (d["OpenAPI_ServiceResponse"] or {}).get("cmmMsgHeader") or {}
            raise NotApproved(f"{h.get('returnReasonCode', '?')} {h.get('returnAuthMsg', '')}".strip())
        items = body.get("items") or {}
        items = items.get("item", []) if isinstance(items, dict) else items
        items = items if isinstance(items, list) else [items]
        rows = [{k: str((x or {}).get(k) or "").strip() for k in FIELDS} for x in items if isinstance(x, dict)]
        return str(header.get("resultCode") or ""), int(body.get("totalCount") or 0), rows, str(header.get("resultMsg") or "")
    found = dict((k, v.strip()) for k, v in GATEWAY.findall(t))
    if found:
        code = found.get("returnReasonCode") or found.get("resultCode") or "?"
        msg = found.get("returnAuthMsg") or found.get("resultMsg") or found.get("errMsg") or ""
        if "returnReasonCode" in found or "returnAuthMsg" in found:
            raise NotApproved(f"{code} {msg}".strip())
        import xml.etree.ElementTree as ET
        root = ET.fromstring(t)
        rows = [{k: (it.findtext(k) or "").strip() for k in FIELDS} for it in root.iter("item")]
        return code, int((root.findtext(".//totalCount") or "0").strip() or 0), rows, msg
    raise ValueError("응답 형식을 알 수 없음")


def fetch_all(key, *, get, sleep=time.sleep):
    rows, total, page = [], None, 1
    while True:
        params = {"serviceKey": key, "pageNo": page, "numOfRows": ROWS, "apiType": "JSON"}
        r = None
        for attempt, timeout in ((1, 40), (2, 70)):
            try:
                r = get(API, params=params, headers={"User-Agent": "seoul-reporting-radar"}, timeout=timeout)
                break
            except Exception as e:  # noqa: BLE001 — network: one slower retry, then 미확인
                if attempt == 2:
                    raise RuntimeError(type(e).__name__)
                sleep(5)
        if r.status_code in (401, 403):
            msg = " ".join(f"{a} {b}" for a, b in GATEWAY.findall(r.text or ""))[:80]
            raise NotApproved(f"HTTP {r.status_code} {msg}".strip())
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        code, count, got, msg = parse(r.text)
        if code == "03":  # 데이터 없음
            count, got = 0, []
        elif code not in ("00", "0", "000"):
            if NOT_REGISTERED.search(f"{code} {msg}"):
                raise NotApproved(f"{code} {msg}".strip())
            raise RuntimeError(f"결과코드 {code} {msg}".strip()[:80])
        total = count if total is None else total
        rows.extend(got)
        if len(rows) >= total or not got:
            break
        page += 1
        if page > MAX_PAGES:
            raise RuntimeError(f"쪽 상한 {MAX_PAGES} 초과(전체 {total}행) — 일부만 받으면 새 신고를 잘못 셀 수 있어 멈춤")
        sleep(0.4)
    if total and len(rows) < total:
        raise RuntimeError(f"목록이 중간에 끝남({len(rows)}/{total}행)")
    return rows, total or 0


def classify(x, earlier):
    same = [r for r in earlier if r["company"] == x["company"] and r["model"] == x["model"]]
    if not same:
        return "새 모델명", None
    rng = num(x.get("range"))
    if rng:
        prev = sorted({num(r.get("range")) for r in same if num(r.get("range"))})
        if prev and rng not in prev:
            return "주행거리 변화", {"previousRanges": prev}
    return "사양·연식 추가", None


def slim(row, company):
    return {"company": company, "maker": row["COMP_NM"], "model": row["MODEL_NM"], "year": row["YEAR"], "carKind": row["CAR_KIND"],
            "carType": row["CAR_TYPE"], "fuel": row["FUEL_NM"], "displacement": row["ENGINE_DISPLACEMENT"], "gear": row["GEAR_TYPE"],
            "eff": row["DISPLAY_EFF"], "urban": row["URBAN_EFF"], "highway": row["HIGHWAY_EFF"], "co2": row["CO2_OUTPUT"],
            "grade": row["GRADE"], "range": row["RANGE_PER_CHARGE"], "registered": ymd(row["DATA_REG_DT"])}


def run(key, *, now, previous=None, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    prev_items = {x["id"]: x for x in prev.get("vehicles", []) if isinstance(x, dict) and x.get("id")}
    seen = set(prev.get("seenKeys") or [])
    keep = {"vehicles": list(prev_items.values()), "seenKeys": sorted(seen), "baselineSince": prev.get("baselineSince")}

    def stop(status, check):
        return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": [check], **keep,
                "rules": RULES, "dataset": DATASET, "confirmedScoops": 0}
    if not key:
        return stop("unset", {"source": SOURCE, "status": "unset", "error": "공공데이터포털 키 없음"})
    try:
        rows, total = fetch_all(key, get=get, sleep=sleep)
    except NotApproved as e:
        return stop("unset", {"source": SOURCE, "status": "unset", "error": f"공공데이터포털 활용신청 필요(15139827) — 응답 {str(e)[:60]}"})
    except Exception as e:  # noqa: BLE001
        return stop("failed", {"source": SOURCE, "status": "failed", "error": str(e)[:100] or type(e).__name__})
    beat = []
    for row in rows:
        c = company_of(row)
        if c:
            beat.append((row_key(row), slim(row, c)))
    check = {"source": SOURCE, "status": "ok", "rows": total, "beatRows": len(beat)}
    baseline = not seen
    fresh = [(k, x) for k, x in beat if k not in seen]
    bulk = not baseline and len(fresh) > BULK_LIMIT
    old_rows = [x for k, x in beat if k in seen]
    items = dict(prev_items)
    if not baseline:
        for k, x in fresh:
            kind, cmp_ = classify(x, old_rows)
            items[f"kf:{k}"] = {"id": f"kf:{k}", **x, "kind": kind, **({"compare": cmp_} if cmp_ else {}),
                                "bulk": bulk, "url": DATASET, "firstSeen": stamp}
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    vehicles = sorted((v for v in items.values() if (v.get("registered") or v["firstSeen"][:10]) >= keep_from),
                      key=lambda v: (v.get("registered") or "", v["id"]), reverse=True)
    for v in vehicles:
        v["isNew"] = v["id"] not in prev_items
    if bulk:
        check["note"] = f"새 행 {len(fresh)}개 — 자료 일괄 갱신으로 보고 모두 참고로만"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "complete", "checks": [check], "vehicles": vehicles[:300],
            "seenKeys": sorted(seen | {k for k, _ in beat}), "baselineSince": prev.get("baselineSince") or stamp,
            "bulk": bulk, "rules": RULES, "dataset": DATASET, "confirmedScoops": 0}


RULES = ["에너지공단 자동차 표시연비 목록(공공데이터포털)에 처음 올라온 출입처 브랜드 행만. 첫 실행은 기준선.",
         "'새 모델명'은 같은 업체에 처음 보는 모델명(새 차종·새 파워트레인·새 트림 이름), '주행거리 변화'는 전기차 1회 충전 주행거리가 같은 모델명 이전 행과 다른 것.",
         "연비 신고는 출시 확정이 아니다. 출시 시점·가격은 회사 확인. 조회 실패·활용신청 전은 0건이 아니라 미확인."]


def resolve_key(env):
    for name in ("DATA_GO_KR_KEY", "CUSTOMS_API_KEY", "G2B_API_KEY"):
        v = str(env.get(name) or "").strip()
        if v:
            return (unquote(v) if re.search(r"%[0-9A-Fa-f]{2}", v) else v), name
    return "", None


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    key, key_name = resolve_key(os.environ)
    previous = None
    if token:
        try:
            previous = private_store.get("kr-fuel", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-fuel-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(key, now=now, previous=previous)
    kinds = {}
    for v in doc["vehicles"]:
        if v.get("isNew"):
            kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    c = doc["checks"][0]
    print(f"::notice title=kr-fuel::상태 {doc['status']} · 키 {key_name or '없음'} · 전체 {c.get('rows')}행 · 출입처 {c.get('beatRows')}행 · "
          f"새 신고 {kinds}{' · 일괄 갱신' if doc.get('bulk') else ''}{' · ' + c['error'] if c.get('error') else ''}")
    if not token:
        print("::warning title=kr-fuel-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed" and previous:
        sys.exit("연비 목록 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-fuel", doc, token)
    print(f"::notice title=kr-fuel-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
