"""미국 NHTSA 전체 리콜 감시: 출입처 브랜드·한국GM 생산 차종·한국 타이어·한국 부품사 이름이 나온 새 리콜.

- 원천: NHTSA 전체 리콜 파일(FLAT_RCL_POST_2010.zip, 매일 갱신, 29칸 탭 구분). 접수일(RCDATE)이 최근 21일인 리콜만 본다.
  기존 감시(nhtsa_public_watch)는 현대·기아 4개 차종만 봤다(운영 10-26 경쟁지 [단독] '아우디 Q4 e-트론 미국 리콜 9,048대'를 놓침).
- 고르는 기준: 제조사(MAKETXT)가 출입처 브랜드, 한국GM이 만드는 차종(트랙스·트레일블레이저·엔비스타·앙코르 GX),
  타이어 리콜 제조사가 한국 타이어 3사, 결함 설명·부품 칸에 한국 부품사 이름.
- 원보고서(Part 573): 고른 리콜 중 실행당 PDF_BUDGET건은 NHTSA safetyIssues API로 보고서 파일 이름을 찾아 PDF를 열고
  '부품 공급사(Supplier Identification)' 칸을 읽는다(전체 리콜 파일의 부품 칸은 부품 이름이지 공급사가 아니다).
- 미국 리콜이 국내 판매 차량에 해당하는지는 이 자료로 알 수 없다. 회사·국토부 확인 대상이다.
- 결함조사(ODI): NHTSA 결함조사 파일(FLAT_INV.zip)에서 최근 120일에 열리거나 닫힌 조사 중 출입처 브랜드·한국GM 생산 차종·
  한국 부품사 이름이 나온 것. 리콜보다 먼저 나오는 신호다(예비조사 PE → 공학분석 EA 격상 → 리콜 적정성 RQ).
  조사 개시는 결함 확정이 아니고, 종결은 결함 없음 판정이 아니다.
- 결과는 기자 전용 저장소(us-recalls)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import datetime as dt
import io
import os
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "us_recalls/v1"
FLAT = "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip"
ISSUES = "https://api.nhtsa.gov/safetyIssues/byNhtsaId"
INV_FLAT = "https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip"
PDF_ROOT = "https://static.nhtsa.gov/odi/rcl"
PAGE = "https://www.nhtsa.gov/recalls?nhtsaId="
WINDOW_DAYS = 21
KEEP_DAYS = 120
PDF_BUDGET = 8
INV_LOOKBACK = 120
INV_TYPES = {"PE": "예비조사(PE)", "EA": "공학분석(EA, 격상 단계)", "RQ": "리콜 적정성 조사(RQ)", "DP": "결함 청원 검토(DP)",
             "AQ": "감사 질의(AQ)", "RP": "리콜 청원 검토(RP)", "IR": "정보 요청(IR)"}
DIRECT = {"현대차", "기아", "한국GM"}
UA = "seoul-reporting-radar (github.com/shhong9173-art/seoul-reporting-radar)"
# Field order of FLAT_RCL (RCL.txt, checked 2026-10-28: 29 fields).
FIELDS = ("RECORD_ID CAMPNO MAKETXT MODELTXT YEARTXT MFGCAMPNO COMPNAME MFGNAME BGMAN ENDMAN RCLTYPECD POTAFF ODATE INFLUENCED_BY "
          "MFGTXT RCDATE DATEA RPNO FMVSS DESC_DEFECT CONEQUENCE_DEFECT CORRECTIVE_ACTION NOTES RCL_CMPT_ID MFR_COMP_NAME "
          "MFR_COMP_DESC MFR_COMP_PTNO DO_NOT_DRIVE PARK_OUTSIDE").split()

# (make in the file, beat company, Korean name used in articles)
BRANDS = {"HYUNDAI": ("현대차", "현대차"), "GENESIS": ("현대차", "제네시스"), "KIA": ("기아", "기아"),
          "AUDI": ("아우디코리아", "아우디"), "VOLKSWAGEN": ("폭스바겐코리아", "폭스바겐"), "BMW": ("BMW코리아", "BMW"),
          "MINI": ("BMW코리아", "미니"), "MERCEDES-BENZ": ("메르세데스-벤츠 코리아", "벤츠"), "MERCEDES-AMG": ("메르세데스-벤츠 코리아", "벤츠"),
          "MERCEDES-MAYBACH": ("메르세데스-벤츠 코리아", "벤츠"), "HONDA": ("혼다코리아", "혼다")}
# Models GM Korea builds for the US market.
GM_KOREA = re.compile(r"^(?:TRAX|TRAILBLAZER|ENVISTA|ENCORE GX)\b", re.I)
TIRES = {"HANKOOK": "한국타이어", "NEXEN": "넥센타이어", "KUMHO": "금호타이어"}
# (pattern, Korean name, beat?) — names that appear in defect text, component fields or the Part 573 supplier box.
SUPPLIERS = [(r"Hyundai Mobis|\bMobis\b", "현대모비스", True), (r"\bHL Mando\b|\bMando\b", "HL만도", True), (r"Hyundai WIA", "현대위아", True),
             (r"Hankook", "한국타이어", True), (r"Nexen", "넥센타이어", True), (r"Kumho", "금호타이어", True),
             (r"\bLS (?:Cable|Electric|Automotive)", "LS", True), (r"\bSK On\b|SK Battery|\bSK Innovation", "SK온", False),
             (r"LG Energy Solution|\bLGES\b|LG Chem", "LG에너지솔루션", False), (r"Samsung SDI", "삼성SDI", False),
             (r"Hanon Systems|\bHanon\b", "한온시스템", False), (r"Hyundai Transys", "현대트랜시스", False), (r"Hyundai Kefico|KEFICO", "현대케피코", False),
             (r"Seoyon E-?Hwa", "서연이화", False), (r"SL Corporation|\bSL Corp\b", "SL", False)]


def kdate(v):
    v = str(v or "").strip()
    return f"{v[:4]}-{v[4:6]}-{v[6:8]}" if re.fullmatch(r"\d{8}", v) else None


def parse_flat(raw):
    """Tab-separated lines → dicts. Lines with another field count are counted, not guessed."""
    rows, bad = [], 0
    for line in raw.splitlines():
        cells = line.split("\t")
        if len(cells) != len(FIELDS):
            bad += 1
            continue
        rows.append(dict(zip(FIELDS, (c.strip() for c in cells))))
    return rows, bad


def suppliers_in(text):
    return sorted({(ko, beat) for rx, ko, beat in SUPPLIERS if re.search(rx, text or "", re.I)})


def campaigns(rows, since):
    """Group model rows by campaign for reports received since `since` (YYYY-MM-DD)."""
    out = {}
    for x in rows:
        rc = kdate(x["RCDATE"])
        if not rc or rc < since:
            continue
        c = out.setdefault(x["CAMPNO"], {"campaign": x["CAMPNO"], "received": rc, "type": x["RCLTYPECD"], "makes": set(), "models": set(),
                                          "component": x["COMPNAME"], "maker": x["MFGNAME"], "affected": 0, "defect": x["DESC_DEFECT"],
                                          "consequence": x["CONEQUENCE_DEFECT"], "remedy": x["CORRECTIVE_ACTION"], "parts": set(),
                                          "doNotDrive": x["DO_NOT_DRIVE"] == "Y", "parkOutside": x["PARK_OUTSIDE"] == "Y"})
        c["makes"].add(x["MAKETXT"].upper())
        if x["MODELTXT"]:
            c["models"].add((x["MODELTXT"].upper(), x["YEARTXT"]))
        if x["MFR_COMP_NAME"]:
            c["parts"].add(x["MFR_COMP_NAME"])
        try:
            c["affected"] = max(c["affected"], int(x["POTAFF"] or 0))
        except ValueError:
            pass
    return out


def model_line(models):
    by = {}
    for m, y in models:
        if y and y != "9999":
            by.setdefault(m, set()).add(y)
        else:
            by.setdefault(m, set())
    parts = []
    for m in sorted(by):
        ys = sorted(by[m])
        parts.append(f"{m} {ys[0]}" + (f"~{ys[-1]}" if len(ys) > 1 else "") if ys else m)
    return ", ".join(parts[:8]) + (f" 외 {len(parts) - 8}" if len(parts) > 8 else "")


def classify(c):
    """Why this recall concerns the beat. Empty list = not ours."""
    why = []
    for mk in sorted(c["makes"]):
        if mk in BRANDS:
            beat, ko = BRANDS[mk]
            why.append({"role": "제조사(출입처 브랜드)", "beat": beat, "name": ko})
    if any(GM_KOREA.match(m) and mk in ("CHEVROLET", "BUICK") for mk in c["makes"] for m, _ in c["models"]):
        why.append({"role": "한국GM 생산 차종", "beat": "한국GM", "name": "한국GM"})
    blob = " ".join([c["maker"], c["defect"], " ".join(c["parts"])])
    if c["type"] == "T":
        for k, ko in TIRES.items():
            if re.search(k, c["maker"] + " " + " ".join(c["makes"]), re.I):
                why.append({"role": "타이어 제조사", "beat": ko, "name": ko})
    for ko, beat in suppliers_in(blob):
        if not any(w["beat"] == ko for w in why):
            why.append({"role": "부품사 이름(결함 설명)" if beat else "부품사 이름(결함 설명, 출입처 아님)", "beat": ko if beat else None, "name": ko})
    return why


def part573(campaign, *, get, sleep):
    """Part 573 report file name via safetyIssues, then the supplier box of the PDF. Returns (fields, error)."""
    try:
        r = get(ISSUES, params={"filter": "recalls", "nhtsaId": campaign}, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=30)
    except Exception as e:
        return None, type(e).__name__
    sleep(0.5)
    if r.status_code != 200:
        return None, f"문서 목록 HTTP {r.status_code}"
    names = sorted(set(re.findall(r"RCLRPT-[0-9A-Z]+-\d+\.pdf", r.text, re.I)))
    if not names:
        return None, "Part 573 보고서 없음"
    year = "20" + campaign[:2]
    url = f"{PDF_ROOT}/{year}/{names[0]}"
    try:
        p = get(url, headers={"User-Agent": UA}, timeout=60)
    except Exception as e:
        return {"report": url}, type(e).__name__
    sleep(0.5)
    if p.status_code != 200 or not p.content[:4] == b"%PDF":
        return {"report": url}, f"보고서 HTTP {p.status_code}"
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(p.content))
        text = re.sub(r"\s+", " ", " ".join((pg.extract_text() or "") for pg in reader.pages[:8]))
    except Exception as e:
        return {"report": url}, f"PDF {type(e).__name__}"
    # Part 573 form (checked 2026-10-28 on 26V698·26V664): 'Component Manufacturer Tier of Supplier: … Supplier Type: … Name: …
    # Address: … Country: …' then 'Involved Components'. Several boxes are possible.
    sups = []
    for m in re.finditer(r"Component Manufacturer\s+Tier of Supplier:.*?Name:\s*(.+?)\s+Address:.*?Country:\s*(.+?)(?=\s+(?:Involved Components|Component Manufacturer|"
                         r"Part 573|U\.S\. Department)|$)", text, re.S):
        # A page break between the boxes inserts the form header ('Part 573 Safety Recall Report 26V663 The information …') — cut it.
        cut = lambda v: re.split(r"\s+(?:Part 573 Safety Recall Report|U\.S\. Department of Transportation|The information contained)", v)[0].strip()  # noqa: E731
        sup = {"name": cut(m.group(1))[:120], "country": cut(m.group(2))[:60]}
        if sup not in sups:
            sups.append(sup)
    box = " / ".join(f"{x['name']} ({x['country']})" for x in sups[:3]) or None
    korean = [ko for ko, _ in suppliers_in(" ".join(x["name"] for x in sups))]
    korean += [x["name"] for x in sups if re.search(r"Korea", x["country"], re.I) and not suppliers_in(x["name"])]
    return {"report": url, "supplierBox": box, "suppliers": sups[:3], "supplierKorean": korean}, None


def report_suppliers(x):
    """원보고서 공급사 칸의 한국 부품사를 관계(why)에 붙인다. why는 실행마다 전체 리콜 파일로 다시 만들고 원보고서는 한 번만 읽으므로
    매 실행 다시 붙인다(10-31 운영: 26V698000 아우디 Q4 e-tron의 'SK Battery Manufacturing Kft.'가 10-28 읽힌 뒤 다음 실행부터
    관계에서 빠져 B·보도 대조 '아우디 리콜'로만 떴다 — 같은 리콜이 10-26 경쟁지 [단독]으로 나왔다)."""
    for ko in x.get("supplierKorean") or []:
        known = next(((k, b) for _, k, b in SUPPLIERS if k == ko), None)
        role = ("부품 공급사(원보고서)" if known[1] else "부품 공급사(원보고서, 출입처 아님)") if known else "부품 공급사(원보고서, 한국 소재)"
        if not any(w["name"] == ko for w in x["why"]):
            x["why"].append({"role": role, "beat": ko if known and known[1] else None, "name": ko})
    x["beat"] = sorted({w["beat"] for w in x.get("why") or [] if w["beat"]})
    return x


def investigation_rows(lead):
    """Beat relations of one ODI action across all its vehicles (the action's first row alone can hide a Hyundai model)."""
    why = []
    for v in lead.get("vehicles") or []:
        make = str(v.get("make") or "").upper()
        if make in BRANDS:
            beat, name = BRANDS[make]
            item = {"role": "제조사(출입처 브랜드)", "beat": beat, "name": name}
        elif make in ("CHEVROLET", "BUICK") and GM_KOREA.match(str(v.get("model") or "")):
            item = {"role": "한국GM 생산 차종", "beat": "한국GM", "name": f"{make.title()} {str(v.get('model')).title()}"}
        else:
            continue
        if item not in why:
            why.append(item)
    for name, beat in suppliers_in(" ".join([lead.get("summary") or "", lead.get("subject") or "", lead.get("component") or "",
                                             *(lead.get("manufacturers") or [])])):
        item = {"role": "부품사(조사 요약)" if beat else "부품사(조사 요약, 출입처 아님)", "beat": name if beat else None, "name": name}
        if item not in why:
            why.append(item)
    return why


INV_FIELDS = ("action", "make", "model", "year", "component", "manufacturer", "opened", "closed", "campaign", "subject", "summary")


def parse_inv(raw, since, until):
    """ODI actions opened or closed between since and until (YYYYMMDD) whose rows name a beat make, a GM Korea model or a
    Korean supplier. The file is ~4 MB zipped / 150k tab rows; it is streamed."""
    import csv
    leads = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = [n for n in z.namelist() if n.lower().endswith((".txt", ".lst"))]
        if len(names) != 1:
            raise RuntimeError("결함조사 파일 형식 미상")
        with z.open(names[0]) as f, io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace", newline="") as fh:
            csv.field_size_limit(15_000)
            scanned = 0
            for row in csv.reader(fh, delimiter="\t"):
                if len(row) != 11:
                    continue
                scanned += 1
                r = dict(zip(INV_FIELDS, (str(x or "").strip() for x in row)))
                if not re.fullmatch(r"[A-Z0-9-]{3,14}", r["action"]) or not re.fullmatch(r"\d{8}", r["opened"]):
                    continue
                if not (since <= r["opened"] <= until or (re.fullmatch(r"\d{8}", r["closed"]) and since <= r["closed"] <= until)):
                    continue
                make = r["make"].upper()
                text = " ".join([r["summary"], r["subject"], r["component"], r["manufacturer"]])
                if not (make in BRANDS or (make in ("CHEVROLET", "BUICK") and GM_KOREA.match(r["model"])) or suppliers_in(text)):
                    continue
                lead = leads.setdefault(r["action"], {"actionNumber": r["action"], "openedDate": r["opened"], "closedDate": r["closed"],
                                                       "component": r["component"], "subject": r["subject"], "summary": r["summary"],
                                                       "vehicles": [], "recallCampaigns": [], "manufacturers": []})
                if r["manufacturer"] and r["manufacturer"] not in lead["manufacturers"]:
                    lead["manufacturers"].append(r["manufacturer"])
                v = {"make": r["make"], "model": r["model"], "modelYear": r["year"]}
                if v not in lead["vehicles"]:
                    lead["vehicles"].append(v)
                if r["campaign"] and r["campaign"] not in lead["recallCampaigns"]:
                    lead["recallCampaigns"].append(r["campaign"])
                lead["closedDate"] = lead["closedDate"] or r["closed"]
    return list(leads.values()), scanned


def investigations(raw, *, now, previous, had_state):
    """ODI actions opened or closed in the last INV_LOOKBACK days that touch a beat company."""
    items, scanned = parse_inv(raw, (now - dt.timedelta(days=INV_LOOKBACK)).strftime("%Y%m%d"), now.strftime("%Y%m%d"))
    stamp = now.isoformat(timespec="seconds")
    prev = {x["id"]: x for x in previous if isinstance(x, dict) and x.get("id")}
    out = []
    for lead in items:
        why = investigation_rows(lead)
        if not why:
            continue
        action = lead["actionNumber"]
        iid = f"odi:{action}"
        old = prev.get(iid, {})
        opened, closed = kdate(lead.get("openedDate")), kdate(lead.get("closedDate"))
        direct = any(w["beat"] in DIRECT or (str(w["role"]) == "부품사(조사 요약)") for w in why)
        rec = {"id": iid, "action": action, "type": INV_TYPES.get(action[:2], action[:2]), "kind": "조사 종결" if closed else "조사 개시",
               "opened": opened, "closed": closed,
               "models": model_line([(f"{v.get('make')} {v.get('model')}".strip(), str(v.get("modelYear") or "")) for v in lead.get("vehicles") or []]),
               "component": str(lead.get("component") or "")[:160], "subject": str(lead.get("subject") or "")[:200],
               "summary": str(lead.get("summary") or "")[:600], "recallCampaigns": lead.get("recallCampaigns") or [],
               "why": why, "beat": sorted({w["beat"] for w in why if w["beat"]}), "url": PAGE + action,
               # A: a probe opened (or escalated) on a Hyundai/Kia/GM Korea car or naming a Korean supplier; its close is B;
               # imported brands' probes are B when opened, C when closed
               "tier": ("A" if not closed else "B") if direct else ("B" if not closed else "C"),
               "firstSeen": old.get("firstSeen") or stamp}
        rec["isNew"] = bool(had_state and iid not in prev)
        if old and closed and not old.get("closed"):
            rec["isNew"], rec["changedAt"] = True, stamp  # a watched probe was closed
        elif old.get("changedAt"):
            rec["changedAt"] = old["changedAt"]
        out.append(rec)
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    ids = {x["id"] for x in out}
    out += [dict(x, isNew=False) for x in prev.values() if x["id"] not in ids and str(x.get("closed") or x.get("opened") or "") >= keep_from]
    return sorted(out, key=lambda x: (x.get("closed") or x.get("opened") or "", x["id"]), reverse=True), scanned


def run(*, now, previous=None, get=None, sleep=time.sleep):
    if get is None:
        import requests
        get = requests.get
    stamp = now.isoformat(timespec="seconds")
    since = (now - dt.timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%d")
    prev = {x["id"]: x for x in (previous or {}).get("recalls", []) if isinstance(x, dict) and x.get("id")}
    had_state = previous is not None
    checks = []
    try:
        r = get(FLAT, headers={"User-Agent": UA}, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        rows, bad = parse_flat(z.read(z.namelist()[0]).decode("latin-1"))
        if not rows:
            raise RuntimeError("행 없음")
        modified = getattr(r, "headers", {}).get("Last-Modified")
        checks.append({"source": "NHTSA 전체 리콜 파일", "status": "ok", "rows": len(rows), "badRows": bad, "fileModified": modified})
    except Exception as e:
        checks.append({"source": "NHTSA 전체 리콜 파일", "status": "failed", "error": str(e)[:80] or type(e).__name__})
        return {"schema": SCHEMA, "generatedAt": stamp, "status": "failed", "checks": checks, "recalls": list(prev.values()),
                "baselineSince": (previous or {}).get("baselineSince"), "rules": RULES, "confirmedScoops": 0}
    found = campaigns(rows, since)
    out = {}
    for camp, c in found.items():
        why = classify(c)
        if not why:
            continue
        rid = f"nhtsa:{camp}"
        old = prev.get(rid, {})
        out[rid] = {"id": rid, "campaign": camp, "received": c["received"], "type": c["type"], "makes": sorted(c["makes"]),
                    "models": model_line(c["models"]), "component": c["component"][:160], "maker": c["maker"][:80],
                    "affected": c["affected"], "defect": c["defect"][:700], "consequence": c["consequence"][:400], "remedy": c["remedy"][:300],
                    "parts": sorted(c["parts"])[:5], "doNotDrive": c["doNotDrive"], "parkOutside": c["parkOutside"],
                    "why": why, "beat": sorted({w["beat"] for w in why if w["beat"]}), "url": PAGE + camp[:6],
                    **{k: old[k] for k in ("report", "supplierBox", "suppliers", "supplierKorean", "reportError") if k in old},
                    "firstSeen": old.get("firstSeen") or stamp}
    # Part 573 supplier box for new matches, beat makers first, budgeted.
    budget, read, errs = PDF_BUDGET, 0, 0
    maker_first = lambda x: any(w["role"].startswith(("제조사", "한국GM", "타이어")) for w in x["why"])  # noqa: E731
    order = sorted(out.values(), key=lambda x: (not maker_first(x), -int(x["received"].replace("-", ""))))
    for x in order:
        if budget <= 0:
            break
        if "report" in x or x.get("reportError") in ("Part 573 보고서 없음",):
            continue
        budget -= 1
        fields, err = part573(x["campaign"], get=get, sleep=sleep)
        if fields:
            x.update(fields)
        if err:
            x["reportError"] = err
            errs += 1
        else:
            read += 1
            x.pop("reportError", None)
    checks.append({"source": "NHTSA 원보고서(Part 573)", "status": "ok" if not errs else ("partial" if read else "failed"),
                   "read": read, "errors": errs, "pending": sum(1 for x in out.values() if "report" not in x and not x.get("reportError"))})
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for rid, x in prev.items():
        if rid not in out and str(x.get("received") or "") >= keep_from:
            out[rid] = x
    for x in out.values():
        report_suppliers(x)
    recalls = sorted(out.values(), key=lambda x: (x["received"], x["affected"]), reverse=True)
    for x in recalls:
        x["isNew"] = bool(had_state and x["id"] not in prev)
    # ODI defect investigations: the first run that reads them is their baseline
    inv_prev = (previous or {}).get("investigations")
    try:
        r = get(INV_FLAT, headers={"User-Agent": UA}, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        invs, scanned = investigations(r.content, now=now, previous=inv_prev or [], had_state=inv_prev is not None)
        checks.append({"source": "NHTSA 결함조사(ODI)", "status": "ok", "rows": scanned, "matched": len(invs)})
    except Exception as e:  # noqa: BLE001
        invs = [dict(x, isNew=False) for x in inv_prev or []]
        checks.append({"source": "NHTSA 결함조사(ODI)", "status": "failed", "error": str(e)[:80] or type(e).__name__})
    # 소비자 결함 신고 급증(리콜·조사 전 단계 신호). 같은 차종·부품의 최근 리콜과 견주려고 리콜 파일 줄을 넘긴다.
    import nhtsa_complaints
    cmpl, ccheck = nhtsa_complaints.collect(now, (previous or {}).get("complaints"), rows, get=get)
    checks.append(ccheck)
    # 제조사 통신(서비스 캠페인·보증 연장·서비스 공지) — 리콜 아닌 무상수리·보증 연장이 먼저 보이는 곳
    import nhtsa_tsbs
    tsbs, tcheck = nhtsa_tsbs.collect(now, (previous or {}).get("tsbs"), get=get)
    checks.append(tcheck)
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "complete" if all(c["status"] == "ok" for c in checks) else "partial",
            "complaints": cmpl, "tsbs": tsbs,
            "windowDays": WINDOW_DAYS, "checks": checks, "recalls": recalls, "investigations": invs, "invLookbackDays": INV_LOOKBACK,
            "baselineSince": (previous or {}).get("baselineSince") or stamp, "rules": RULES, "confirmedScoops": 0}


RULES = ["NHTSA 전체 리콜 파일에서 접수일 최근 21일 리콜 중 출입처 브랜드·한국GM 생산 차종·한국 타이어 3사·한국 부품사 이름이 나온 것만.",
         "부품사 이름은 결함 설명·부품 칸·원보고서(Part 573) 공급사 칸에 적힌 경우만이다. 원인 제공자라는 뜻은 아니다.",
         "미국 리콜이 국내 판매 차량에 해당하는지는 이 자료로 알 수 없다. 회사·국토부(자동차리콜센터) 확인 대상이다.",
         "결함조사(ODI)는 최근 120일에 열리거나 닫힌 조사다. 조사 개시는 결함 확정이 아니고, 종결은 결함 없음 판정이 아니다.",
         "첫 실행은 기준선이다. 조회 실패는 0건이 아니라 미확인."]


def main():
    import private_store
    now = dt.datetime.now(KST)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("us-recalls", token)
        except private_store.StoreError as e:
            print(f"::warning title=us-recalls-state::이전 상태 조회 실패({e}) — 신규 표시는 이번 실행 기준")
    if private_store.late_scheduled_duplicate(previous, now):
        return
    doc = run(now=now, previous=previous)
    roles = {}
    for x in doc["recalls"]:
        for w in x["why"]:
            roles[w["role"]] = roles.get(w["role"], 0) + 1
    invs = doc.get("investigations") or []
    sp = [x for x in (doc.get("complaints") or {}).get("spikes", []) if x.get("active")]
    # 공개 로그라 차종 이름은 적지 않는다(건수만)
    print(f"::notice title=us-complaints::소비자 결함 신고 급증 {len(sp)}건(신규 {sum(1 for x in sp if x.get('isNew'))}, "
          f"B {sum(1 for x in sp if x.get('tier') == 'B')}) · 점검 {[c['status'] for c in doc['checks'] if c['source'] == 'NHTSA 소비자 결함 신고']}")
    ts = (doc.get("tsbs") or {}).get("items") or []
    print(f"::notice title=us-tsbs::제조사 통신 {len(ts)}건(신규 {sum(1 for x in ts if x.get('isNew'))}, "
          f"A {sum(1 for x in ts if x.get('tier') == 'A')}, B {sum(1 for x in ts if x.get('tier') == 'B')}) · "
          f"점검 {[c['status'] for c in doc['checks'] if c['source'] == 'NHTSA 제조사 통신(TSB)']}")
    print(f"::notice title=us-recalls::상태 {doc['status']} · 출입처 관련 리콜 {len(doc['recalls'])}건(신규 {sum(1 for x in doc['recalls'] if x['isNew'])}) · "
          f"결함조사 {len(invs)}건(신규·종결 {sum(1 for x in invs if x.get('isNew'))}, A {sum(1 for x in invs if x.get('tier') == 'A')}) · "
          f"분류 {roles} · 점검 {[(c['source'], c['status']) for c in doc['checks']]}")
    if not token:
        print("::warning title=us-recalls-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("리콜 파일 조회 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("us-recalls", doc, token)
    print(f"::notice title=us-recalls-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
