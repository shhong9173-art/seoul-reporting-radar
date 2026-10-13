"""Store ONLY public, URL-backed editorial fact-check events in GitHub.

No anonymous reporter/source names, off-the-record remarks, unpublished
article hypotheses, protected interview notes, or internal documents.
"""
import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

KST=timezone(timedelta(hours=9))
TYPES={"prior_coverage","company_response","actual_application",
       "industry_impact","reporting_angle"}
OUTCOMES={"verified_public","contradicted_public","needs_check"}
NUMBER=re.compile(r"^10\d{11}$")
ACTOR=re.compile(r"^[A-Za-z0-9-]{1,39}$")

def append_event(ledger,desk,publication,kind,result,url,actor,now=None):
    now=now or datetime.now(KST)
    if not isinstance(ledger.get("checks"),list):
        raise ValueError("Invalid public fact-check ledger")
    if not NUMBER.fullmatch(str(publication or "")):
        raise ValueError("Publication number must be a Korean 13-digit patent number")
    if kind not in TYPES or result not in OUTCOMES:
        raise ValueError("Invalid check type or outcome")
    if not ACTOR.fullmatch(str(actor or "")):
        raise ValueError("Authenticated GitHub actor required")
    if not isinstance(desk.get("reviewQueue"),list) or not any(
        p.get("publicationNumber")==publication for p in desk["reviewQueue"]):
        raise ValueError("Number is not in checked KIPRIS reporting source window")
    url=str(url or "").strip()
    if result!="needs_check" and not url:
        raise ValueError("Positive/negative fact checks require public evidence URL")
    if url:
        p=urlsplit(url)
        if (p.scheme!="https" or not p.hostname or p.username or p.password or
            len(url)>500 or p.hostname.lower() in ("localhost","127.0.0.1")):
            raise ValueError("Only standard public HTTPS evidence URL permitted")
    event={"publicationNumber":publication,"checkType":kind,"result":result,
           "evidenceUrl":url or None,"reviewer":actor,
           "reviewedAt":now.isoformat(timespec="seconds"),
           "evidenceScope":"reporter-labelled PUBLIC document; not an automatically verified patent-to-business connection"}
    return {**ledger,"schemaVersion":1,"checks":ledger["checks"]+[event]},event

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--ledger",default="data/patent_reporting_checks.json")
    p.add_argument("--desk",default="digests/patent_desk_latest.json")
    args=p.parse_args()
    ledger=json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    desk=json.loads(Path(args.desk).read_text(encoding="utf-8"))
    report,event=append_event(ledger,desk,os.getenv("FACTCHECK_PUBLICATION_NUMBER"),
                os.getenv("FACTCHECK_TYPE"),os.getenv("FACTCHECK_RESULT"),
                os.getenv("FACTCHECK_URL"),os.getenv("GITHUB_ACTOR"))
    output=Path(args.ledger);temp=output.with_suffix(".json.tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(output)
    print("Stored public reporter fact-check",event["publicationNumber"],event["checkType"],
          event["result"],"events",len(report["checks"]))

if __name__=="__main__":main()
