"""Collect already-public NHTSA vehicle safety evidence, not scoop claims."""
import json
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import datetime,timedelta,timezone
from pathlib import Path

CASES=[("Hyundai","IONIQ 5",2026),("Hyundai","TUCSON",2026),
       ("Kia","EV6",2026),("Kia","SORENTO",2026)]
KINDS=("recalls","complaints")
def collect(fetch=None):
 if fetch is None:
  def fetch(uri):
   with urlopen(uri,timeout=12) as response:return json.load(response)
 checks=[];records=[]
 for make,model,year in CASES:
  for kind in KINDS:
   url="https://api.nhtsa.gov/"+kind+"/"+kind+"ByVehicle?"+urlencode(
    {"make":make,"model":model,"modelYear":year})
   try:
    data=fetch(url)
    if not isinstance(data.get("results"),list):raise ValueError("missing results")
    checks.append({"make":make,"model":model,"year":year,
                   "kind":kind,"status":"checked","rows":len(data["results"])})
    for entry in data["results"][:35]:
     number=entry.get("NHTSACampaignNumber") if kind=="recalls" else entry.get("odiNumber")
     if not number:continue
     records.append({"make":make,"model":model,"year":year,"kind":kind,
                     "id":str(number),"officialApi":url,
                     "reportDate":str(entry.get("ReportReceivedDate") or
                        entry.get("dateComplaintFiled") or "")[:40],
                     "alreadyPublic":True,"confirmedScoop":False})
   except (ValueError,OSError,TimeoutError) as error:
    checks.append({"make":make,"model":model,"year":year,
                  "kind":kind,"status":"source_error","error":type(error).__name__})
 if not any(c["status"]=="checked" for c in checks):raise ValueError("all sources failed")
 return {"generatedAt":datetime.now(timezone(timedelta(hours=9))).isoformat(),
         "source":"US NHTSA official recalls and complaints",
         "checks":checks,"records":records,"scoopConfirmed":False,
         "warning":"이미 공개된 미국 리콜·불만 접수. 국내 결함·단독 인정 불가"}
def main():
 path=Path("digests/nhtsa_official_latest.json")
 result=collect();path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(".json.tmp")
 tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 tmp.replace(path)
if __name__=="__main__":main()
