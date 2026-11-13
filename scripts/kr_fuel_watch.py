"""국내 자동차 표시연비 신고 감시: 출입처 브랜드(국산 5사·수입 법인)의 새 연비 신고.

- 원천: 공공데이터포털 '한국에너지공단_자동차 표시연비 목록 조회 서비스'(데이터 15139827, 개발계정 자동승인·일 10,000회)
  GET apis.data.go.kr/B553530/CAREFF/CAREFF_LIST — 업체명·모델명·출시년도·연료·배기량·변속기·표시/도심/고속 연비·CO2·등급·
  1회 충전 주행거리·등록일(DATA_REG_DT). 에너지공단 누리집(bpms.kemco.or.kr)은 해외 러너에서 접속이 안 돼 이 API를 쓴다.
- 전체 목록을 1,000행씩 받아 업체명·모델명으로 출입처 브랜드만 고른다. 처음 보는 행(사양 묶음)만 새 신고. 첫 실행은 기준선.
- 분류: 같은 업체에 처음 보는 모델명이면 '새 모델명', 전기차 1회 충전 주행거리가 같은 모델명의 이전 행과 다르면 '주행거리 변화',
  나머지는 '사양·연식 추가'. 한 번에 너무 많이 바뀌면(자료 일괄 갱신) 모두 참고로만 둔다.
- 연비 신고는 출시 전에 나오는 경우가 많지만 출시 확정이 아니다. 결과는 기자 전용 저장소(kr-fuel)로만, 공개 로그는 건수만.
- 키가 이 데이터에 활용신청되지 않았으면 '미설정(활용신청 필요)'로 남긴다 — 0건이 아니다.
- 같은 저장소(kr-fuel)의 freeRepair 구역에 자동차리콜센터 '무상점검·수리' 게시판 새 글(kr_free_repair.py, 11-14)을 함께 싣는다.
  게시판은 낮에도 본다(평일 11:30·14:30·16:30) — 그 실행들은 연비 목록을 다시 받지 않는다(18시간 안에 정상으로 받았으면 건너뜀).
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
            plain = (r.text or "").strip()
            if not msg and plain.startswith("{"):
                # apis.data.go.kr의 새 게이트웨이는 403 거부를 JSON으로 준다(10-28 국내 접속 확인: 30 등록되지 않은 서비스키).
                try:
                    h = (json.loads(plain).get("OpenAPI_ServiceResponse") or {}).get("cmmMsgHeader") or {}
                    msg = f"{h.get('returnReasonCode', '')} {h.get('errMsg') or h.get('returnAuthMsg') or ''}".strip()[:80]
                except (ValueError, AttributeError):
                    msg = ""
            if not msg and re.fullmatch(r"[A-Za-z _.]{1,40}", plain):  # 'Forbidden' 같은 짧은 문구만(키·주소 없음)
                msg = plain
            if not msg:
                msg = f"본문 형식 미상({len(plain)}자)"  # 해외 접속 차단 등 다른 거부와 구분하려고 길이만
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


FUEL_EVERY_HOURS = 18


def fuel_is_fresh(previous, now):
    """연비 목록을 이 시간 안에 정상으로 받았으면 True — 낮 실행(무상점검 게시판용)에서 연비 API를 다시 부르지 않는다."""
    if not isinstance(previous, dict) or not previous.get("fuelAt") or not isinstance(previous.get("vehicles"), list):
        return False
    fuel_check = next((c for c in previous.get("checks", []) if c.get("source") == SOURCE), {})
    if fuel_check.get("status") != "ok":
        return False
    try:
        age = (now - dt.datetime.fromisoformat(str(previous["fuelAt"]))).total_seconds() / 3600
    except (TypeError, ValueError):
        return False
    return 0 <= age < FUEL_EVERY_HOURS


def resolve_keys(env):
    """Every configured data.go.kr account key, in order (several accounts may exist; the dataset may be approved on only one)."""
    out, seen = [], set()
    # KR_FUEL_API_KEY: 연비 자료만 다른 공공데이터포털 계정에서 승인받았을 때(다른 감시의 키는 건드리지 않음)
    for name in ("KR_FUEL_API_KEY", "DATA_GO_KR_KEY", "CUSTOMS_API_KEY", "G2B_API_KEY"):
        v = str(env.get(name) or "").strip()
        if v:
            v = unquote(v) if re.search(r"%[0-9A-Fa-f]{2}", v) else v
            if v not in seen:
                seen.add(v)
                out.append((v, name))
    return out


def run_any(keys, **kw):
    """Try each key until one is not refused for this dataset. Returns (doc, key name, refused names)."""
    refused = []
    for key, name in keys:
        doc = run(key, **kw)
        if doc["status"] != "unset":
            return doc, name, refused
        refused.append(name)
    return (doc if keys else run("", **kw)), None, refused


def build(previous, now, keys, *, get=None, session=None, sleep=time.sleep):
    """한 번 실행의 저장 문서. 돌려줌: (doc, {keyName, refused, fuelFailed, free}).
    연비 목록과 무상점검·수리 게시판(kr_free_repair.py)은 따로 읽는다 — 한쪽이 실패해도 다른 쪽은 저장한다."""
    import kr_free_repair
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else None
    if fuel_is_fresh(prev, now):
        # 연비 쪽은 아침 결과 그대로([신규] 표시도 그대로 — 다시 받지 않았으니 '직전 수집 뒤 새 신고'가 바뀌지 않았다)
        doc, key_name, refused = dict(prev, generatedAt=stamp, status="complete"), "건너뜀(연비 목록은 오늘 받음)", []
        doc["checks"] = [c for c in prev.get("checks", []) if c.get("source") == SOURCE][:1]
    else:
        doc, key_name, refused = run_any(keys, now=now, previous=prev, get=get, sleep=sleep)
        doc["fuelAt"] = stamp if doc["status"] == "complete" else (prev or {}).get("fuelAt")
    if refused:
        doc["checks"][0]["keysRefused"] = refused  # 이름만(값 없음)
    if session is None:
        import requests
        session = requests.Session()
    free, fcheck = kr_free_repair.collect((prev or {}).get("freeRepair"), now, session, sleep=sleep)
    if free:
        doc["freeRepair"] = free
    doc["checks"] = [doc["checks"][0], fcheck]
    fuel_failed = doc["status"] == "failed" and bool(prev)
    if fuel_failed:
        # 연비 목록만 실패: 연비 쪽은 이전 결과 그대로 두고(0건 아님) 무상점검 구역과 실패 표시만 새로 저장한다
        doc = {**prev, "generatedAt": stamp, "status": "partial", "checks": doc["checks"], **({"freeRepair": doc["freeRepair"]} if doc.get("freeRepair") else {})}
    elif doc["status"] == "complete" and fcheck["status"] != "ok":
        doc["status"] = "partial"
    return doc, {"keyName": key_name, "refused": refused, "fuelFailed": fuel_failed, "free": free}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    keys = resolve_keys(os.environ)
    previous = None
    if token:
        try:
            previous = private_store.get("kr-fuel", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-fuel-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc, info = build(previous, now, keys)
    fcheck = doc["checks"][1]
    fitems = (info["free"] or {}).get("items", [])
    print(f"::notice title=kr-free-repair::무상점검·수리 게시판 상태 {fcheck['status']} · 목록 {fcheck.get('pages', 0)}쪽 {fcheck.get('returned', 0)}건(전체 {fcheck.get('total')}) · "
          f"새 글 {fcheck.get('newPosts', 0)}(출입처 {fcheck.get('newBeat', 0)}) · 상세 {fcheck.get('detailsRead', 0)} · 읽기 대기 {fcheck.get('pending', 0)} · "
          f"저장 {len(fitems)}건(A {sum(1 for x in fitems if x.get('tier') == 'A')}·B {sum(1 for x in fitems if x.get('tier') == 'B')})"
          f"{' · ' + fcheck['robots'] if fcheck.get('robots') else ''}{' · ' + fcheck['error'] if fcheck.get('error') else ''}")
    kinds = {}
    for v in doc.get("vehicles", []):
        if v.get("isNew"):
            kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    c = doc["checks"][0]
    refused_note = f" (거부: {info['refused']})" if info["refused"] else ""
    print(f"::notice title=kr-fuel::상태 {doc['status']} · 키 {info['keyName'] or '없음'}{refused_note} · 전체 {c.get('rows')}행 · 출입처 {c.get('beatRows')}행 · "
          f"새 신고 {kinds}{' · 일괄 갱신' if doc.get('bulk') else ''}{' · ' + c['error'] if c.get('error') else ''}")
    if not token:
        print("::warning title=kr-fuel-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    status = private_store.put("kr-fuel", doc, token)
    print(f"::notice title=kr-fuel-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)
    if info["fuelFailed"]:
        sys.exit("연비 목록 조회 실패 — 연비는 이전 결과 유지(0건 아님), 무상점검 구역은 저장함")


if __name__ == "__main__":
    main()
