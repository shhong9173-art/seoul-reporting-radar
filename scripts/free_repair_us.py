"""자동차리콜센터 무상수리 공지 ↔ 미국 NHTSA 리콜 자동 대조(같은 차종·같은 연식·같은 부품 낱말).

근거: 11-04 아이뉴스24 「구형 팰리세이드 9만대 ABS 무상수리⋯美보다 11개월 늦어」 — 국내 무상수리 공지와 미국 리콜의
시점·조치 차이가 기사였다. 레이더는 국내 공지(kr_free_repair.py)와 미국 리콜(us_recall_watch.py, 최근 접수분)을 따로 보여 줘
둘을 잇는 일은 기자가 손으로 했다 — 미국 리콜이 몇 달 먼저인 경우가 많아 최근 접수분만으로는 이어지지 않는다.

NHTSA 공개 API(recallsByVehicle — nhtsa.gov 'Datasets and APIs'에 적힌 것, nhtsa_official_watch.py와 같은 길)로 공지 차종의
미국 판매 이름·생산기간 연식을 조회해, 부품 낱말이 맞는 리콜만 남긴다. 같은 결함이라는 확인이 아니다(원문 대조·회사 확인).
- 조회는 출입처 공지마다 한 번(차종 2개 × 연식 3개까지), 실행당 BUDGET번, 요청 사이 GAP초. 실패는 TRIES번까지 다음 실행이 다시.
- 미국 판매 이름을 모르는 차종(국내 전용·수입차)은 조회하지 않는다 — '미국 리콜 없음'이 아니라 '조회 안 함'.
- 리콜 접수일(ReportReceivedDate)은 '일/월/연' 꼴이다(저장소 digests/nhtsa_official_latest.json의 '27/01/2026').
결과는 기자 전용 저장소(kr-fuel의 freeRepair 구역 항목의 us 칸)로만. 공개 로그는 건수만.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from urllib.parse import urlencode

API = "https://api.nhtsa.gov/recalls/recallsByVehicle"
UA = "Mozilla/5.0 seoul-reporting-radar (reporter research)"
BUDGET = 12          # 한 실행의 조회 수
GAP = 1.0            # 조회 사이 간격(초)
TRIES = 3            # 실패한 공지는 이 횟수까지 다음 실행이 다시
MAX_MODELS, MAX_YEARS, MAX_MATCHES = 2, 3, 3
LEAD_DAYS = 60       # 미국 리콜이 국내 공지보다 이만큼 앞서면 A(kr_free_repair.classify)
PARTS_VERSION = 2     # 부품 낱말 판: 바뀌면 낱말 없음으로 맞춰 보지 않은(parts 빈) 공지 중 새 판에서 낱말이 잡히는 것만 다시 본다(2: 11-27 주행·주차 보조·스프링)
MODEL_VERSION = 2    # 차종 목록 판: 바뀌면 '조회 안 함'(no-model)으로 적은 공지를 다시 본다(2: 11-22 혼다·한국GM·폭스바겐·아우디)

# (국내 차명 규칙, 미국 제조사, 미국 차명, 하이브리드 차명, 전기차 차명). 국내 전용 차종(그랜저·캐스퍼·스타리아·레이·모닝·K8·K9·타스만 등)은 없다.
US_MODELS = [
    (r"아반떼|엘란트라", "HYUNDAI", "ELANTRA", "ELANTRA HYBRID", None),
    (r"쏘나타", "HYUNDAI", "SONATA", "SONATA HYBRID", None),
    (r"투싼", "HYUNDAI", "TUCSON", "TUCSON HYBRID", None),
    (r"싼타페", "HYUNDAI", "SANTA FE", "SANTA FE HYBRID", None),
    (r"팰리세이드", "HYUNDAI", "PALISADE", None, None),
    (r"코나", "HYUNDAI", "KONA", None, "KONA ELECTRIC"),
    (r"베뉴", "HYUNDAI", "VENUE", None, None),
    (r"아이오닉\s*5|IONIQ\s*5", "HYUNDAI", "IONIQ 5", None, None),
    (r"아이오닉\s*6|IONIQ\s*6", "HYUNDAI", "IONIQ 6", None, None),
    (r"아이오닉\s*9|IONIQ\s*9", "HYUNDAI", "IONIQ 9", None, None),
    (r"넥쏘", "HYUNDAI", "NEXO", None, None),
    (r"쏘렌토", "KIA", "SORENTO", "SORENTO HYBRID", None),
    (r"스포티지", "KIA", "SPORTAGE", "SPORTAGE HYBRID", None),
    (r"카니발", "KIA", "CARNIVAL", None, None),
    (r"셀토스", "KIA", "SELTOS", None, None),
    (r"니로", "KIA", "NIRO", None, "NIRO EV"),
    (r"쏘울", "KIA", "SOUL", None, None),
    (r"(?<![A-Z0-9])K5(?![0-9])", "KIA", "K5", None, None),
    (r"(?<![A-Z0-9])K4(?![0-9])", "KIA", "K4", None, None),
    (r"(?<![A-Z0-9])EV\s*6(?![0-9])", "KIA", "EV6", None, None),
    (r"(?<![A-Z0-9])EV\s*9(?![0-9])", "KIA", "EV9", None, None),
    (r"(?<![A-Z0-9])G70(?![0-9])", "GENESIS", "G70", None, None),
    (r"(?<![A-Z0-9])G80(?![0-9])", "GENESIS", "G80", None, "ELECTRIFIED G80"),
    (r"(?<![A-Z0-9])G90(?![0-9])", "GENESIS", "G90", None, None),
    (r"(?<![A-Z0-9])GV60(?![0-9])", "GENESIS", "GV60", None, None),
    (r"(?<![A-Z0-9])GV70(?![0-9])", "GENESIS", "GV70", None, "ELECTRIFIED GV70"),
    (r"(?<![A-Z0-9])GV80(?![0-9])", "GENESIS", "GV80", None, None),
    # 11-22: 미국에서 만들거나 미국에도 파는 수입·한국GM 차종 — 혼다(어코드·CR-V·파일럿·오딧세이는 미국 생산), 한국GM 수출 차종, 폭스바겐·아우디 일부.
    # BMW·벤츠는 국내 차명(520i·E 300)과 미국 차명(530I·E350)이 달라 뺐다.
    (r"어코드|ACCORD", "HONDA", "ACCORD", "ACCORD HYBRID", None),
    (r"(?<![A-Z])CR-?V(?![A-Z0-9])", "HONDA", "CR-V", "CR-V HYBRID", None),
    (r"(?<![A-Z])HR-?V(?![A-Z0-9])", "HONDA", "HR-V", None, None),
    (r"파일럿|PILOT", "HONDA", "PILOT", None, None),
    (r"오딧세이|오디세이|ODYSSEY", "HONDA", "ODYSSEY", None, None),
    (r"시빅|CIVIC", "HONDA", "CIVIC", "CIVIC HYBRID", None),
    (r"프롤로그|PROLOGUE", "HONDA", "PROLOGUE", None, None),
    (r"트랙스|TRAX", "CHEVROLET", "TRAX", None, None),
    (r"트레일블레이저|TRAILBLAZER", "CHEVROLET", "TRAILBLAZER", None, None),
    (r"이쿼녹스|EQUINOX", "CHEVROLET", "EQUINOX", None, "EQUINOX EV"),
    (r"타호|TAHOE", "CHEVROLET", "TAHOE", None, None),
    (r"콜로라도|COLORADO", "CHEVROLET", "COLORADO", None, None),
    (r"아틀라스|ATLAS", "VOLKSWAGEN", "ATLAS", None, None),
    (r"티구안|TIGUAN", "VOLKSWAGEN", "TIGUAN", None, None),
    (r"제타|JETTA", "VOLKSWAGEN", "JETTA", None, None),
    (r"(?<![A-Z])ID\.?\s*4(?![0-9])", "VOLKSWAGEN", "ID.4", None, None),
    (r"Q4\s*(?:\d{2}\s*)?(?:Sportback\s*)?e-?tron", "AUDI", "Q4 E-TRON", None, None),
]
HYBRID = re.compile(r"하이브리드|HEV(?!\w)|\bHybrid\b", re.I)
ELECTRIC = re.compile(r"일렉트릭|전기차|(?<![A-Z])EV(?![0-9A-Z])|Electric", re.I)

# (표시 낱말, 국내 공지 낱말, 미국 리콜 낱말, 강한 낱말인가). 약한 낱말(시트·도어)만 맞은 리콜은 남기지 않는다.
PARTS = [
    ("레이더", r"레이더", r"RADAR", True),
    ("웨더스트립", r"웨더\s*스트립", r"WEATHER\s*-?\s*STRIP", True),
    ("DPF", r"DPF|매연\s*저감", r"\bDPF\b|PARTICULATE", True),
    ("ECU", r"\bECU\b|엔진\s*제어", r"\bECU\b|\bECM\b|ENGINE CONTROL", True),
    ("BDC", r"\bBDC\b|바디\s*도메인", r"\bBDC\b|BODY DOMAIN", True),
    ("HPCU", r"HPCU|하이브리드\s*통합\s*제어", r"HPCU|HYBRID POWER CONTROL", True),
    ("ICCU", r"ICCU|통합\s*충전", r"ICCU|INTEGRATED CHARGING CONTROL", True),
    ("ABS", r"\bABS\b|잠김\s*방지", r"\bABS\b|ANTI-?\s*LOCK", True),
    ("에어백", r"에어백", r"AIR\s*BAG", True),
    ("래치", r"래치", r"LATCH", True),
    ("안전벨트", r"안전벨트|좌석안전띠|시트\s*벨트", r"SEAT\s*BELT", True),
    ("와이어링", r"와이어링|배선", r"WIRING|HARNESS", True),
    ("USB", r"USB", r"\bUSB\b", True),
    ("룸미러", r"룸미러|실내\s*미러", r"REAR\s*-?\s*VIEW MIRROR|INSIDE MIRROR|INTERIOR MIRROR", True),
    ("타이어 밸브", r"에어\s*밸브|타이어\s*밸브", r"VALVE STEM|TIRE VALVE", True),
    ("VCU", r"\bVCU\b|차량\s*제어", r"\bVCU\b|VEHICLE CONTROL UNIT", True),
    ("EGR", r"EGR", r"\bEGR\b", True),
    ("엔진오일", r"엔진\s*오일", r"OIL CONSUMPTION|ENGINE OIL", True),
    ("브레이크", r"브레이크|제동", r"BRAKE", True),
    ("연료펌프", r"연료\s*펌프", r"FUEL PUMP", True),
    ("조향", r"조향|스티어링", r"STEERING", True),
    ("트렁크", r"트렁크|테일\s*게이트|리프트\s*게이트", r"TRUNK|TAILGATE|LIFTGATE", True),
    ("선루프", r"선루프|파노라마\s*루프", r"SUNROOF|PANORAMIC ROOF", True),
    ("와이퍼", r"와이퍼", r"WIPER", True),
    ("계기판", r"계기판|클러스터", r"INSTRUMENT (?:PANEL|CLUSTER)|\bCLUSTER\b", True),
    ("전조등", r"전조등|헤드\s*램프", r"HEADLAMP|HEADLIGHT", True),
    ("후방카메라", r"후방\s*카메라", r"REAR\s*-?\s*VIEW CAMERA|BACKUP CAMERA|REAR CAMERA", True),
    ("변속기", r"변속기", r"TRANSMISSION", True),
    ("터보", r"터보", r"TURBO", True),
    ("고전압 배터리", r"고전압\s*배터리", r"HIGH\s*-?\s*VOLTAGE BATTERY", True),
    ("12V 배터리", r"12\s*V(?![0-9])|12\s*볼트|보조\s*배터리", r"12\s*-?\s*V(?:OLT)?\b", True),
    ("스마트키", r"스마트\s*키|UWB|\bFOB\b", r"SMART KEY|KEY FOB|\bFOB\b|\bUWB\b|ULTRA\s*-?\s*WIDE", True),
    ("연료 누유", r"연료\s*누|누유", r"FUEL LEAK", True),
    # 11-27: GV60 '운전자 주행 보조 제어기'·'운전자 주차 보조 제어기'(4891·4890), 니로 '리어 스프링'(4894)이 부품 낱말 없음으로 대조를 건너뛰었다
    ("주행 보조", r"주행\s*보조|운전자\s*보조|(?<![A-Z])ADAS(?![A-Z])|스마트\s*크루즈|차로\s*유지", r"DRIVER\s*-?\s*ASSIST|\bADAS\b|FORWARD COLLISION|LANE KEEP|LANE DEPARTURE|SMART CRUISE|ADAPTIVE CRUISE|HIGHWAY DRIVING", True),
    ("주차 보조", r"주차\s*보조|주차\s*거리|초음파\s*센서", r"PARK(?:ING)?\s*(?:ASSIST|AID|DISTANCE)|PARKING SENSOR|ULTRASONIC", True),
    ("스프링", r"(?:리어|프런트|프론트|코일|현가)\s*스프링", r"SUSPENSION\S*?SPRING|COIL SPRINGS?|(?:REAR|FRONT)\s*(?:COIL\s*)?SPRINGS?", True),
    ("시트", r"시트(?!\s*벨트)", r"\bSEATS?\b(?!\s*BELT)", False),
    ("도어", r"도어", r"\bDOORS?\b", False),
]
_PARTS = [(label, re.compile(ko, re.I), re.compile(en, re.I), strong) for label, ko, en, strong in PARTS]
_MODELS = [(re.compile(p, re.I), make, base, hyb, ev) for p, make, base, hyb, ev in US_MODELS]
SEGMENT = re.compile(r"\s-\s(.+?)(?:\s관련)?\s*무상(?:수리|점검)")


# 미국 제조사 → 공지의 출입처(kr_free_repair.BRANDS 이름). 다른 브랜드 공지에 든 낱말('아틀라스' 배터리 등)로 엉뚱한 차종을 조회하지 않게.
MAKER_OF = {"HYUNDAI": "현대차", "GENESIS": "현대차", "KIA": "기아", "HONDA": "혼다코리아", "CHEVROLET": "한국GM",
            "VOLKSWAGEN": "폭스바겐코리아", "AUDI": "아우디코리아"}


def us_models(item):
    """(제조사, [미국 차명 ≤2]) 또는 None. 차명 칸·제목에서 찾는다. 공지에 출입처가 적혀 있으면 그 브랜드 차종만."""
    text = f"{item.get('model') or ''} {item.get('title') or ''}"
    company = item.get("company")
    for rx, make, base, hyb, ev in _MODELS:
        if company and MAKER_OF.get(make) != company:
            continue
        if not rx.search(text):
            continue
        names = [base]
        if hyb and HYBRID.search(text):
            names.append(hyb)
        if ev and ELECTRIC.search(text):
            names = [ev] + names
        return make, names[:MAX_MODELS]
    return None


def model_years(produced):
    """생산기간 'YYYY-MM-DD ~ YYYY-MM-DD' → 미국 연식 후보(≤3: 처음·가운데·끝). 하반기 생산은 다음 연식일 수 있어 끝 해 +1까지."""
    ys = [int(y) for y in re.findall(r"(20\d{2})[-.]\d{1,2}", str(produced or ""))]
    if not ys:
        return []
    lo, hi = min(ys), max(ys)
    cand = list(range(lo, hi + 2))
    if len(cand) <= MAX_YEARS:
        return cand
    return sorted({cand[0], cand[len(cand) // 2], cand[-1]})


def domestic_parts(item):
    """국내 공지의 부품 낱말 — 제목의 부품 이름(' - … 관련 무상수리')과 원인 문장(조치 칸은 안 본다)."""
    seg = SEGMENT.search(str(item.get("title") or ""))
    text = f"{seg.group(1) if seg else ''} {item.get('reason') or ''}"
    return [(label, en, strong) for label, ko, en, strong in _PARTS if ko.search(text)]


def recall_date(raw):
    """'27/01/2026' → '2026-01-27'. ISO('2026-01-27…')도 받는다. 못 읽으면 None."""
    s = str(raw or "").strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return dt.date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    return m.group(0) if m else None


def recall_url(campaign):
    c = str(campaign or "")
    return f"https://www.nhtsa.gov/recalls?nhtsaId={c[:-3] if c.endswith('000') and len(c) > 6 else c}"


def match_rows(rows, parts, domestic_date=None):
    """조회 결과 줄들 → 부품 낱말이 맞은 리콜(캠페인별로 연식·차명을 합침), 접수일 이른 순."""
    by = {}
    for r in rows:
        camp = str(r.get("NHTSACampaignNumber") or "").strip()
        if not camp:
            continue
        hay = f"{r.get('Component') or ''} {r.get('Summary') or ''}"
        hit = [label for label, en, strong in parts if en.search(hay)]
        if not any(strong for label, en, strong in parts if label in hit):
            continue
        rec = by.setdefault(camp, {"campaign": camp, "received": recall_date(r.get("ReportReceivedDate")), "models": [], "years": [],
                                   "component": str(r.get("Component") or "")[:100], "summary": str(r.get("Summary") or "")[:240],
                                   "parts": hit, "url": recall_url(camp)})
        for k, v in (("models", str(r.get("Model") or r.get("_model") or "").upper()), ("years", str(r.get("ModelYear") or r.get("_year") or ""))):
            if v and v not in rec[k]:
                rec[k].append(v)
    out = sorted(by.values(), key=lambda x: (x["received"] or "9999", x["campaign"]))
    if domestic_date:
        for x in out:
            try:
                x["leadDays"] = (dt.date.fromisoformat(domestic_date[:10]) - dt.date.fromisoformat(x["received"])).days if x["received"] else None
            except ValueError:
                x["leadDays"] = None
    for x in out:
        x["years"] = sorted(x["years"])
    return out[:MAX_MATCHES]


class Unknown(Exception):
    """NHTSA가 모르는 차명·연식(HTTP 400) — 11-22 첫 운영: SANTA FE·SONATA 2027년형이 400(아직 등록 전 연식). 조회 실패가 아니다."""


def _fetch(get, make, model, year):
    url = f"{API}?{urlencode({'make': make, 'model': model, 'modelYear': year})}"
    r = get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=20)
    if getattr(r, "status_code", 200) == 400:
        raise Unknown("HTTP 400")
    if getattr(r, "status_code", 200) != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    data = r.json() if hasattr(r, "json") else json.loads(r.text)
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("results 없음")
    return [{**x, "_model": model, "_year": year} for x in rows if isinstance(x, dict)]


def link(items, get, now, *, sleep=time.sleep, budget=BUDGET):
    """출입처·상세 읽은 공지에 us 칸을 채운다(새 글부터, 한 번). 돌려줌: 점검 {calls, checked, linked, failed, waiting}."""
    stamp = now.isoformat(timespec="seconds")
    for x in items:   # 11-22 첫 운영 저장분: HTTP 400(모르는 연식)을 실패로 적었다 — 한 번 고쳐 둔다
        us = x.get("us") or {}
        bits = [b.strip() for b in str(us.get("error") or "").split(";") if b.strip()]
        if us.get("status") in ("partial", "failed") and bits and all(b.endswith("HTTP 400") for b in bits):
            us.update(status="ok", unknown=[b[:-len(" HTTP 400")] for b in bits])
            us.pop("error", None)
            us.pop("tries", None)
    todo = [x for x in items if x.get("company") and x.get("detail") == "ok"
            and (not x.get("us") or (x["us"].get("status") == "failed" and (x["us"].get("tries") or 0) < TRIES)
                 or (x["us"].get("status") == "no-model" and x["us"].get("v") != MODEL_VERSION)
                 or (x["us"].get("status") in ("ok", "partial") and x["us"].get("parts") == []
                     and x["us"].get("pv") != PARTS_VERSION and domestic_parts(x)))]
    todo.sort(key=lambda x: (x.get("date") or "", int(x.get("no") or 0)), reverse=True)
    calls = checked = linked = failed = waiting = 0
    for x in todo:
        found = us_models(x)
        if not found:
            x["us"] = {"at": stamp, "status": "no-model", "v": MODEL_VERSION}
            continue
        years = model_years(x.get("produced"))
        if not years:
            x["us"] = {"at": stamp, "status": "no-years", "models": found[1]}
            continue
        make, names = found
        pairs = [(m, y) for m in names for y in years]
        if calls + len(pairs) > budget:
            waiting += 1
            continue
        rows, errors, unknown = [], [], []
        for m, y in pairs:
            if calls:
                sleep(GAP)
            calls += 1
            try:
                rows += _fetch(get, make, m, y)
            except Unknown:
                unknown.append(f"{m} {y}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{m} {y} {str(e)[:40] or type(e).__name__}")
        parts = domestic_parts(x)
        status = "failed" if len(errors) == len(pairs) else "partial" if errors else "ok"
        prev_tries = (x.get("us") or {}).get("tries") or 0
        x["us"] = {"at": stamp, "status": status, "make": make, "models": names, "years": years,
                   "parts": [label for label, _, _ in parts], "pv": PARTS_VERSION, "campaigns": len({r.get("NHTSACampaignNumber") for r in rows if r.get("NHTSACampaignNumber")}),
                   "matches": match_rows(rows, parts, x.get("date")) if parts else [],
                   **({"unknown": unknown} if unknown else {}),
                   **({"error": "; ".join(errors)[:160], "tries": prev_tries + 1} if errors else {})}
        checked += 1
        failed += status == "failed"
        linked += bool(x["us"]["matches"])
    return {"calls": calls, "checked": checked, "linked": linked, "failed": failed, "waiting": waiting}


def link_tsbs(items, tsbs):
    """미국 제조사 통신(us-recalls 저장소의 tsbs.items — 서비스 캠페인·보증 연장·서비스 공지, 최근 120일)과 같은 차종·연식·부품 낱말.
    조회 없이 저장소끼리 맞춘다. 실행마다 다시 보고, 한 번 맞은 통신은 보관 기간이 지나도 남긴다. 돌려줌: 맞은 공지 수."""
    hit = 0
    for x in items:
        if not (x.get("company") and x.get("detail") == "ok"):
            continue
        found = us_models(x)
        parts = domestic_parts(x) if found else []
        if not found or not parts:
            continue
        names = set(found[1])
        years = {str(y) for y in model_years(x.get("produced"))}
        keep = {m["key"]: m for m in x.get("usTsb") or [] if isinstance(m, dict) and m.get("key")}
        for t in tsbs or []:
            rows = [m for m in t.get("models") or [] if str(m.get("model") or "").upper() in names and (not years or years & {str(y) for y in m.get("years") or []})]
            if not rows:
                continue
            hay = f"{' '.join(t.get('components') or [])} {t.get('summary') or ''}"
            got = [label for label, en, strong in parts if en.search(hay)]
            if not any(strong for label, en, strong in parts if label in got):
                continue
            key = t.get("campaign") or t.get("doc") or t.get("id")
            when = t.get("mfrDate") or t.get("added") or ""
            lead = None
            try:
                lead = (dt.date.fromisoformat(str(x.get("date"))[:10]) - dt.date.fromisoformat(str(when)[:10])).days
            except ValueError:
                pass
            keep[key] = {"key": key, "campaign": t.get("campaign") or "", "doc": t.get("doc") or "", "kind": t.get("kindName") or t.get("type") or "",
                         "date": str(when)[:10], "models": [m["model"] for m in rows], "years": sorted({y for m in rows for y in (m.get("years") or [])})[-4:],
                         "parts": got, "summary": str(t.get("summary") or "")[:240], "url": t.get("url") or "", "leadDays": lead}
        if keep:
            x["usTsb"] = sorted(keep.values(), key=lambda m: (m.get("date") or "9999", m["key"]))[:MAX_MATCHES]
            hit += 1
    return hit


# 넓은 부품 낱말: 같은 차종의 다른 결함 리콜에도 흔히 나온다(제동 계통·배선·변속기·조향) — 화면엔 보이되 이 낱말만 맞은 대조로는 A로 올리지 않는다
# 11-27 '주행 보조'도 넓다(전방 충돌·차로 유지·적응형 크루즈를 한데 묶은 낱말)
BROAD = {"브레이크", "와이어링", "변속기", "조향", "주행 보조"}


def lead_note(item):
    """미국 리콜이 국내 공지보다 LEAD_DAYS일 넘게 앞선 첫 대조 결과(넓은 낱말만 맞은 것 빼고) → 등급 이유 문장, 없으면 ''."""
    for m in (item.get("us") or {}).get("matches") or []:
        if (m.get("leadDays") or 0) >= LEAD_DAYS and set(m.get("parts") or []) - BROAD:
            return f"미국 같은 차종·부품 낱말 리콜 {m['campaign']}이 국내 공지보다 {m['leadDays']}일 앞(같은 결함인지 미확인)"
    return ""
