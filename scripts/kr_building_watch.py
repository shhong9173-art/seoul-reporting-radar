"""출입처 공장 부지 건축인허가 감시: 공장 증축·신축 허가는 공장등록 변경보다 몇 달 앞선다.

- 출입처 공장 목록은 kr-official(공장등록) 결과에서 읽는다(회사·공장명·도로명주소).
- 도로명주소 → 지번(우체국 도로명주소 조회) → 법정동코드(행정표준코드) → 건축인허가 기본개요(국토부 건축HUB)를
  같은 번지(본번 기준, 부번 전체)로 조회한다. 주소 변환 결과는 180일 재사용.
- 새 허가(관리허가대장 PK 처음 봄): 신축·증축이고 연면적 1,000㎡ 이상 = A, 그 밖 = B, 300㎡ 미만 = C.
  이미 본 허가에 사용승인일이 새로 붙으면 B(준공).
- 공공데이터포털 활용신청(15136267 건축인허가, 15000124 우체국 도로명주소, 15077871 법정동코드)이 된 키여야 한다.
  키는 KR_FUEL_API_KEY → DATA_GO_KR_KEY → CUSTOMS_API_KEY → G2B_API_KEY 순서로 데이터마다 시도한다.
- 건축허가는 회사 이름이 없다(건축주 비공개). 같은 번지 = 그 공장 부지라는 뜻일 뿐, 건축주·용도는 회사·지자체 확인.
- 결과는 기자 전용 저장소(kr-building)로만. 공개 로그는 건수만. 조회 실패·미설정은 0건이 아니다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_building/v1"
EPOST = "http://openapi.epost.go.kr/postal/retrieveNewAdressAreaCdService/retrieveNewAdressAreaCdService/getNewAddressListAreaCd"
REGION = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
ARCH = "https://apis.data.go.kr/1613000/ArchPmsHubService/getApBasisOulnInfo"
UA = {"User-Agent": "newsroom-official-research/1.0", "Accept": "application/json, application/xml"}
KEY_NAMES = ("KR_FUEL_API_KEY", "DATA_GO_KR_KEY", "CUSTOMS_API_KEY", "G2B_API_KEY")
DATASETS = {"epost": "15000124 우체국 도로명주소", "region": "15077871 법정동코드", "arch": "15136267 건축인허가"}
PARCEL_TTL_DAYS = 180
SHOW_DAYS = 400
KEEP_MAX = 600
# GitHub job timeout is 30 min: stop looking up addresses at 13 min and permits at 25 min, save what was done
ADDR_BUDGET_S = 13 * 60
TOTAL_BUDGET_S = 25 * 60
BIG_AREA = 1000.0
SMALL_AREA = 300.0
RULES = [
    "건축인허가에는 건축주 이름이 없다. '출입처 공장과 같은 번지'일 뿐 — 건축주·용도·투자 규모는 회사·지자체 확인.",
    "허가는 착공·준공이 아니다(착공예정일·실제착공일·사용승인일 칸 확인). 첫 실행에 있던 허가는 기준선.",
    "같은 번지(본번)의 부번 전체를 본다. 큰 공장은 여러 번지에 걸쳐 있어 다른 번지의 허가는 못 볼 수 있다.",
]


class Refused(Exception):
    """The gateway refused this key for this dataset (code 30 etc.) — try the next key."""


def norm_space(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def resolve_keys(env=None):
    env = os.environ if env is None else env
    out, seen = [], set()
    for name in KEY_NAMES:
        v = urllib.parse.unquote((env.get(name) or "").strip())
        if v and v not in seen:
            seen.add(v)
            out.append((name, v))
    return out


def gateway_code(text):
    m = re.search(r"<(?:returnReasonCode|resultCode|returnCode)>\s*([^<]+)", text or "") or \
        re.search(r'"(?:returnReasonCode|resultCode|returnCode)"\s*:\s*"?([^",}\s]+)', text or "")
    return m.group(1).strip() if m else None


class Caller:
    """Per-dataset key choice: the first key the gateway accepts is kept for the run."""

    def __init__(self, keys, get=None, sleep=time.sleep):
        self.keys, self.sleep, self.chosen, self.refused = keys, sleep, {}, {}
        if get is None:
            import requests
            get = requests.get
        self.get = get

    def call(self, dataset, url, params):
        order = [self.chosen[dataset]] if dataset in self.chosen else self.keys
        last = None
        for name, key in order:
            r = self.get(url, params={"serviceKey": key, **params}, headers=UA, timeout=40)
            text = r.text or ""
            code = gateway_code(text)
            if r.status_code in (401, 403) or code in ("30", "31", "20", "SERVICE_KEY_IS_NOT_REGISTERED_ERROR"):
                self.refused.setdefault(dataset, set()).add(name)
                last = f"{name} 거부({r.status_code}/{code})"
                continue
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            self.chosen[dataset] = (name, key)
            self.sleep(0.3)
            return text
        raise Refused(last or "열쇠 없음")


# ---------------------------------------------------------------- address → parcel
JIBUN = re.compile(r"^(.*?[가-힣0-9]+(?:동|리|가))\s+(산\s*)?(\d+)(?:-(\d+))?")


def road_query(road):
    """'충청남도 당진시 송악읍 북부산업로 1228 (고대리)' → '충청남도 당진시 송악읍 북부산업로 1228'."""
    q = re.sub(r"\(.*?\)", " ", str(road or ""))
    q = re.split(r",", q)[0]
    m = re.match(r"(.*?\S+(?:로|길)\s*\d+(?:-\d+)?)", norm_space(q))
    return norm_space(m.group(1) if m else q)


def epost_jibun(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise RuntimeError("우체국 응답 형식 미상")
    if (root.findtext(".//successYN") or "Y").strip() == "N" and (root.findtext(".//returnCode") or "") not in ("", "00"):
        raise RuntimeError(f"우체국 {root.findtext('.//returnCode')} {root.findtext('.//errMsg')}")
    for it in root.iter("newAddressListAreaCd"):
        lnm = norm_space(it.findtext("lnmAdres"))
        if lnm:
            return lnm
    return None


def split_jibun(lnm):
    m = JIBUN.match(re.sub(r"\s*\(.*$", "", lnm or ""))
    if not m:
        return None
    return {"dong": norm_space(m.group(1)), "platGbCd": "1" if m.group(2) else "0", "bun": m.group(3), "ji": m.group(4) or "0"}


def region_code(text, dong):
    try:
        d = json.loads(text)
    except ValueError:
        raise RuntimeError("법정동코드 응답 형식 미상")
    rows = []
    for part in d.get("StanReginCd") or []:
        rows += part.get("row") or []
    for r in rows:
        if norm_space(r.get("locatadd_nm")) == dong and len(str(r.get("region_cd") or "")) == 10:
            return str(r["region_cd"])
    return None


def parcel_for(fac, caller, now, regions=None):
    road = road_query(fac.get("rnAdres"))
    if not road:
        return {"road": "", "error": "주소 없음", "checkedAt": now}
    lnm = epost_jibun(caller.call("epost", EPOST, {"searchSe": "road", "srchwrd": road, "countPerPage": 5, "currentPage": 1}))
    if not lnm:
        return {"road": road, "error": "지번 못 찾음", "checkedAt": now}
    j = split_jibun(lnm)
    if not j:
        return {"road": road, "jibun": lnm, "error": "지번 형식 미상", "checkedAt": now}
    regions = {} if regions is None else regions
    if j["dong"] not in regions:  # many plants share one dong
        regions[j["dong"]] = region_code(caller.call("region", REGION, {"locatadd_nm": j["dong"], "type": "json", "numOfRows": 20, "pageNo": 1}), j["dong"])
    code = regions[j["dong"]]
    if not code:
        return {"road": road, "jibun": lnm, "error": "법정동코드 못 찾음", "checkedAt": now}
    return {"road": road, "jibun": lnm, "sigunguCd": code[:5], "bjdongCd": code[5:], "platGbCd": j["platGbCd"],
            "bun": j["bun"].zfill(4), "ji": j["ji"].zfill(4), "checkedAt": now}


# ---------------------------------------------------------------- permits
def permits(text):
    d = json.loads(text)
    body = (d.get("response") or {}).get("body") or {}
    items = (body.get("items") or {}) if isinstance(body.get("items"), dict) else {}
    rows = items.get("item") or []
    return rows if isinstance(rows, list) else [rows]


def ymd(s):
    s = re.sub(r"\D", "", str(s or ""))
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s != "00000000" else None


def area(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tier_of(p):
    a = p.get("totArea") or 0
    if a < SMALL_AREA:
        return "C"
    return "A" if p.get("archGbCdNm") in ("신축", "증축") and a >= BIG_AREA else "B"


def run(keys, factories, *, now, previous=None, get=None, sleep=time.sleep, clock=time.monotonic):
    stamp = now.isoformat(timespec="seconds")
    # a stored '미설정' result (datasets not approved yet) is not a baseline: the first run that really queries is
    baseline = not (isinstance(previous, dict) and previous.get("baselineSince"))
    if (isinstance(previous, dict) and previous.get("permits") and not previous.get("baselineMarked")
            and not any(x.get("baseline") for x in previous["permits"]) and len({x.get("firstSeen") for x in previous["permits"]}) == 1):
        # 10-29: the first real run came after a '미설정' result and stored its existing permits as new
        for x in previous["permits"]:
            x["baseline"], x["isNew"] = True, False
    if not keys:
        return {"schema": SCHEMA, "generatedAt": stamp, "status": "unset", "permits": (previous or {}).get("permits") or [],
                "parcels": (previous or {}).get("parcels") or {}, "rules": RULES,
                "checks": [{"source": "건축인허가", "status": "unset", "error": "공공데이터포털 키 없음"}]}
    caller = Caller(keys, get=get, sleep=sleep)
    parcels = dict((previous or {}).get("parcels") or {})
    ttl = (now - dt.timedelta(days=PARCEL_TTL_DAYS)).isoformat()
    checks, refused = [], None
    addr_ok = addr_fail = addr_left = 0
    start, regions = clock(), {}
    for f in factories:
        fid = f["id"]
        p = parcels.get(fid)
        if p and p.get("road") == road_query(f.get("rnAdres")) and str(p.get("checkedAt")) >= ttl and not p.get("error"):
            continue
        if clock() - start > ADDR_BUDGET_S:
            addr_left += 1  # done next run (resolved parcels are kept)
            continue
        try:
            fresh = parcel_for(f, caller, stamp, regions)
            if p and p.get("archFirst") and all(p.get(k) == fresh.get(k) for k in ("sigunguCd", "bjdongCd", "platGbCd", "bun")):
                fresh["archFirst"] = p["archFirst"]  # same parcel re-resolved after the TTL: not a first look
            parcels[fid] = fresh
            addr_ok += 0 if parcels[fid].get("error") else 1
            addr_fail += 1 if parcels[fid].get("error") else 0
        except Refused as e:
            refused = refused or str(e)
            break
        except Exception as e:  # noqa: BLE001
            parcels[fid] = {"road": road_query(f.get("rnAdres")), "error": str(e)[:60] or type(e).__name__, "checkedAt": stamp}
            addr_fail += 1
    if refused:
        missing = [DATASETS[d] for d in ("epost", "region") if d in caller.refused and d not in caller.chosen]
        checks.append({"source": "주소 변환", "status": "unset", "error": f"활용신청 필요({', '.join(missing) or refused})"})
    elif addr_left:
        checks.append({"source": "주소 변환", "status": "partial", "returned": addr_ok, "failed": addr_fail,
                       "error": f"시간 한도 — 남은 {addr_left}곳은 다음 실행"})
    else:
        checks.append({"source": "주소 변환", "status": "ok", "returned": addr_ok, "failed": addr_fail})

    old = {x["id"]: x for x in (previous or {}).get("permits") or []}
    out = dict(old)
    by_parcel = {}
    for f in factories:
        p = parcels.get(f["id"]) or {}
        if p.get("sigunguCd"):
            by_parcel.setdefault((p["sigunguCd"], p["bjdongCd"], p["platGbCd"], p["bun"]), []).append(f)
    queried = fail = arch_left = 0
    arch_refused = None
    show_cut = (now - dt.timedelta(days=SHOW_DAYS)).date().isoformat()
    for (sg, bj, gb, bun), facs in by_parcel.items():
        if clock() - start > TOTAL_BUDGET_S:
            arch_left += 1
            continue
        try:
            text = caller.call("arch", ARCH, {"sigunguCd": sg, "bjdongCd": bj, "platGbCd": gb, "bun": bun, "numOfRows": 100, "pageNo": 1, "_type": "json"})
            rows = permits(text)
            queried += 1
        except Refused as e:
            arch_refused = str(e)
            break
        except Exception:  # noqa: BLE001
            fail += 1
            continue
        # permits at a parcel looked at for the first time (first run, a parcel left over by the time limit,
        # a newly registered plant) are its baseline, not new
        first_look = baseline or any(not (parcels.get(f["id"]) or {}).get("archFirst") for f in facs)
        for f in facs:
            parcels[f["id"]].setdefault("archFirst", stamp)
        for r in rows:
            pk = str(r.get("mgmPmsrgstPk") or "")
            if not pk:
                continue
            pid = f"bld:{pk}"
            rec = {"id": pid, "company": facs[0]["company"], "companies": sorted({x["company"] for x in facs}),
                   "factory": facs[0].get("cmpnyNm"), "factoryId": facs[0]["id"], "plot": norm_space(r.get("platPlc")),
                   "bldNm": norm_space(r.get("bldNm")) or None, "archGbCdNm": norm_space(r.get("archGbCdNm")) or None,
                   "mainPurpsCdNm": norm_space(r.get("mainPurpsCdNm")) or None, "totArea": area(r.get("totArea")),
                   "archArea": area(r.get("archArea")), "permitted": ymd(r.get("archPmsDay")), "startPlanned": ymd(r.get("stcnsSchedDay")),
                   "started": ymd(r.get("realStcnsDay")), "useApproved": ymd(r.get("useAprDay"))}
            if (rec["permitted"] or "0000") < show_cut and pid not in old:
                continue  # old permits are not kept
            prev = old.get(pid)
            rec["kind"] = "새 허가"
            rec["firstSeen"] = prev["firstSeen"] if prev else stamp
            rec["baseline"] = bool(prev.get("baseline")) if prev else first_look
            rec["isNew"] = not prev and not first_look
            rec["tier"] = tier_of(rec)
            if prev and rec["useApproved"] and not prev.get("useApproved"):
                rec["kind"], rec["isNew"], rec["tier"], rec["changedAt"] = "사용승인(준공)", True, "B", stamp
            elif prev:
                rec["changedAt"] = prev.get("changedAt")
            out[pid] = rec
    if not by_parcel:
        # nothing to query is not '0 permits': the parcels are unknown
        checks.append({"source": "건축인허가", "status": "unset" if refused else "failed",
                       "error": "조회할 번지 없음 — 주소 변환 " + ("활용신청 후" if refused else "실패")})
    elif arch_refused:
        checks.append({"source": "건축인허가", "status": "unset", "error": f"활용신청 필요({DATASETS['arch']})"})
    else:
        err = "; ".join(e for e in (f"{fail}개 번지 조회 실패" if fail else "", f"시간 한도 — 남은 {arch_left}개 번지 미조회" if arch_left else "") if e)
        checks.append({"source": "건축인허가", "status": "ok" if not err else "partial", "returned": queried, **({"error": err} if err else {})})
    for pid, x in out.items():
        if pid in old and x is old[pid]:
            x["isNew"] = False
    kept = sorted(out.values(), key=lambda x: (str(x.get("permitted") or ""), x["id"]), reverse=True)[:KEEP_MAX]
    statuses = {c["status"] for c in checks}
    status = ("unset" if statuses == {"unset"} else "failed" if statuses <= {"failed", "unset"} and "failed" in statuses
              else "partial" if statuses - {"ok"} else "complete")
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "permits": kept, "parcels": parcels,
            "rules": RULES, "plants": len(factories), "parcelsResolved": sum(1 for p in parcels.values() if p.get("sigunguCd")), "baselineMarked": True,
            "baselineSince": (previous or {}).get("baselineSince") or (stamp if status != "unset" else None)}


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not token:
        print("::warning title=kr-building::MCP_ACCESS_TOKEN 미설정 — 공장 목록을 읽을 수 없어 실행하지 않음")
        return
    official = private_store.get("kr-official", token) or {}
    factories = [f for f in official.get("factories") or [] if f.get("id") and f.get("rnAdres") and not f.get("stale")]
    previous = None
    try:
        previous = private_store.get("kr-building", token)
    except private_store.StoreError as e:
        print(f"::warning title=kr-building-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(resolve_keys(), factories, now=now, previous=previous)
    new = [x for x in doc["permits"] if x.get("isNew")]
    print(f"::notice title=kr-building::상태 {doc['status']} · 공장 {doc.get('plants')} · 번지 확인 {doc.get('parcelsResolved')} · "
          + " · ".join(f"{c['source']} {c['status']}{('(' + c['error'] + ')') if c.get('error') else ''}" for c in doc["checks"])
          + f" · 새 허가 {len(new)} · 보관 {len(doc['permits'])}")
    if doc["status"] == "failed":
        sys.exit("건축인허가 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-building", doc, token)
    print(f"::notice title=kr-building-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
