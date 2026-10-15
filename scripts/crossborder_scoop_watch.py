"""Scan ALL recent US vehicle recalls, including old model years.

NHTSA's vehicle-by-model API missed the 2015-2020 Genesis/G80 26V664
because the former collector queried just four 2026 models. The official
post-2010 flat recall archive covers *all* models in one download.
A recall record is public; do not infer a Korean defect, domestic recall
absence, fire incident, or an exclusive from the US record alone.
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

KST = timezone(timedelta(hours=9))
SOURCE = "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip"
CAMPAIGN = re.compile(r"^\d{2}[A-Z]\d{3,6}$")
DATE = re.compile(r"^20\d{6}$")
# Official RCL.txt field offsets, zero-indexed:
# CAMPNO=1 MAKETXT=2 MODELTXT=3 YEARTXT=4 COMPNAME=6 MFGNAME=7
# RCLTYPECD=10 POTAFF=11 RCDATE=15 DATEA=16 DESC_DEFECT=19
# CONSEQUENCE=20 CORRECTIVE_ACTION=21 PARK_OUTSIDE=28
GROUP = ("HYUNDAI", "GENESIS", "KIA")
FIRE = re.compile(r"fire|burn|ignit|smoke|overheat|thermal|short circuit", re.I)
KOREAN_TERMS = re.compile(r"\bkorea(n)?\b|south korea|republic of korea", re.I)


def is_beat(make, manufacturer):
    make = str(make or "").upper().strip()
    mfg = str(manufacturer or "").upper()
    return (make.startswith(GROUP) or
            any(word in mfg for word in
                ("HYUNDAI MOTOR", "KIA AMERICA", "KIA MOTORS", "GENESIS MOTOR")))


def safe_date(value):
    text = str(value or "").strip()
    if not DATE.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def fetch_archive(url=SOURCE):
    req = Request(url, headers={"User-Agent":"industry-reporter-safety-watch/1.0",
                                 "Accept":"application/zip"})
    with urlopen(req, timeout=75) as response:
        payload = response.read(32_000_001)
    if len(payload) > 32_000_000:
        raise ValueError("NHTSA ZIP is larger than allowed 32MB")
    return payload


def scan_archive(payload, *, now=None, window_days=45):
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        raise ValueError("timezone required")
    today = now.astimezone(KST).date()
    begin = today - timedelta(days=window_days)
    latest = None
    checked = 0
    selected = 0
    grouped = defaultdict(list)
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise ValueError("NHTSA ZIP invalid")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        files = [f for f in archive.infolist() if not f.is_dir() and
                 f.filename.upper().endswith(".TXT")]
        if len(files) != 1 or files[0].file_size > 550_000_000:
            raise ValueError("NHTSA ZIP schema/size unexpected")
        with archive.open(files[0]) as body:
            stream = io.TextIOWrapper(body, encoding="latin-1", errors="replace")
            for line in stream:
                cols = line.rstrip("\r\n").split("\t")
                if len(cols) < 29:
                    continue
                received = safe_date(cols[15])
                if received and received <= today:
                    if latest is None or received > latest:
                        latest = received
                if not received or received < begin or received > today:
                    continue
                checked += 1
                campaign = cols[1].strip()
                if not CAMPAIGN.fullmatch(campaign) or cols[10].strip() != "V":
                    continue
                if not is_beat(cols[2], cols[7]):
                    continue
                selected += 1
                grouped[campaign].append(cols)
    if latest is None or latest < today - timedelta(days=21):
        raise ValueError("NHTSA source is stale; must not publish a zero-lead scan")
    leads = []
    for no, rows in grouped.items():
        dates = sorted({r[15] for r in rows})
        makes = sorted({r[2].strip() for r in rows if r[2].strip()})
        models = sorted({(r[3].strip(), r[4].strip()) for r in rows if r[3].strip()})
        if len(dates) != 1:
            # Conflicting campaign receipt dates require human checking.
            continue
        defect = max((r[19].strip() for r in rows), key=len, default="")
        consequence = max((r[20].strip() for r in rows), key=len, default="")
        action = max((r[21].strip() for r in rows), key=len, default="")
        category = next((r[6].strip() for r in rows if r[6].strip()), "")
        combined = defect + " " + consequence
        flags = []
        if FIRE.search(combined):
            flags.append("fire_or_thermal_word_in_us_summary")
        if any(str(r[28]).strip().upper() in ("Y", "YES", "1") for r in rows):
            flags.append("us_park_outside_advice")
        if any(m[1].isdigit() and int(m[1]) <= today.year - 4 for m in models):
            flags.append("older_vehicle_model")
        # Flat-file defect text is NOT a Part 573 chronology.
        if KOREAN_TERMS.search(combined):
            flags.append("korean_term_in_us_defect_summary")
        score = 40 + (20 if flags and "fire_or_thermal_word_in_us_summary" in flags else 0)
        score += 10 if "us_park_outside_advice" in flags else 0
        score += 10 if "older_vehicle_model" in flags else 0
        leads.append({
            "id":no, "officialDate":dates[0], "makes":makes,
            "models":[{"model":m, "year":y} for m,y in models][:35],
            "modelCount":len(models), "component":category, "defect":defect[:1100],
            "consequence":consequence[:750], "remedy":action[:600],
            "flags":flags, "priorityScore":min(85,score),
            "sourceUrl":"https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber="+no,
            "reportSearchUrl":"https://www.nhtsa.gov/recalls?nhtsaId="+no,
            "officialEvidence":"NHTSA US recall record only",
            "usRecallExists":True,
            "part573ChronologyVerified":False, "koreanIncidentVerified":False,
            "koreanPartMatchVerified":False, "koreanRecallChecked":False,
            "priorCoverageChecked":False, "exclusiveConfirmed":False,
            "approvedForPitch":False,
            "mustCheck":[
                "Open complete Part 573 chronology and search Korea / thermal event; no claim until original text verified",
                "Compare exact seat/component part numbers and specifications of Korea-sold variants",
                "Check Korea recall and free repair in car.go.kr and ask KATRI/MOLIT if inaccessible",
                "Check domestic/overseas news for the same angle; US recall itself is not exclusive"
            ]
        })
    leads.sort(key=lambda x:(x["officialDate"],x["priorityScore"],x["id"]),reverse=True)
    return {
        "generatedAt":now.astimezone(KST).isoformat(),
        "source":"NHTSA ODI full post-2010 recall archive",
        "sourceUrl":SOURCE,
        "archiveLatestReceived":latest.isoformat(),
        "lookbackDays":window_days, "recentSourceRowsExamined":checked,
        "beatRows":selected, "campaignCount":len(leads),
        "status":"official_us_recalls_to_review",
        "domesticSourceStatus":"not_connected",
        "firstSeenWarning":"Initial run is a baseline, not newly published scoops",
        "confirmedScoops":0,
        "leads":leads[:75]
    }


def main():
    result = scan_archive(fetch_archive())
    path = Path("digests/crossborder_safety_latest.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    tmp.replace(path)


if __name__ == "__main__":
    main()
