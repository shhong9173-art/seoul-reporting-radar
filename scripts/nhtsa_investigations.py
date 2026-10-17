"""NHTSA ODI *investigations* (not merely manufacturer recall headlines).

Source: https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip and its INV.txt
metadata. All records are tab-delimited. Opened investigations are not
established safety defects; investigative records can cover multiple models.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.request import urlopen,Request

KST=timezone(timedelta(hours=9))
SOURCE="https://static.nhtsa.gov/odi/ffdd/inv/FLAT_INV.zip"
DOCS="https://www.nhtsa.gov/nhtsa-datasets-and-apis"
# Long, unambiguous identifiers. 'GM' by itself could name many unrelated entities.
MAKES={"HYUNDAI":"현대차","KIA":"기아","GENESIS":"현대차(제네시스)",
       "CHEVROLET":"한국GM 관련 가능성(미국 GM)","BUICK":"한국GM 관련 가능성(미국 GM)",
       "BMW":"BMW코리아 관련(미국 판매차)","AUDI":"아우디코리아 관련(미국 판매차)",
       "VOLKSWAGEN":"폭스바겐코리아 관련(미국 판매차)",
       "MERCEDES-BENZ":"벤츠코리아 관련(미국 판매차)",
       "HONDA":"혼다코리아 관련(미국 판매차)",
       "RENAULT":"르노코리아 연관 별도 확인"}
FIELDS=("actionNumber","make","model","modelYear","component","manufacturer",
        "openedDate","closedDate","recallCampaign","subject","summary")
DATE=re.compile(r"^(?:19|20)\d{6}$")
ACTION=re.compile(r"^[A-Z0-9-]{3,14}$")
# Include STILL-OPEN, older investigations as a comparison baseline. Publication
# time of later changes in an old case is not given by the FLAT_INV dataset.
LONG_OPEN_WATCH_DAYS=1461


def direct_make(make,manufacturer):
    tokens=re.findall(r"[A-Z0-9]+(?:-[A-Z0-9]+)*",str(make or "").upper())
    company=str(manufacturer or "").upper()
    # NHTSA MAKE field usually names primary manufacturer / marque. No alias
    # derived from a generic 'KIA' inside another word such as 'NOKIAN'.
    for key,label in MAKES.items():
        if key in tokens or (key in ("HYUNDAI","KIA") and
                             re.search(r"(?<![A-Z])"+key+r"(?![A-Z])",company)):
            return label
    return None


def parse_tab_data(content,now=None,lookback=100):
    """Legacy small in-memory fixtures: real NHTSA ZIP is stream-parsed."""
    if len(content)>120_000_000:raise ValueError("In-memory fixture too large")
    text=io.StringIO(content.decode("utf-8-sig",errors="replace"))
    return parse_rows(csv.reader(text,delimiter="\t"),now=now,lookback=lookback)


def valid_date(value):
    if not DATE.fullmatch(value):
        return False
    try:
        datetime.strptime(value,"%Y%m%d")
        return True
    except ValueError:
        return False


def parse_rows(reader,now=None,lookback=100):
    now=now or datetime.now(KST)
    if not 1<=lookback<=365:raise ValueError("1..365 days only")
    start=(now-timedelta(days=lookback)).strftime("%Y%m%d")
    oldest_open=(now-timedelta(days=LONG_OPEN_WATCH_DAYS)).strftime("%Y%m%d")
    end=now.strftime("%Y%m%d")
    leads={}
    evidence={}
    inspected=0
    for row in reader:
        if not row or len(row)!=11:continue
        inspected+=1
        if inspected>800_000:raise ValueError("NHTSA record row count exceeds safety limit")
        obj=dict(zip(FIELDS,(str(x or "").strip() for x in row)))
        action=obj["actionNumber"]
        opened=obj["openedDate"]
        closed=obj["closedDate"]
        if (not ACTION.fullmatch(action) or not valid_date(opened) or opened>end
            or (closed and (not valid_date(closed) or closed<opened or closed>end))):
            continue
        # Old still-open actions can acquire new official evidence without a
        # new action number or recent opening date. Observe up to four years,
        # but NEVER call their first observation a fresh opened investigation.
        recent_event=(start<=opened<=end or (closed and start<=closed<=end))
        old_open_watch=(not closed and oldest_open<=opened<start)
        if not (recent_event or old_open_watch):continue
        owner=direct_make(obj["make"],obj["manufacturer"])
        if not owner:continue
        obj["coveredIssuerRelation"]=owner
        obj["sourceUrl"]=DOCS
        obj["sourceDataset"]=SOURCE
        obj["recallLinked"]=bool(obj["recallCampaign"])
        obj["longRunningOpenReferenceOnly"]=bool(old_open_watch)
        obj["publicationDateForSourceChangeVerified"]=False
        # Hash the complete official row before bounding the displayed excerpt.
        # Row order and repeated model rows must not manufacture a change.
        signature=hashlib.sha256(json.dumps([obj[k] for k in FIELDS],
                    ensure_ascii=False).encode()).hexdigest()
        evidence.setdefault(action,set()).add(signature)
        obj["summary"]=obj["summary"][:900]
        obj["discoveryType"]=("official_us_investigation_closed" if closed
                              else "official_us_investigation_opened")
        obj["officialEventDate"]=closed or opened
        obj["caution"]="미국 NHTSA 조사 기록. 종결은 결함 없음 판정이 아니며 결함 확정·국내 판매 모델 동일성·국내 리콜/단독 아님"
        lead=leads.setdefault(action,{**obj,"vehicles":[],"officialEventDates":[],
                                     "recallCampaigns":[]})
        # Require every matched row to be an old still-open record before
        # applying the background-only classification to this action.
        lead["longRunningOpenReferenceOnly"]=bool(
            lead["longRunningOpenReferenceOnly"] and old_open_watch)
        vehicle={k:obj[k] for k in ("make","model","modelYear","manufacturer","component")}
        if vehicle not in lead["vehicles"]:lead["vehicles"].append(vehicle)
        dates={"openedDate":opened,"closedDate":closed}
        if dates not in lead["officialEventDates"]:lead["officialEventDates"].append(dates)
        if obj["recallCampaign"] and obj["recallCampaign"] not in lead["recallCampaigns"]:
            lead["recallCampaigns"].append(obj["recallCampaign"])
    for action,lead in leads.items():
        lead["vehicles"].sort(key=lambda v:tuple(v[k] for k in sorted(v)))
        lead["officialEventDates"].sort(key=lambda v:(v["openedDate"],v["closedDate"]))
        lead["recallCampaigns"].sort()
        lead["recallLinked"]=bool(lead["recallCampaigns"])
        lead["eventDateConflict"]=len(lead["officialEventDates"])!=1
        if lead["eventDateConflict"]:
            lead["officialEventDate"]=None
            lead["discoveryType"]="official_us_investigation_date_conflict"
        if lead["longRunningOpenReferenceOnly"]:
            lead["discoveryType"]="historical_still_open_investigation_source_watch"
        lead["sourceFingerprintVersion"]=1
        lead["sourceFingerprint"]=hashlib.sha256("\n".join(sorted(evidence[action])).encode()).hexdigest()
    return {"scannedRecords":inspected,"items":sorted(leads.values(),
                    key=lambda z:(z["officialEventDate"] or "",z["actionNumber"]),reverse=True)}


def recent_changes(current,previous):
    old={x.get("actionNumber"):x for x in (previous or {}).get("items",[])}
    for x in current["items"]:
        before=old.get(x["actionNumber"])
        x["firstSeenInRadar"]=before.get("firstSeenInRadar") if before else current["generatedAt"]
        old_open=bool(x.get("longRunningOpenReferenceOnly"))
        x["observationState"]=(
            "historical_open_baseline_not_new_event" if before is None and old_open
            else "first_observed_in_this_radar" if before is None
            else "previously_observed")
        comparable=bool(before and x.get("sourceFingerprint") and before.get("sourceFingerprint")
                        and x.get("sourceFingerprintVersion")==before.get("sourceFingerprintVersion")==1)
        x["sourceContentChanged"]=(x["sourceFingerprint"]!=before["sourceFingerprint"]
                                    if comparable else None)
        x["changeComparisonStatus"]="compared" if comparable else "baseline_required"
        if x["sourceContentChanged"]:
            x["observationState"]=(
                "historical_open_source_changed_publication_date_unknown" if old_open
                else "previously_observed_source_changed")
        x["changeIsNewPublicationVerified"]=False
        x["changeVerifiedFromTwoOfficialSnapshots"]=bool(comparable and x["sourceContentChanged"])
        x["changeEvidenceIsNotNewPublicAnnouncement"]=True
        x["substantiveChangeDetails"]=(
            {
              "vehicleScopeChanged":bool(before.get("vehicles")!=x.get("vehicles")),
              "formalEventDatesChanged":bool(before.get("officialEventDates")!=x.get("officialEventDates")),
              "recallReferencesChanged":bool(before.get("recallCampaigns")!=x.get("recallCampaigns")),
              "displayedSummaryChanged":bool(before.get("summary")!=x.get("summary")),
              "fullOfficialRowSignatureChanged":True,
              "trueRevisionTimestampVerified":False,
              "publicationDateUnknown":True,
              "manufacturerOrAgencyConfirmedNewHazard":False,
            } if x["sourceContentChanged"] else None
        )
        # First observed is NOT first published nor scoop. Keep source date.
    current["newlyObserved"]=sum(x["observationState"]=="first_observed_in_this_radar"
                                  for x in current["items"])
    current["changedObserved"]=sum(x["sourceContentChanged"] is True for x in current["items"])
    current["longRunningOpenBackgroundCount"]=sum(
        x.get("longRunningOpenReferenceOnly") is True for x in current["items"])
    current["historicalOpenSubstantiveDeltaCount"]=sum(
        x.get("observationState")=="historical_open_source_changed_publication_date_unknown"
        for x in current["items"])
    current["olderBaselineIsNotNewPublication"]=True
    return current


def fetch_zip(url=SOURCE):
    req=Request(url,headers={"User-Agent":"seoul-reporting-radar NHTSA public records/1.0"})
    with urlopen(req,timeout=35) as r:
        raw=r.read(12_000_001)
    if len(raw)>12_000_000:raise ValueError("NHTSA official compressed dataset larger than expected")
    return raw


def parse_zip_data(raw,now=None,lookback=100):
    # The official 4MB compressed archive can expand beyond 120MB. Stream
    # rather than materializing decompressed multi-decade records in memory.
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=[n for n in z.namelist() if n.lower().endswith((".txt",".lst"))]
        if len(names)!=1:raise ValueError("NHTSA ZIP expected one tab data text file")
        info=z.getinfo(names[0])
        if info.file_size>650_000_000:raise ValueError("NHTSA ZIP exceeds bounded scan size")
        if info.compress_size<1 or info.file_size<100:
            raise ValueError("NHTSA ZIP text content incomplete")
        with z.open(info) as f:
            with io.TextIOWrapper(f,encoding="utf-8-sig",errors="replace",
                                  newline="") as reader:
                csv.field_size_limit(15_000)
                return parse_rows(csv.reader(reader,delimiter="\t"),now=now,lookback=lookback)


def write_health(data,output=Path("digests/nhtsa_source_status_latest.json")):
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(output)


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="digests/nhtsa_investigations_latest.json")
    p.add_argument("--lookback",type=int,default=100)
    a=p.parse_args()
    out=Path(a.out)
    previous={}
    if out.is_file():
        try:previous=json.loads(out.read_text(encoding="utf-8"))
        except (OSError,ValueError):pass
    now=datetime.now(KST)
    try:
        downloaded=fetch_zip()
        result=parse_zip_data(downloaded,now=now,lookback=a.lookback)
        if result["scannedRecords"]<200:
            raise ValueError("NHTSA investigations original file was incomplete")
        status={"generatedAt":now.isoformat(timespec="seconds"),"status":"checked",
                "scannedRecords":result["scannedRecords"],"candidateCount":len(result["items"]),
                "sourceUrl":SOURCE}
    except (OSError,ValueError,TimeoutError,zipfile.BadZipFile) as err:
        reason=(str(err)[:160] if isinstance(err,ValueError) else "network_or_zip_error")
        status={"generatedAt":now.isoformat(timespec="seconds"),"status":"source_error",
                "errorType":type(err).__name__,"sourceUrl":SOURCE,
                "errorReason":reason,
                "warning":"NHTSA 공식원천 다운로드/파싱 불완전, 이전 정상자료 보존"}
        write_health(status)
        raise SystemExit("NHTSA official source failed: "+type(err).__name__) from None
    write_health(status)
    result.update({"generatedAt":now.isoformat(timespec="seconds"),"sourceUrl":SOURCE,
                   "scope":"US ODI formal opened investigations among matched marques, not recalls or complaint allegation totals",
                   "lookbackDays":a.lookback,
                   "confirmedScoops":0,"domesticModelApplicabilityVerified":False,
                   "verifiedPublicationDateForSourceUpdates":False,
                   "historicalOpenFirstSeenIsNotNewInvestigation":True})
    recent_changes(result,previous)
    # Empty for matched makes may be correct, but successful official scan is
    # required; neither failed download nor silent schema change means zero.
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(out)
    print("NHTSA investigations parsed",result["scannedRecords"],
          "matching opened",len(result["items"]),"newly observed",result["newlyObserved"])


if __name__=="__main__":main()
