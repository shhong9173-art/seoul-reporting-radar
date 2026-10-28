"""미국 NHTSA 전체 리콜 감시: 출입처 브랜드·한국GM 생산 차종·한국 타이어·한국 부품사 이름이 나온 새 리콜.

- 원천: NHTSA 전체 리콜 파일(FLAT_RCL_POST_2010.zip, 매일 갱신, 29칸 탭 구분). 접수일(RCDATE)이 최근 21일인 리콜만 본다.
  기존 감시(nhtsa_public_watch)는 현대·기아 4개 차종만 봤다(운영 10-26 경쟁지 [단독] '아우디 Q4 e-트론 미국 리콜 9,048대'를 놓침).
- 고르는 기준: 제조사(MAKETXT)가 출입처 브랜드, 한국GM이 만드는 차종(트랙스·트레일블레이저·엔비스타·앙코르 GX),
  타이어 리콜 제조사가 한국 타이어 3사, 결함 설명·부품 칸에 한국 부품사 이름.
- 원보고서(Part 573): 고른 리콜 중 실행당 PDF_BUDGET건은 NHTSA safetyIssues API로 보고서 파일 이름을 찾아 PDF를 열고
  '부품 공급사(Supplier Identification)' 칸을 읽는다(전체 리콜 파일의 부품 칸은 부품 이름이지 공급사가 아니다).
- 미국 리콜이 국내 판매 차량에 해당하는지는 이 자료로 알 수 없다. 회사·국토부 확인 대상이다.
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
PDF_ROOT = "https://static.nhtsa.gov/odi/rcl"
PAGE = "https://www.nhtsa.gov/recalls?nhtsaId="
WINDOW_DAYS = 21
KEEP_DAYS = 120
PDF_BUDGET = 8
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
             (r"\bLS (?:Cable|Electric|Automotive)", "LS", True), (r"\bSK On\b|SK Battery America|\bSK Innovation", "SK온", False),
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
    m = re.search(r"Supplier Identification:?(.{0,500}?)(?:Chronology|Description of Remedy|Recall Schedule|$)", text, re.I)
    box = re.sub(r"\s+", " ", m.group(1)).strip()[:400] if m else None
    return {"report": url, "supplierBox": box, "supplierKorean": [ko for ko, _ in suppliers_in(box or "")]}, None


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
                    **{k: old[k] for k in ("report", "supplierBox", "supplierKorean", "reportError") if k in old},
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
            for ko in x.get("supplierKorean") or []:
                beat = next((b for _, k, b in SUPPLIERS if k == ko), False)
                if not any(w["name"] == ko for w in x["why"]):
                    x["why"].append({"role": "부품 공급사(원보고서)" if beat else "부품 공급사(원보고서, 출입처 아님)", "beat": ko if beat else None, "name": ko})
            x["beat"] = sorted({w["beat"] for w in x["why"] if w["beat"]})
    checks.append({"source": "NHTSA 원보고서(Part 573)", "status": "ok" if not errs else ("partial" if read else "failed"),
                   "read": read, "errors": errs, "pending": sum(1 for x in out.values() if "report" not in x and not x.get("reportError"))})
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for rid, x in prev.items():
        if rid not in out and str(x.get("received") or "") >= keep_from:
            out[rid] = x
    recalls = sorted(out.values(), key=lambda x: (x["received"], x["affected"]), reverse=True)
    for x in recalls:
        x["isNew"] = bool(had_state and x["id"] not in prev)
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "complete" if all(c["status"] == "ok" for c in checks) else "partial",
            "windowDays": WINDOW_DAYS, "checks": checks, "recalls": recalls,
            "baselineSince": (previous or {}).get("baselineSince") or stamp, "rules": RULES, "confirmedScoops": 0}


RULES = ["NHTSA 전체 리콜 파일에서 접수일 최근 21일 리콜 중 출입처 브랜드·한국GM 생산 차종·한국 타이어 3사·한국 부품사 이름이 나온 것만.",
         "부품사 이름은 결함 설명·부품 칸·원보고서(Part 573) 공급사 칸에 적힌 경우만이다. 원인 제공자라는 뜻은 아니다.",
         "미국 리콜이 국내 판매 차량에 해당하는지는 이 자료로 알 수 없다. 회사·국토부(자동차리콜센터) 확인 대상이다.",
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
    print(f"::notice title=us-recalls::상태 {doc['status']} · 출입처 관련 리콜 {len(doc['recalls'])}건(신규 {sum(1 for x in doc['recalls'] if x['isNew'])}) · "
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
