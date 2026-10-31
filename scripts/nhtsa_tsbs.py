"""미국 NHTSA 제조사 통신(Manufacturer Communications, TSBS_RECEIVED_<YYYY-YYYY>.zip) — 현대차·기아·제네시스·한국GM 생산 차종의
서비스 캠페인·보증 연장·안전 관련 서비스 공지. 리콜이 아닌 '조용한 수리'가 먼저 보이는 곳이다.

탐침(11-01): 2025-2026 파일 12MB(압축)·416MB(풀면)·81만 줄·14칸(탭), 날마다 갱신(Last-Modified 10-31).
통신 하나(NHTSA ID, 8자리 숫자)가 차종×연식×부품마다 한 줄씩 나온다 — 건수는 NHTSA ID로 센다. 최근 120일 출입처 통신 241건
(서비스 공지 83·보증 프로그램 77·서비스 캠페인 42·배출가스 19·기타 16·OTA 4), 드라이런 2초·메모리 59MB.
통신 종류 칸은 'Service Bulletin/Repair Instructions'처럼 빗금 둘레에 띄어쓰기가 없다(설명 문서와 다름).
문서 PDF: static.nhtsa.gov/odi/tsbs/<추가 연도>/MC-<NHTSA ID>-0001.pdf (탐침 3건 200 application/pdf).
칸(TSBS.txt): 1 NHTSA ID, 2 대체 공지 번호, 3 파일 추가일, 4 TSB/문서 번호, 5 제조사 통신일, 6 제조사 캠페인 번호/소프트웨어 버전,
7 통신 종류(Service Bulletin / Repair Instructions · Service Campaign · Warranty Program / Extension · Over The Air · Emissions · Other),
8 제조사, 9 차명, 10 연식, 11 NHTSA 부품, 12 제조사 부품 계통, 13 제조사 부품 하위 계통, 14 요약.
풀면 400MB가 넘어 메모리에 올리지 않고 줄 단위로 읽는다.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import zipfile

URL = "https://static.nhtsa.gov/odi/ffdd/tsbs/TSBS_RECEIVED_{span}.zip"
PDF = "https://static.nhtsa.gov/odi/tsbs/{year}/MC-{id}-0001.pdf"
WINDOW_DAYS = 120       # 파일 추가일 기준 이 안의 통신만 본다
KEEP = 300
SEEN_MAX = 6000
ID, REPL, ADDED, DOC, MFR_DATE, CAMPAIGN, CTYPE, MAKE, MODEL, YEAR, COMP, SYS, SUBSYS, SUMMARY = range(14)
BRANDS = {"HYUNDAI": ("현대차", "현대차"), "GENESIS": ("현대차", "제네시스"), "KIA": ("기아", "기아")}
GM_KOREA = re.compile(r"^(?:TRAX|TRAILBLAZER|ENVISTA|ENCORE GX)\b", re.I)
# 등급 낱말은 부품 분류 칸이 아니라 요약 원문에서만 찾는다 — 'ENGINE' 분류 칸에 공기 플랩 배선, '모터' 낱말에 공조 송풍 모터가 걸렸다(11-01 운영).
EXTENSION = re.compile(r"WARRANTY EXTENSION|EXTEND(?:S|ING|ED)? (?:THE )?(?:NEW VEHICLE LIMITED |POWERTRAIN |LIMITED )?WARRANTY|SPECIAL COVERAGE|"
                       r"EXTENDED (?:LIMITED )?WARRANTY|\b1[05] YEARS? ?/ ?[\d,]+ MILES", re.I)
SERIOUS = re.compile(r"\bENGINE (?:FAILURE|DAMAGE|REPLACEMENT|ASSEMBLY|SEIZ\w*|KNOCK\w*|BEARING\w*)|LONG BLOCK|SHORT BLOCK|TURBOCHARGER|"
                     r"CONNECTING ROD|PISTON|OIL CONSUMPTION|HIGH[- ]VOLTAGE BATTERY|\bHV BATTERY|TRACTION BATTERY|BATTERY PACK|\bICCU\b|"
                     r"INTEGRATED CHARGING CONTROL|INVERTER|DRIVE MOTOR|\bTRANSMISSION\b|\bDCT\b|\bIVT\b|\bCVT\b|FUEL PUMP", re.I)
SAFETY = re.compile(r"\bFIRE\b|FLAME|SMOKE|\bSTALL|LOSS OF (?:MOTIVE |DRIVE |PROPULSION )?POWER|REDUCED (?:ENGINE |MOTOR )?POWER|NO[- ]START|"
                    r"FUEL (?:LEAK|ODOR|SMELL)|AIR ?BAGS?\b|\bSRS\b|BRAKE (?:FAIL|LOSS|ASSIST|BOOSTER|FLUID LEAK)|LOSS OF (?:BRAK|STEER)|"
                    r"STEERING (?:LOSS|ASSIST|FAIL|COLUMN|GEAR|RACK)|SEAT ?BELT|THERMAL|OVERHEAT|CRASH|INJUR|HIGH[- ]VOLTAGE|"
                    r"WHEEL (?:DETACH|SEPARAT)|COOLANT LEAK", re.I)
RENOTICE = re.compile(r"RENOTIFICATION|RE-NOTIFICATION|REMINDER", re.I)
FORM = re.compile(r"REIMBURSEMENT (?:REQUEST )?FORM|QUESTION AND ANSWER|\bQ ?& ?A\b", re.I)
DOC_TAIL = re.compile(r"(?:[\s_-]+(?:TSB|DCS|WEBDCS|DL|OWNR\w*|DPSM|DP|QA|REIMB\w*|LETTER))+$", re.I)
CO_KEY = {"현대차": "HMA", "기아": "KIA", "한국GM": "GM"}
BULLETIN, CAMPAIGN_T, WARRANTY, OTA, EMISSIONS, OTHER = ("SERVICE BULLETIN/REPAIR INSTRUCTIONS", "SERVICE CAMPAIGN", "WARRANTY PROGRAM/EXTENSION",
                                                        "OVER THE AIR", "EMISSIONS", "OTHER")
KIND = {BULLETIN: "서비스 공지(수리 지침)", CAMPAIGN_T: "서비스 캠페인", WARRANTY: "보증 프로그램·캠페인", OTA: "무선 업데이트(OTA)",
        EMISSIONS: "배출가스", OTHER: "기타"}


def norm_type(t):
    """'Service Bulletin/Repair Instructions'·'Service Bulletin / Repair Instructions' 둘 다 같은 이름으로."""
    return re.sub(r"\s*/\s*", "/", re.sub(r"\s+", " ", (t or "").strip())).upper()


def brand_of(make, model):
    make = (make or "").strip().upper()
    if make in BRANDS:
        return BRANDS[make]
    if make in ("CHEVROLET", "BUICK") and GM_KOREA.match((model or "").strip()):
        return ("한국GM", "한국GM")
    return None


def spans(now):
    """파일 이름 후보. 지금은 TSBS_RECEIVED_2025-2026(앞 파일은 2020-2024) — 이름 짓는 법이 해마다 바뀔 수 있어
    두 해 묶음(불만 신고 파일과 같은 꼴)과 5년 구간 꼴을 함께 시도하고 없는 이름(404)은 건너뛴다."""
    y = now.year
    start = 2025 + ((y - 2025) // 5) * 5 if y >= 2025 else 2020
    return list(dict.fromkeys([f"{y - 1}-{y}", f"{y}-{y + 1}", f"{start}-{y}"]))


def day(v):
    v = re.sub(r"\D", "", v or "")
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if len(v) == 8 else ""


def short(text, n=600):
    """latin-1로 읽은 UTF-8을 되돌리고(불만 신고 파일과 같은 처리) 공백을 줄인다."""
    t = re.sub(r"\s+", " ", (text or "").encode("latin-1", "ignore").decode("utf-8", "ignore")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"


def read_comms(blob, since):
    """출입처 차종 줄만 NHTSA ID로 묶는다(추가일 since 이후). 같은 통신의 다른 제조사 차종 줄 수도 센다 —
    GM 통신은 한국 생산 차종(트랙스·트레일블레이저 등)과 미국 생산 차종을 한 번에 다루는 일이 많다."""
    out, rows_by_id = {}, {}
    zf = zipfile.ZipFile(io.BytesIO(blob))
    for info in zf.infolist():
        with zf.open(info) as fh:
            for raw in io.TextIOWrapper(fh, encoding="latin-1", newline=""):
                parts = raw.rstrip("\r\n").split("\t")
                if len(parts) < 14:
                    continue
                added = day(parts[ADDED])
                if not added or added < since:
                    continue
                nid = parts[ID].strip()
                rows_by_id[nid] = rows_by_id.get(nid, 0) + 1
                b = brand_of(parts[MAKE], parts[MODEL])
                if not b:
                    continue
                x = out.setdefault(nid, {"id": nid, "doc": parts[DOC].strip(), "added": added, "rows": 0,
                                                       "mfrDate": day(parts[MFR_DATE]), "campaign": parts[CAMPAIGN].strip(),
                                                       "type": norm_type(parts[CTYPE]), "summary": short(parts[SUMMARY]), "replaces": parts[REPL].strip(),
                                                       "companies": set(), "brands": set(), "models": {}, "components": set(), "systems": set()})
                x["rows"] += 1
                x["companies"].add(b[0])
                x["brands"].add(b[1])
                yrs = x["models"].setdefault(parts[MODEL].strip().upper(), set())
                if parts[YEAR].strip() and parts[YEAR].strip() != "9999":
                    yrs.add(parts[YEAR].strip())
                for c in re.split(r"[:;]", parts[COMP]):
                    if c.strip():
                        x["components"].add(c.strip())
                if parts[SYS].strip():
                    x["systems"].add(parts[SYS].strip())
    for nid, x in out.items():
        x["otherRows"] = rows_by_id.get(nid, 0) - x["rows"]
    return out


def group_key(x):
    """같은 캠페인 문서(소유주 통지·딜러 메모·Q&A·환급 양식·TSB)를 한 건으로 — 11-01 운영: 기아 WTY046 한 캠페인이 문서 6건이었다."""
    co = CO_KEY.get(sorted(x["companies"])[0], "X")
    if x.get("campaign"):
        return f"{co}:{x['campaign'].upper()}"
    base = DOC_TAIL.sub("", x.get("doc") or "").strip().upper()
    return f"{co}:doc:{base}" if base else f"{co}:id:{x['id']}"


def tier_of(text, types, companies, other_rows):
    """A: 보증 연장(특별 보증) 원문에 엔진 손상·터보·고전압 배터리·ICCU·변속기 같은 동력계통. B: 그 밖 보증 연장, 서비스 캠페인,
    안전·동력계통 낱말이 든 통신. 재통지는 C. 한국GM은 GM이 다른 차종과 함께 낸 공통 통신이면 C."""
    ext, serious, safety = EXTENSION.search(text), SERIOUS.search(text), SAFETY.search(text)
    if ext and serious:
        tier = "A"
    elif ext or CAMPAIGN_T in types or serious or safety:
        tier = "B"
    else:
        tier = "C"
    if tier == "B" and RENOTICE.search(text) and not ext:
        tier = "C"
    if companies == {"한국GM"} and other_rows > 0:
        tier = "C"
    return tier


def build(key, parts):
    parts = sorted(parts, key=lambda x: (x["added"], x["id"]))
    main = max(parts, key=lambda x: (not FORM.search(x["summary"]), len(x["summary"])))
    companies, brands, comps, systems, models = set(), set(), set(), set(), {}
    for x in parts:
        companies |= x["companies"]
        brands |= x["brands"]
        comps |= x["components"]
        systems |= x["systems"]
        for m, ys in x["models"].items():
            models.setdefault(m, set()).update(ys)
    text = " ".join(x["summary"] for x in parts)
    types = sorted({x["type"] for x in parts})
    other = sum(x.get("otherRows", 0) for x in parts)
    if EXTENSION.search(text):
        kind = "보증 연장"
    elif CAMPAIGN_T in types:
        kind = KIND[CAMPAIGN_T]
    else:
        kind = KIND.get(main["type"], main["type"] or "?")
    rec = {"id": key, "ids": [x["id"] for x in parts], "doc": main["doc"], "campaign": main.get("campaign", ""),
           "added": parts[0]["added"], "lastAdded": parts[-1]["added"], "mfrDate": min((x["mfrDate"] for x in parts if x["mfrDate"]), default=""),
           "type": main["type"], "types": types, "kindName": kind, "summary": main["summary"],
           "docs": [{"id": x["id"], "doc": x["doc"], "added": x["added"]} for x in parts][:10], "docCount": len(parts),
           "companies": sorted(companies), "brands": sorted(brands),
           "models": [{"model": m, "years": sorted(ys)} for m, ys in sorted(models.items())][:20], "modelCount": len(models),
           "components": sorted(comps)[:8], "systems": sorted(systems)[:6], "otherRows": other,
           "tier": tier_of(text, types, companies, other), "url": PDF.format(year=main["added"][:4], id=main["id"])}
    if RENOTICE.search(text):
        rec["renotice"] = True
    return {k: v for k, v in rec.items() if v not in ("", None)}


def collect(now, previous, *, get):
    """(구역, 점검). 캠페인(같은 캠페인 번호·같은 문서 번호) 단위로 묶고, 처음 본 캠페인만 [신규]. 첫 실행은 기준선."""
    stamp = now.isoformat(timespec="seconds")
    prev = previous or {}
    baseline = not prev
    seen_ids = set(prev.get("seen") or [])
    seen_keys = set(prev.get("seenKeys") or [])
    prev_items = [x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")]
    old = {x["id"]: x for x in prev_items}
    since = (now.date() - dt.timedelta(days=WINDOW_DAYS)).isoformat()
    comms, modified = {}, None
    try:
        got = 0
        for s in spans(now):
            r = get(URL.format(span=s), headers={"User-Agent": "seoul-reporting-radar (github.com/shhong9173-art/seoul-reporting-radar)"}, timeout=240)
            if r.status_code == 404:
                continue
            if r.status_code != 200:
                raise RuntimeError(f"{s} HTTP {r.status_code}")
            got += 1
            modified = modified or getattr(r, "headers", {}).get("Last-Modified")
            comms.update(read_comms(r.content, since))
        if not got:
            raise RuntimeError("파일 없음(" + ", ".join(spans(now)) + ")")
    except Exception as e:  # noqa: BLE001
        return ({**prev, "items": [dict(x, isNew=False) for x in prev_items], "stale": True},
                {"source": "NHTSA 제조사 통신(TSB)", "status": "failed", "error": str(e)[:80] or type(e).__name__})
    groups = {}
    for x in comms.values():
        groups.setdefault(group_key(x), []).append(x)
    items = {k: dict(x, isNew=False) for k, x in old.items() if x.get("ids")}   # 문서 한 건씩 담던 11-01 첫 결과는 버리고 묶음으로 다시
    for k, parts in groups.items():
        rec = build(k, parts)
        ids = rec["ids"]
        before = [old[i]["firstSeen"] for i in ids if i in old and old[i].get("firstSeen")]
        rec["firstSeen"] = (old.get(k) or {}).get("firstSeen") or (min(before) if before else stamp)
        rec["isNew"] = not baseline and k not in seen_keys and not any(i in seen_ids for i in ids)
        items[k] = rec
    seen_ids |= set(comms)
    seen_keys |= set(groups)
    kept = sorted((x for x in items.values() if str(x.get("lastAdded") or x.get("added")) >= since),
                  key=lambda x: (x.get("lastAdded") or x["added"], x["id"]), reverse=True)[:KEEP]
    check = {"source": "NHTSA 제조사 통신(TSB)", "status": "ok", "rows": len(comms), "campaigns": len(groups),
             "new": sum(1 for x in kept if x["isNew"]), **({"fileModified": modified} if modified else {})}
    return {"checkedAt": stamp, "baselineSince": prev.get("baselineSince") or stamp, "windowDays": WINDOW_DAYS, "items": kept,
            "seen": sorted(seen_ids)[-SEEN_MAX:], "seenKeys": sorted(seen_keys)[-SEEN_MAX:], "fileModified": modified, "rules": RULES}, check


RULES = ["NHTSA 제조사 통신 파일(TSB·서비스 캠페인·보증 프로그램·OTA)에서 파일 추가일 최근 120일, 현대차·기아·제네시스와 "
         "한국GM 생산 차종(트랙스·트레일블레이저·엔비스타·앙코르 GX) 통신만. 같은 캠페인 번호(없으면 같은 문서 번호)의 소유주 통지·딜러 메모·"
         "Q&A·환급 양식·TSB는 한 건으로 묶는다. 처음 본 캠페인이 [신규].",
         "등급: 보증 연장(특별 보증) 원문에 엔진 손상·터보차저·고전압 배터리·ICCU·변속기 같은 동력계통이 나오면 A, 그 밖 보증 연장·"
         "서비스 캠페인·화재·시동 꺼짐·에어백·제동·조향·고전압 등 안전 낱말이 든 통신 B, 나머지·재통지 C. GM이 다른 차종과 함께 낸 공통 통신은 C. "
         "등급 낱말은 요약 원문에서만 찾는다(부품 분류 칸은 넓다).",
         "제조사가 딜러·소유주에게 보낸 통신이라 결함 인정·리콜이 아니다. 국내 판매 차량 해당 여부·국내 무상수리 여부는 회사 확인 대상이다."]
