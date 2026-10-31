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
SAFETY = re.compile(r"\bFIRE\b|FLAME|SMOKE|STALL|LOSS OF (?:MOTIVE |DRIVE |PROPULSION )?POWER|NO[- ]START|\bICCU\b|INTEGRATED CHARGING|"
                    r"FUEL (?:LEAK|ODOR|SMELL)|AIR ?BAG|\bSRS\b|BRAKE|STEERING|SEAT ?BELT|THERMAL|OVERHEAT|ENGINE (?:SEIZ|FAILURE|DAMAGE|KNOCK)|"
                    r"CONNECTING ROD|PISTON|OIL CONSUMPTION|TRANSMISSION (?:FAIL|SLIP|DAMAGE)|CRASH|INJUR|HIGH[- ]VOLTAGE|BATTERY PACK", re.I)
POWERTRAIN = re.compile(r"ENGINE|BATTERY|TRANSMISSION|\bICCU\b|MOTOR|INVERTER|HIGH[- ]VOLTAGE|POWERTRAIN", re.I)
BULLETIN, CAMPAIGN_T, WARRANTY, OTA, EMISSIONS, OTHER = ("SERVICE BULLETIN/REPAIR INSTRUCTIONS", "SERVICE CAMPAIGN", "WARRANTY PROGRAM/EXTENSION",
                                                        "OVER THE AIR", "EMISSIONS", "OTHER")
KIND = {BULLETIN: "서비스 공지(수리 지침)", CAMPAIGN_T: "서비스 캠페인", WARRANTY: "보증 연장·보증 프로그램", OTA: "무선 업데이트(OTA)",
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


def tier_of(x):
    """보증 프로그램(동력계통 A·그 밖 B)·서비스 캠페인(B)·안전 낱말이 든 서비스 공지/OTA/기타(B), 나머지 C.
    한국GM은 GM이 다른 차종과 함께 낸 공통 통신이면 C(한국 생산 차종만의 일이 아님)."""
    text = " ".join([x["summary"], " ".join(x["components"]), " ".join(x["systems"])])
    t = x["type"]
    if t == WARRANTY:
        tier = "A" if POWERTRAIN.search(text) else "B"
    elif t == CAMPAIGN_T:
        tier = "B"
    elif t in (BULLETIN, OTA, OTHER) and SAFETY.search(text):
        tier = "B"
    else:
        tier = "C"
    if x["companies"] == {"한국GM"} and x.get("otherRows", 0) > 0:
        tier = "C"
    return tier


def finish(x):
    models = sorted(x["models"].items())
    return {**{k: v for k, v in x.items() if k not in ("companies", "brands", "models", "components", "systems", "replaces") and v != ""},
            **({"replaces": x["replaces"]} if x.get("replaces") else {}),
            "companies": sorted(x["companies"]), "brands": sorted(x["brands"]),
            "models": [{"model": m, "years": sorted(ys)} for m, ys in models][:20], "modelCount": len(models),
            "components": sorted(x["components"])[:8], "systems": sorted(x["systems"])[:6],
            "kindName": KIND.get(x["type"], x["type"] or "?")}


def collect(now, previous, *, get):
    """(구역, 점검). 처음 본 NHTSA ID만 [신규]. 첫 실행은 기준선."""
    stamp = now.isoformat(timespec="seconds")
    prev = previous or {}
    baseline = not prev
    seen = set(prev.get("seen") or [])
    old = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
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
        return ({**prev, "items": [dict(x, isNew=False) for x in old.values()], "stale": True},
                {"source": "NHTSA 제조사 통신(TSB)", "status": "failed", "error": str(e)[:80] or type(e).__name__})
    items = dict(old)
    for i, x in comms.items():
        rec = finish(x)
        rec["tier"] = tier_of(x)
        rec["firstSeen"] = (old.get(i) or {}).get("firstSeen") or stamp
        rec["isNew"] = not baseline and i not in seen
        rec["url"] = PDF.format(year=rec["added"][:4], id=i)
        items[i] = rec
    for i in items:
        if i not in comms:
            items[i]["isNew"] = False
    seen |= set(comms)
    kept = sorted((x for x in items.values() if str(x.get("added")) >= since), key=lambda x: (x["added"], x["id"]), reverse=True)[:KEEP]
    check = {"source": "NHTSA 제조사 통신(TSB)", "status": "ok", "rows": len(comms), "new": sum(1 for x in kept if x["isNew"]),
             **({"fileModified": modified} if modified else {})}
    return {"checkedAt": stamp, "baselineSince": prev.get("baselineSince") or stamp, "windowDays": WINDOW_DAYS, "items": kept,
            "seen": sorted(seen)[-SEEN_MAX:], "fileModified": modified, "rules": RULES}, check


RULES = ["NHTSA 제조사 통신 파일(TSB·서비스 캠페인·보증 프로그램·OTA)에서 파일 추가일 최근 120일, 현대차·기아·제네시스와 "
         "한국GM 생산 차종(트랙스·트레일블레이저·엔비스타·앙코르 GX) 통신만. 처음 본 NHTSA ID가 [신규].",
         "등급: 보증 프로그램(엔진·배터리·변속기·ICCU·모터 낱말 A, 그 밖 B) · 서비스 캠페인 B · 화재·시동 꺼짐·에어백·제동·조향 등 "
         "안전 낱말이 든 서비스 공지·OTA B · 나머지 C. GM이 다른 차종과 함께 낸 공통 통신은 C.",
         "제조사가 딜러에게 보낸 통신이라 결함 인정·리콜이 아니다. 국내 판매 차량 해당 여부·국내 무상수리 여부는 회사 확인 대상이다."]
