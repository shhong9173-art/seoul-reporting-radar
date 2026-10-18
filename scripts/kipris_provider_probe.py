"""One bounded provider diagnostic; never write operational patent snapshots."""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from xml.etree.ElementTree import ParseError

from patent_hunt import BASE, KST, ProviderResponseError, parse_response, request_xml


def probe(key, *, fetch=request_xml, now=None):
    now=now or datetime.now(KST)
    report={"generatedAt":now.isoformat(timespec="seconds"),
            "diagnosticOnly":True,"requestsAttempted":0,
            "collectionRecovered":False,"accountUsageVerified":False,
            "providerResultCode":None,"providerMessageCategory":None,
            "confirmedScoops":0}
    if not key:
        return dict(report,status="api_key_missing")
    params={"applicant":"현대자동차주식회사",
            "openDate":(now-timedelta(days=7)).strftime("%Y%m%d")+"~"+now.strftime("%Y%m%d"),
            "patent":"true","utility":"false","sortSpec":"OPD",
            "descSort":"true","pageNo":"1","numOfRows":"1","ServiceKey":key}
    report["requestsAttempted"]=1
    try:
        parsed=parse_response(fetch(BASE+"?"+urlencode(params)))
        report.update(status="single_query_responded",reportedTotal=parsed["total"],
                      returnedRows=len(parsed["items"]))
    except ProviderResponseError as error:
        # Safe code/category only, never the body or key-bearing request URL.
        report.update(status="provider_rejected",
                      providerResultCode=str(error).rsplit(" ",1)[-1],
                      providerMessageCategory=error.category)
    except HTTPError as error:
        report.update(status="http_error",httpStatus=int(error.code))
    except (URLError, OSError, TimeoutError):
        report["status"]="transport_error"
    except (ValueError, ParseError):
        report["status"]="response_invalid"
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",required=True,help="Isolated diagnostic JSON, not a source snapshot")
    args=p.parse_args()
    out=Path(args.out).resolve()
    if "digests" in out.parts:
        p.error("운영 digests 파일에 진단 결과를 저장할 수 없습니다")
    report=probe(os.getenv("KIPRIS_SERVICE_KEY","").strip())
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    # This program diagnoses rejection successfully, not collection recovery.
    # Callers must examine status/collectionRecovered, never the exit code alone.


if __name__=="__main__":main()
