"""출입처 공장 부지 건축인허가 감시: 공장 증축·신축 허가는 공장등록 변경보다 몇 달 앞선다.

- 출입처 공장 목록은 kr-official(공장등록) 결과에서 읽는다(회사·공장명·도로명주소).
- 도로명주소 → 법정동코드·지번(행정안전부 도로명주소 검색API, business.juso.go.kr) → 건축인허가 기본개요(국토부 건축HUB)를
  같은 번지(본번 기준, 부번 전체)로 조회한다. 주소 변환 결과는 180일 재사용.
  (우체국 도로명주소 API는 GitHub 러너 같은 해외 서버에서 접속이 안 돼(10-29 연결 시간 초과) 쓰지 않는다.)
- 새 허가(관리허가대장 PK 처음 봄): 신축이고 연면적 1,000㎡ 이상 = A, 증축·그 밖 = B, 300㎡ 미만 = C.
  증축 허가의 연면적은 증축분이 아니라 건물 전체로 보인다(10-29 첫 실행: '본관동 장비출입구' 증축에 66,680㎡) — 크기로 A를 주지 않는다.
  이미 본 허가에 사용승인일이 새로 붙으면 B(준공).
- 키: 주소는 JUSO_CONFM_KEY(도로명주소 검색API 승인키), 건축인허가는 공공데이터포털 활용신청(15136267)이 된 키.
  공공데이터포털 키는 KR_FUEL_API_KEY → DATA_GO_KR_KEY → CUSTOMS_API_KEY → G2B_API_KEY 순서로 시도한다.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_building/v1"
JUSO = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
REGION = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
JUSO_HELP = "JUSO_CONFM_KEY 없음 — 도로명주소 검색API 승인키(business.juso.go.kr) 필요"
ARCH = "https://apis.data.go.kr/1613000/ArchPmsHubService/getApBasisOulnInfo"
UA = {"User-Agent": "newsroom-official-research/1.0", "Accept": "application/json, application/xml"}
KEY_NAMES = ("KR_FUEL_API_KEY", "DATA_GO_KR_KEY", "CUSTOMS_API_KEY", "G2B_API_KEY")
DATASETS = {"arch": "15136267 건축인허가", "region": "15077871 법정동코드"}
CONNECT_STREAK = 3  # this many connection failures in a row: the address service is unreachable, stop
PARCEL_TTL_DAYS = 180
SHOW_DAYS = 400
KEEP_MAX = 2000  # a full run keeps ~600 (10-29); trimmed rows are told apart from new ones by date (see run)
# GitHub job timeout is 30 min: stop looking up addresses at 13 min and permits at 25 min, save what was done
ADDR_BUDGET_S = 13 * 60
TOTAL_BUDGET_S = 25 * 60
BIG_AREA = 1000.0
SMALL_AREA = 300.0
RULES = [
    "건축인허가에는 건축주 이름이 없다. '출입처 공장과 같은 번지'일 뿐 — 건축주·용도·투자 규모는 회사·지자체 확인.",
    "허가는 착공·준공이 아니다(착공예정일·실제착공일·사용승인일 칸 확인). 첫 실행에 있던 허가는 기준선.",
    "증축 허가의 연면적은 증축분이 아니라 건물 전체일 수 있다 — 증축 규모는 허가서·지자체 확인. 증축은 B, 신축 1,000㎡ 이상만 A.",
    "같은 번지(본번)의 부번 전체를 본다. 공장과 부번까지 같은 필지면 그대로, 본번만 같은 다른 필지면 한 등급 낮춘다(이웃 회사 건물일 수 있음).",
    "큰 공장은 여러 번지에 걸쳐 있어 다른 번지의 허가는 못 볼 수 있다.",
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
def road_query(road):
    """'충청남도 당진시 송악읍 북부산업로 1228 (고대리)' → '충청남도 당진시 송악읍 북부산업로 1228'."""
    q = re.sub(r"\(.*?\)", " ", str(road or ""))
    q = re.split(r",", q)[0]
    m = re.match(r"(.*?\S+(?:로|길)\s*\d+(?:-\d+)?)", norm_space(q))
    return norm_space(m.group(1) if m else q)


class Juso:
    """도로명주소 검색API: one call gives the 법정동코드(admCd) and the lot number of a road address."""

    def __init__(self, key, get=None, sleep=time.sleep):
        self.key, self.sleep = key, sleep
        if get is None:
            import requests
            get = requests.get
        self.get = get

    def lookup(self, road):
        # the plant registry writes the 2026 merged province ('전남광주통합특별시 …'); if the full address finds nothing,
        # the address without its province is tried (matched on the end of the road address)
        tries = [road]
        parts = road.split(" ")
        if len(parts) > 3:
            tries.append(" ".join(parts[1:]))
        for q in tries:
            r = self.get(JUSO, params={"confmKey": self.key, "currentPage": 1, "countPerPage": 10, "keyword": q, "resultType": "json"},
                         headers=UA, timeout=30)
            if r.status_code != 200:
                raise RuntimeError(f"도로명주소 HTTP {r.status_code}")
            self.sleep(0.15)  # development key: 10 requests a second
            x = juso_pick(r.text, q)
            if x:
                return x
        return None


def juso_pick(text, road):
    try:
        res = json.loads(text).get("results") or {}
    except ValueError:
        raise RuntimeError("도로명주소 응답 형식 미상")
    common = res.get("common") or {}
    code = str(common.get("errorCode") or "0")
    if code in ("E0001", "E0014"):  # key not approved / development key expired
        raise Refused(f"도로명주소 승인키 거부({code} {common.get('errorMessage') or ''})".strip())
    if code != "0":
        raise RuntimeError(f"도로명주소 {code} {common.get('errorMessage') or ''}".strip()[:60])
    rows = [x for x in res.get("juso") or [] if len(str(x.get("admCd") or "")) == 10 and str(x.get("lnbrMnnm") or "").strip("0")]
    exact = [x for x in rows if norm_space(x.get("roadAddrPart1")) == road or norm_space(x.get("roadAddrPart1")).endswith(" " + road)]
    pick = exact or rows
    if not pick:
        return None
    if len({(x["admCd"], x.get("mtYn"), x.get("lnbrMnnm")) for x in pick}) > 1:
        raise RuntimeError(f"도로명 주소 후보 {len(pick)}개 — 번지 특정 불가")
    return pick[0]


# Some plants are registered with a lot address ('여수시 화치동 48-26번지', '청천동 199번지 외27필지', '신평리 산 12-10'):
# the lot is read from the address and only the 법정동코드 is looked up (행정표준코드, 15077871).
JIBUN_ADDR = re.compile(r"^(?P<area>.*?[가-힣0-9]+(?:동|리|가))\s*(?P<mt>산\s*)?(?P<bun>\d+)(?:\s*-\s*(?P<ji>\d+))?(?:\s*번지)?(?=\s|$|외|,)")
NO_LOT = re.compile(r"(?<![\d-])0(?:-0)?\s*번지")


def jibun_parts(addr):
    a = norm_space(re.sub(r"\(.*?\)", " ", str(addr or "")))
    if re.search(r"\S+(?:로|길)\s*\d+", a):
        return None  # a road address
    m = JIBUN_ADDR.match(a)
    if not m:
        return None
    return {"area": norm_space(m["area"]), "mt": bool(m["mt"]), "bun": m["bun"], "ji": m["ji"] or "0"}


def region_pick(text, q):
    try:
        d = json.loads(text)
    except ValueError:
        raise RuntimeError("법정동코드 응답 형식 미상")
    rows = []
    for part in d.get("StanReginCd") or []:
        rows += part.get("row") or []
    codes = {str(r.get("region_cd")) for r in rows if len(str(r.get("region_cd") or "")) == 10
             and (norm_space(r.get("locatadd_nm")) == q or norm_space(r.get("locatadd_nm")).endswith(" " + q))}
    if len(codes) > 1:
        raise RuntimeError(f"법정동코드 후보 {len(codes)}개")
    return codes.pop() if codes else None


def region_lookup(caller, area, cache):
    if area not in cache:
        tries = [area]
        parts = area.split(" ")
        if len(parts) > 2:
            tries.append(" ".join(parts[1:]))  # '전남광주통합특별시 여수시 화치동' → '여수시 화치동'
        code = None
        for q in tries:
            code = region_pick(caller.call("region", REGION, {"locatadd_nm": q, "type": "json", "numOfRows": 50, "pageNo": 1}), q)
            if code:
                break
        cache[area] = code
    return cache[area]


def parcel_for(fac, juso, now, caller=None, regions=None):
    addr = fac.get("rnAdres")
    road = road_query(addr)
    if not road:
        return {"road": "", "error": "주소 없음", "checkedAt": now}
    if NO_LOT.search(norm_space(addr)):
        return {"road": road, "error": "주소에 번지 없음(0번지)", "checkedAt": now}
    jp = jibun_parts(addr)
    if jp and caller is not None:
        code = region_lookup(caller, jp["area"], {} if regions is None else regions)
        if not code:
            return {"road": road, "error": "법정동코드 못 찾음", "checkedAt": now}
        lot = f"{jp['area']} {'산 ' if jp['mt'] else ''}{jp['bun']}{'-' + jp['ji'] if jp['ji'] != '0' else ''}"
        return {"road": road, "jibun": lot, "sigunguCd": code[:5], "bjdongCd": code[5:], "platGbCd": "1" if jp["mt"] else "0",
                "bun": jp["bun"].zfill(4), "ji": jp["ji"].zfill(4), "checkedAt": now, "from": "지번 주소"}
    x = juso.lookup(road)
    if not x:
        return {"road": road, "error": "지번 못 찾음", "checkedAt": now}
    adm = str(x["admCd"])
    return {"road": road, "jibun": norm_space(x.get("jibunAddr")), "sigunguCd": adm[:5], "bjdongCd": adm[5:],
            "platGbCd": "1" if str(x.get("mtYn")) == "1" else "0", "bun": str(x["lnbrMnnm"]).zfill(4),
            "ji": str(x.get("lnbrSlno") or "0").zfill(4), "checkedAt": now}


# ---------------------------------------------------------------- permits
def permits(text):
    return permits_page(text)[0]


def permits_page(text):
    """(rows, totalCount) of one 건축HUB JSON page."""
    if not (text or "").strip():
        raise RuntimeError("빈 응답")  # 10-29: HTTP 200 with an empty body, gone on an immediate retry
    d = json.loads(text)
    body = (d.get("response") or {}).get("body") or {}
    items = (body.get("items") or {}) if isinstance(body.get("items"), dict) else {}
    rows = items.get("item") or []
    rows = rows if isinstance(rows, list) else [rows]
    try:
        total = int(body.get("totalCount") or 0)
    except (TypeError, ValueError):
        total = 0
    return rows, total


def ymd(s):
    s = re.sub(r"\D", "", str(s or ""))
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s != "00000000" else None


def area(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


OK_CODES = {None, "00", "0", "000", "INFO-0", "NORMAL_SERVICE"}


def error_kind(e):
    """A short, fixed label for a failure (requests' own messages can carry the request URL with the key)."""
    name = type(e).__name__
    if name in ("ConnectTimeout", "ConnectionError", "ReadTimeout", "Timeout", "SSLError"):
        return name
    if isinstance(e, ValueError) and not isinstance(e, RuntimeError):
        return "응답 형식(JSON 아님)"
    return str(e)[:40] if isinstance(e, RuntimeError) else name


ARCH_PAGE = 100
ARCH_MAX_PAGES = 5
RETRY_WAITS = (2.0, 5.0)  # empty bodies, 503s and timeouts were momentary on 10-29


def arch_page(caller, params, page, sleep):
    for attempt in range(len(RETRY_WAITS) + 1):
        try:
            text = caller.call("arch", ARCH, {**params, "numOfRows": ARCH_PAGE, "pageNo": page, "_type": "json"})
            code = gateway_code(text)
            if code == "03":  # NODATA
                return [], 0
            if code not in OK_CODES:
                raise RuntimeError(f"응답 코드 {code}")
            return permits_page(text)
        except Refused:
            raise
        except Exception:  # noqa: BLE001
            if attempt == len(RETRY_WAITS):
                raise
            sleep(RETRY_WAITS[attempt])


def arch_rows(caller, params, sleep):
    """Every permit at one parcel (본번): a big plant's lot can hold more than one page (LS일렉트릭 청주 송정동 1 = 140)."""
    rows, total = arch_page(caller, params, 1, sleep)
    page = 1
    while len(rows) < total and page < ARCH_MAX_PAGES:
        page += 1
        more, _ = arch_page(caller, params, page, sleep)
        if not more:
            break
        rows += more
    return rows


def lot_of(r):
    """(본번, 부번) of a permit row: the bun/ji fields, else the end of 대지위치."""
    bun, ji = str(r.get("bun") or "").strip(), str(r.get("ji") or "").strip()
    if bun.isdigit():
        return int(bun), int(ji) if ji.isdigit() else 0
    m = re.search(r"(\d+)(?:-(\d+))?\s*번지\s*$", norm_space(r.get("platPlc")))
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def tier_of(p):
    a = p.get("totArea") or 0
    if a < SMALL_AREA:
        return "C"
    t = "A" if p.get("archGbCdNm") == "신축" and a >= BIG_AREA else "B"  # 증축: totArea is the whole building, not the addition
    if p.get("sameLot") is False:  # same 본번, another 부번: may be a neighbour's building
        t = {"A": "B", "B": "C"}[t]
    return t


def run(keys, factories, *, now, previous=None, get=None, sleep=time.sleep, clock=time.monotonic, juso_key=None):
    stamp = now.isoformat(timespec="seconds")
    # a stored '미설정' result (datasets not approved yet) is not a baseline: the first run that really queries is
    baseline = not (isinstance(previous, dict) and previous.get("baselineSince"))
    if (isinstance(previous, dict) and previous.get("permits") and not previous.get("baselineMarked")
            and not any(x.get("baseline") for x in previous["permits"]) and len({x.get("firstSeen") for x in previous["permits"]}) == 1):
        # 10-29: the first real run came after a '미설정' result and stored its existing permits as new
        for x in previous["permits"]:
            x["baseline"], x["isNew"] = True, False
    if isinstance(previous, dict) and previous.get("permits") and previous.get("baselineSince") and not previous.get("pagedMarked"):
        # 10-29 17:20: the first paged run (#362) saw pages 2+ of big lots for the first time and stored 248 existing
        # permits as new. Rows first seen in that run are a baseline.
        for x in previous["permits"]:
            if x.get("isNew") and x.get("firstSeen") == previous.get("generatedAt") and x.get("kind") == "새 허가":
                x["baseline"], x["isNew"] = True, False
    if not keys:
        return {"schema": SCHEMA, "generatedAt": stamp, "status": "unset", "permits": (previous or {}).get("permits") or [],
                "parcels": (previous or {}).get("parcels") or {}, "rules": RULES,
                "checks": [{"source": "건축인허가", "status": "unset", "error": "공공데이터포털 키 없음"}]}
    caller = Caller(keys, get=get, sleep=sleep)
    parcels = {k: dict(v) for k, v in ((previous or {}).get("parcels") or {}).items()}
    if isinstance(previous, dict) and previous.get("baselineSince") and not previous.get("archFirstMarked"):
        # state written before first-look stamps: a clean permit check means every resolved parcel was looked at
        arch = next((c for c in previous.get("checks") or [] if c.get("source") == "건축인허가"), {})
        if arch.get("status") == "ok":
            for p in parcels.values():
                if p.get("sigunguCd"):
                    p.setdefault("archFirst", previous.get("generatedAt"))
    if isinstance(previous, dict) and previous.get("pagedMarked") and not previous.get("archPagedMarked"):
        # 10-29 17:50: lots that failed in the first paged run were paged for the first time in the next one and their
        # page-2+ permits were stored as new (20). Those rows are a baseline; lots paged cleanly then are marked as paged.
        for x in previous.get("permits") or []:
            if x.get("isNew") and x.get("firstSeen") == previous.get("generatedAt") and x.get("kind") == "새 허가":
                x["baseline"], x["isNew"] = True, False
        failed = {str(x.get("parcel")) for x in previous.get("archFailed") or []}
        bad_groups = {(p.get("sigunguCd"), p.get("bjdongCd"), p.get("platGbCd"), p.get("bun")) for p in parcels.values() if str(p.get("jibun") or p.get("road")) in failed}
        for p in parcels.values():
            if p.get("sigunguCd") and p.get("archFirst") and (p.get("sigunguCd"), p.get("bjdongCd"), p.get("platGbCd"), p.get("bun")) not in bad_groups:
                p.setdefault("archPaged", previous.get("generatedAt"))
    ttl = (now - dt.timedelta(days=PARCEL_TTL_DAYS)).isoformat()
    checks, refused = [], None
    addr_ok = addr_fail = addr_left = streak = 0
    addr_errs = {}
    unreachable = False
    start = clock()
    juso = Juso(juso_key, get=get, sleep=sleep) if juso_key else None
    regions = {}
    for f in factories if juso else []:
        fid = f["id"]
        p = parcels.get(fid)
        if p and p.get("road") == road_query(f.get("rnAdres")) and str(p.get("checkedAt")) >= ttl and not p.get("error"):
            continue
        if clock() - start > ADDR_BUDGET_S:
            addr_left += 1  # done next run (resolved parcels are kept)
            continue
        if unreachable:
            addr_left += 1
            continue
        try:
            fresh = parcel_for(f, juso, stamp, caller, regions)
            if p and p.get("archFirst") and all(p.get(k) == fresh.get(k) for k in ("sigunguCd", "bjdongCd", "platGbCd", "bun")):
                fresh["archFirst"] = p["archFirst"]  # same parcel re-resolved after the TTL: not a first look
                if p.get("archPaged"):
                    fresh["archPaged"] = p["archPaged"]
            parcels[fid] = fresh
            streak = 0
            if fresh.get("error"):
                addr_errs[fresh["error"]] = addr_errs.get(fresh["error"], 0) + 1
            addr_ok += 0 if parcels[fid].get("error") else 1
            addr_fail += 1 if parcels[fid].get("error") else 0
        except Refused as e:
            refused = refused or str(e)
            break
        except Exception as e:  # noqa: BLE001
            # requests' connection errors carry the request URL: keep the class name only
            conn = type(e).__name__ in ("ConnectTimeout", "ConnectionError", "ReadTimeout", "Timeout")
            parcels[fid] = {"road": road_query(f.get("rnAdres")), "error": type(e).__name__ if conn else (str(e)[:60] or type(e).__name__), "checkedAt": stamp}
            k = error_kind(e)
            addr_errs[k] = addr_errs.get(k, 0) + 1
            addr_fail += 1
            streak = streak + 1 if conn else 0
            unreachable = streak >= CONNECT_STREAK
    if not juso:
        checks.append({"source": "주소 변환", "status": "unset", "error": JUSO_HELP})
    elif refused:
        checks.append({"source": "주소 변환", "status": "unset", "error": refused})
    elif unreachable:
        checks.append({"source": "주소 변환", "status": "failed", "returned": addr_ok, "failed": addr_fail,
                       "error": f"도로명주소 API 접속 실패(연속 {CONNECT_STREAK}회) — 남은 {addr_left}곳은 다음 실행"})
    elif addr_left:
        checks.append({"source": "주소 변환", "status": "partial", "returned": addr_ok, "failed": addr_fail,
                       "error": f"시간 한도 — 남은 {addr_left}곳은 다음 실행"})
    else:
        checks.append({"source": "주소 변환", "status": "ok", "returned": addr_ok, "failed": addr_fail,
                       **({"errors": dict(sorted(addr_errs.items(), key=lambda kv: -kv[1])[:5])} if addr_errs else {})})

    old = {x["id"]: x for x in (previous or {}).get("permits") or []}
    out = dict(old)
    by_parcel = {}
    for f in factories:
        p = parcels.get(f["id"]) or {}
        if p.get("sigunguCd"):
            by_parcel.setdefault((p["sigunguCd"], p["bjdongCd"], p["platGbCd"], p["bun"]), []).append(f)
    queried = fail = arch_left = 0
    arch_refused, errs, arch_failed = None, {}, []
    # rows trimmed at KEEP_MAX were the oldest: one older than everything kept is not new when it shows up again
    trim_floor = min((str(x.get("permitted") or "") for x in old.values()), default="") if len(old) >= KEEP_MAX else ""
    show_cut = (now - dt.timedelta(days=SHOW_DAYS)).date().isoformat()
    for (sg, bj, gb, bun), facs in by_parcel.items():
        if clock() - start > TOTAL_BUDGET_S:
            arch_left += 1
            continue
        try:
            rows = arch_rows(caller, {"sigunguCd": sg, "bjdongCd": bj, "platGbCd": gb, "bun": bun}, sleep)
            queried += 1
        except Refused as e:
            arch_refused = str(e)
            break
        except Exception as e:  # noqa: BLE001
            fail += 1
            k = error_kind(e)
            errs[k] = errs.get(k, 0) + 1
            p0 = parcels.get(facs[0]["id"]) or {}
            arch_failed.append({"company": facs[0]["company"], "plant": facs[0].get("cmpnyNm"), "parcel": p0.get("jibun") or p0.get("road"), "error": k})
            continue
        own_lots = {(int((parcels.get(f["id"]) or {}).get("bun") or 0), int((parcels.get(f["id"]) or {}).get("ji") or 0)) for f in facs}
        # permits at a parcel looked at for the first time (first run, a parcel left over by the time limit,
        # a newly registered plant) are its baseline, not new
        # a lot is fully seen only after one clean query of all its pages (archPaged): until then its rows are a baseline
        first_look = baseline or any(not (parcels.get(f["id"]) or {}).get("archPaged") for f in facs)
        for f in facs:
            parcels[f["id"]].setdefault("archFirst", stamp)
            parcels[f["id"]].setdefault("archPaged", stamp)
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
            lot = lot_of(r)
            rec["sameLot"] = None if lot is None else lot in own_lots
            if (rec["permitted"] or "0000") < show_cut and pid not in old:
                continue  # old permits are not kept
            if pid not in old and trim_floor and (rec["permitted"] or "0000") < trim_floor:
                continue  # trimmed at KEEP_MAX before, not new
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
        checks.append({"source": "건축인허가", "status": "unset" if refused or not juso else "failed",
                       "error": "조회할 번지 없음 — 주소 변환 " + ("승인키 등록 후" if refused or not juso else "실패")})
    elif arch_refused:
        checks.append({"source": "건축인허가", "status": "unset", "error": f"활용신청 필요({DATASETS['arch']})"})
    else:
        kinds = ", ".join(f"{k} {n}" for k, n in sorted(errs.items(), key=lambda kv: -kv[1])[:3])
        err = "; ".join(e for e in (f"{fail}개 번지 조회 실패({kinds})" if fail else "", f"시간 한도 — 남은 {arch_left}개 번지 미조회" if arch_left else "") if e)
        checks.append({"source": "건축인허가", "status": "ok" if not err else "partial", "returned": queried, **({"error": err} if err else {})})
    current = {f["id"] for f in factories}
    for pid, x in out.items():
        if pid in old and x is old[pid]:
            x["isNew"] = False
        # a plant dropped from the plant list (closed, renamed, or a name rule tightened — 10-29 '한국지엠디'):
        # its permits are kept (so they never come back as new) but hidden
        if current:
            if x.get("factoryId") in current:
                x.pop("orphan", None)
            else:
                x["orphan"] = True
    kept = sorted(out.values(), key=lambda x: (str(x.get("permitted") or ""), x["id"]), reverse=True)[:KEEP_MAX]
    statuses = {c["status"] for c in checks}
    status = ("unset" if statuses == {"unset"} else "failed" if statuses <= {"failed", "unset"} and "failed" in statuses
              else "partial" if statuses - {"ok"} else "complete")
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks, "permits": kept, "parcels": parcels,
            "rules": RULES, "plants": len(factories), "archFailed": arch_failed[:80],
            "unresolved": [{"company": f["company"], "plant": f.get("cmpnyNm"), "road": road_query(f.get("rnAdres")),
                            "error": (parcels.get(f["id"]) or {}).get("error") or "미조회"}
                           for f in factories if not (parcels.get(f["id"]) or {}).get("sigunguCd")][:80], "parcelsResolved": sum(1 for p in parcels.values() if p.get("sigunguCd")), "baselineMarked": True, "archFirstMarked": True, "pagedMarked": True, "archPagedMarked": True,
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
    doc = run(resolve_keys(), factories, now=now, previous=previous, juso_key=os.environ.get("JUSO_CONFM_KEY", "").strip() or None)
    new = [x for x in doc["permits"] if x.get("isNew")]
    print(f"::notice title=kr-building::상태 {doc['status']} · 공장 {doc.get('plants')} · 번지 확인 {doc.get('parcelsResolved')} · "
          + " · ".join(f"{c['source']} {c['status']}{('(' + c['error'] + ')') if c.get('error') else ''}"
                       + (f" 이번 {c['returned']}·실패 {c['failed']}" if "failed" in c else "")
                       + (f" {c['errors']}" if c.get("errors") else "") for c in doc["checks"])
          + f" · 다른 필지(같은 본번) {sum(1 for x in doc['permits'] if x.get('sameLot') is False)}"
          + f" · 공장 목록에서 빠짐(숨김) {sum(1 for x in doc['permits'] if x.get('orphan'))}"
          + f" · 지번 주소로 번지 확인 {sum(1 for p in doc.get('parcels', {}).values() if p.get('from') == '지번 주소')}"
          + f" · 새 허가 {len(new)} · 보관 {len(doc['permits'])}")
    if doc["status"] == "failed":
        sys.exit("건축인허가 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-building", doc, token)
    print(f"::notice title=kr-building-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
