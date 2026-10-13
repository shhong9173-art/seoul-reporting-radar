"""US NHTSA official vehicle recalls/complaints research monitor.

Official API, no scraping. A complaint is NOT a confirmed defect; a recall
is already publicly disclosed, not a scoop. Track *first seen* ID against
previous verified snapshot, never confuse model year with filing year.
"""
from __future__ import annotations
import argparse
import json
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,urlopen

KST=timezone(timedelta(hours=9))
BASE="https://api.nhtsa.gov"
# Named model-year combinations prevent unaudited model enumeration.
VEHICLES=(
 ("Hyundai","IONIQ 5",2026),("Hyundai","TUCSON",2026),
 ("Hyundai","SANTA FE",2026),("Kia","EV6",2026),
 ("Kia","SORENTO",2026),("Kia","SPORTAGE",2026),
 ("Genesis","GV70",2026),("BMW","X5",2026),
 ("Mercedes-Benz","GLC300",2026),("Toyota","RAV4",2026),
)
KINDS={"recalls":"recallsByVehicle","complaints":"complaintsByVehicle"}
ISSUE=re.compile(r"^[0-9A-Za-z-]{5,24}$")
def read_json(url):
    with urlopen(Request(url,headers={"User-Agent":"industry-official-reporter/1.0",
                                      "Accept":"application/json"}),timeout=13) as res:
        data=res.read(2_000_001)
    if len(data)>2_000_000:raise ValueError("NHTSA response exceeded limit")
    out=json.loads(data)
    if not isinstance(out,dict):raise ValueError("Invalid NHTSA response")
    return out

def canonical(kind,row):
    if kind=="recalls":
        rid=str(row.get("NHTSACampaignNumber") or "").strip()
        date=str(row.get("ReportReceivedDate") or "").strip()
        summary=str(row.get("Summary") or "").strip()
    else:
        rid=str(row.get("odiNumber") or row.get("ODINumber") or "").strip()
        date=str(row.get("dateOfIncident") or row.get("dateComplaintFiled") or "").strip()
        summary=str(row.get("summary") or row.get("Summary") or "").strip()
    if not ISSUE.fullmatch(rid):return None
    return {"id":rid,"dateReported":date[:30],"summaryExcerpt":summary[:260],
            "sourceUrl":"https://www.nhtsa.gov/recalls" if kind=="recalls"
                        else "https://www.nhtsa.gov/report-a-safety-problem"}

def build(previous=None,fetch=read_json,now=None,vehicles=VEHICLES,kinds=KINDS):
    now=now or datetime.now(KST)
    old={(r.get("type"),str(r.get("id"))) for r in (previous or {}).get("records",[])
         if isinstance(r,dict)}
    checks=[];records=[]
    for make,model,year in vehicles:
        for kind,route in kinds.items():
            uri=BASE+"/"+kind+"/"+route+"?"+urlencode({"make":make,"model":model,"modelYear":year})
            try:
                obj=fetch(uri)
                if not isinstance(obj.get("results"),list):
                    raise ValueError("Official response missing results")
                distinct=set()
                for entry in obj["results"]:
                    if not isinstance(entry,dict):continue
                    out=canonical(kind,entry)
                    if not out or out["id"] in distinct:continue
                    distinct.add(out["id"])
                    records.append({**out,"type":kind,"make":make,"model":model,
                                    "modelYear":year,"officialOriginalApi":uri,
                                    "firstSeenInMonitoring":False if not previous else
                                        (kind,out["id"]) not in old,
                                    "publicationAlreadyPublic":True,
                                    "confirmedDefect":False if kind=="complaints" else None,
                                    "scoopConfirmed":False})
                checks.append({"make":make,"model":model,"modelYear":year,
                               "type":kind,"status":"checked","count":len(distinct)})
            except (ValueError,TimeoutError,OSError) as e:
                checks.append({"make":make,"model":model,"modelYear":year,
                               "type":kind,"status":"source_error",
                               "errorType":type(e).__name__})
    if not any(c["status"]=="checked" for c in checks):
        raise ValueError("All official NHTSA queries failed; keep previous snapshot")
    records.sort(key=lambda x:(x["dateReported"],x["id"]),reverse=True)
    return {"generatedAt":now.isoformat(timespec="seconds"),
            "source":"NHTSA official US recalls and consumer complaint APIs",
            "scope":"Curated 2026 US model-year combinations only; complaints are user submissions",
            "checks":checks,"records":records[:150],
            "checkedQueries":sum(c["status"]=="checked" for c in checks),
            "failedQueries":sum(c["status"]=="source_error" for c in checks),
            "newToMonitor":sum(r["firstSeenInMonitoring"] for r in records),
            "newnessValid":previous is not None,
            "scoopConfirmed":0,
            "warning":"이미 공개된 미국 리콜/불만 접수. 한국 차량 결함 확인 또는 신규 단독·한국 판매분 적용을 뜻하지 않음."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="digests/nhtsa_official_latest.json")
    a=p.parse_args()
    dst=Path(a.out)
    prev=None
    if dst.exists():
        try:prev=json.loads(dst.read_text(encoding="utf-8"))
        except (OSError,ValueError):pass
    report=build(prev)
    dst.parent.mkdir(parents=True,exist_ok=True)
    tmp=dst.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(dst)
    print("NHTSA checked",report["checkedQueries"],"failed",report["failedQueries"],
          "new since prior snapshot",report["newToMonitor"] if report["newnessValid"] else "unknown")
if __name__=="__main__":main()
