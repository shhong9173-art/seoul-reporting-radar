"""Append a trusted editor's GitHub workflow_dispatch patent review.

Only repository collaborators with Actions dispatch permission can trigger the
workflow. Public notes and evidence URLs are deliberately nonconfidential.
"""
import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

KST=timezone(timedelta(hours=9))
NUMBER=re.compile(r"^10\d{11}$")
DECISIONS={
    "worth_reporting","published","already_reported",
    "wrong_beat","unsupported_angle","low_value","needs_reporting",
}


def record(ledger,source,publication_number,decision,evidence_url="",public_note="",
           reviewer="",now=None):
    now=now or datetime.now(KST)
    number=re.sub(r"[\s-]","",str(publication_number or ""))
    if not NUMBER.fullmatch(number):
        raise ValueError("Use a real 13-digit Korean patent publication number")
    if decision not in DECISIONS:
        raise ValueError("Unrecognized editorial outcome")
    if not isinstance(ledger,dict) or not isinstance(ledger.get("reviews"),list):
        raise ValueError("Missing editorial event ledger")
    if not isinstance(source,dict) or not isinstance(source.get("items"),list):
        raise ValueError("Missing source patent dataset")
    rows=[x for x in source["items"]
          if str(x.get("publicationNumber"))==number]
    if not rows:
        raise ValueError("Patent not in verified official source window; review historical source separately")
    url=str(evidence_url or "").strip()
    if url:
        parts=urlsplit(url)
        if (parts.scheme!="https" or not parts.hostname or
            parts.username is not None or parts.password is not None or
            len(url)>500 or parts.hostname in ("localhost","127.0.0.1")):
            raise ValueError("Public evidence must be a normal HTTPS URL")
    if decision in ("published","already_reported") and not url:
        raise ValueError("Published/prior-reported decisions need an actual article URL")
    public_note=str(public_note or "").strip()
    if len(public_note)>300 or "\n" in public_note or "\r" in public_note:
        raise ValueError("Only short nonconfidential single-line notes")
    reviewer=str(reviewer or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}",reviewer):
        raise ValueError("Must use GitHub-authenticated reviewer identity")
    row=rows[0]
    event={
        "publicationNumber":number,
        "decision":decision,
        "reviewedAt":now.isoformat(timespec="seconds"),
        "reviewer":reviewer,
        "patentTitle":str(row.get("title") or "")[:250],
        "publicationDate":str(row.get("publicationDate") or ""),
        "evidenceUrl":url or None,
        "publicNote":public_note or None,
        "statusNote":"담당 기자의 수동 판정. 실제 단독·특허 신규성 증명이 아님",
    }
    output={**ledger,"schemaVersion":1,
            "reviews":ledger["reviews"]+[event]}
    return output,event


def main():
    import os
    a=argparse.ArgumentParser()
    a.add_argument("--ledger",default="data/patent_editorial_reviews.json")
    a.add_argument("--source",default="digests/patent_hunt_latest.json")
    args=a.parse_args()
    path=Path(args.ledger)
    old=json.loads(path.read_text(encoding="utf-8"))
    official=json.loads(Path(args.source).read_text(encoding="utf-8"))
    result,event=record(old,official,
        os.environ.get("REVIEW_PUBLICATION_NUMBER"),
        os.environ.get("REVIEW_DECISION"),
        evidence_url=os.environ.get("REVIEW_EVIDENCE_URL"),
        public_note=os.environ.get("REVIEW_PUBLIC_NOTE"),
        reviewer=os.environ.get("GITHUB_ACTOR"))
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("Recorded human editorial judgement",event["publicationNumber"],event["decision"],
          "total review events",len(result["reviews"]))


if __name__=="__main__":
    main()
