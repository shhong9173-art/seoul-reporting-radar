"""Official Slovak Ministry of Finance RUZ accounting registry evidence.

Read-only bounded public API. The verified Kia Slovakia s.r.o. production
company has IČO 35876832; never confuse with Kia Sales Slovakia (35942894).
A filed audited financial statement is NOT proof of dividend remittance,
distributable retained earnings, or funds received by a Korean parent.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen,Request
from urllib.error import URLError,HTTPError

KST=timezone(timedelta(hours=9))
API="https://registeruz.sk/cruz-public/api/"
COMPANY_PAGE="https://www.registeruz.sk/cruz-public/domain/accountingentity/show/244945"
API_DOCS="https://registeruz.sk/cruz-public/home/api"
ICO="35876832"
EXPECTED_NAME="kiaslovakiasro"
MAX_RESPONSE=800_000
DETAIL_LIMIT=16
TARGET_YEARS=(2024,2025)

def json_get(url):
    if not isinstance(url,str) or not url.startswith(API):
        raise ValueError("untrusted_official_api_endpoint")
    request=Request(url,headers={"Accept":"application/json",
                                 "User-Agent":"industry-newsroom-official-evidence/1.0"})
    with urlopen(request,timeout=20) as response:
        payload=response.read(MAX_RESPONSE+1)
    if len(payload)>MAX_RESPONSE:raise ValueError("official_api_response_too_large")
    result=json.loads(payload)
    if not isinstance(result,dict):raise ValueError("official_api_invalid_json_object")
    return result

def endpoint(resource,**kwargs):
    if resource not in ("uctovne-jednotky","uctovna-jednotka","uctovna-zavierka"):
        raise ValueError("endpoint_not_allowlisted")
    return API+resource+"?"+urlencode(kwargs)

def norm_name(s):
    return re.sub(r"[^a-z0-9]","",str(s or "").lower())

def positive_id(v):
    return type(v) is int and 0<v<10_000_000_000

def registry_evidence(fetch=json_get,*,now=None):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("timezone_required")
    status={
       "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
       "status":"official_slovak_registry_identity_and_filing_metadata",
       "registry":"Slovak Ministry of Finance Register of Financial Statements",
       "apiDocumentation":API_DOCS,
       "companyRegistryUrl":COMPANY_PAGE,
       "company":"Kia Slovakia s. r. o.","ico":ICO,
       "companyIdentityVerified":False,
       "companyIdentityStatus":"not_checked",
       "checkedYearScope":list(TARGET_YEARS),
       "statements":[],"statementPeriodDiagnostics":[],
       "sourceQueriesSucceeded":0,
       "sourceQueriesFailed":0,
       "sourceErrors":[],
       "statementAvailabilityStatus":"unverified",
       "actualNetProfitVerified":False,
       "approvedDistributionAmountVerified":False,
       "dividendPaymentToKoreanParentVerified":False,
       "parentCashReceiptVerified":False,
       "auditedLocalStatementsReadInFull":False,
       "priorPressChecked":False,
       "exclusiveConfirmed":False,
       "warning":"Only registry metadata of the exact Kia Slovakia production entity. Existence, submission/approval of annual statements is NOT analysis of net profit, distributable reserves or parent cash remittance. PDF-only IFRS statements require manual document review."
    }
    def get(resource,**kwargs):
        out=fetch(endpoint(resource,**kwargs))
        status["sourceQueriesSucceeded"]+=1
        if not isinstance(out,dict):raise ValueError("official_api_nonobject")
        return out
    try:
        ids=get("uctovne-jednotky",**{"zmenene-od":"2000-01-01","ico":ICO,
                                    "max-zaznamov":5})
        raw=ids.get("id")
        if (not isinstance(raw,list) or not 1<=len(raw)<=5
            or ids.get("existujeDalsieId") is not False
            or not all(positive_id(x) for x in raw)):
            raise ValueError("official_registry_identifier_missing_or_ambiguous")
        matches=[]
        for entity_id in raw:
            data=get("uctovna-jednotka",id=entity_id)
            if data.get("ico")==ICO and norm_name(data.get("nazovUJ"))==EXPECTED_NAME:
                matches.append(data)
        if len(matches)!=1:
            raise ValueError("exact_legal_entity_identity_not_unique")
        entity=matches[0]
        if not positive_id(entity.get("id")):raise ValueError("missing_issuer_id")
        status["companyIdentityVerified"]=True
        status["companyIdentityStatus"]="exact_registered_name_ico_unique"
        status["officialEntityId"]=entity["id"]
        status["registryLastModified"]=entity.get("datumPoslednejUpravy")
        all_ids=entity.get("idUctovnychZavierok")
        if all_ids is None:
            status["statementAvailabilityStatus"]="accounting_filing_ids_absent_not_proof_of_none"
            return status
        if (not isinstance(all_ids,list) or
            not all(positive_id(x) for x in all_ids) or
            len(all_ids)>5000):
            raise ValueError("untrusted_statement_id_list")
        last=sorted(set(all_ids),reverse=True)[:DETAIL_LIMIT]
        found=[]
        failures=0
        for statement_id in last:
            try:
                r=get("uctovna-zavierka",id=statement_id)
                if r.get("id")!=statement_id or r.get("idUJ")!=entity["id"]:
                    raise ValueError("foreign_entity_statement_mismatch")
                period=r.get("obdobieDo")
                # Source-schema diagnostics, not interpreted financial amounts.
                status["statementPeriodDiagnostics"].append({
                    "statementId":statement_id,
                    "periodTo":str(period or "")[:12],
                    "consolidationFlag":(
                        "true" if r.get("konsolidovana") is True
                        else "false" if r.get("konsolidovana") is False
                        else "omitted"),
                    "hasSubmissionDate":bool(r.get("datumPodania"))
                })
                if not isinstance(period,str) or not re.fullmatch(r"20\d\d-12",period):
                    continue
                year=int(period[:4])
                # The RUZ API specification omits attributes with null
                # values. Missing 'konsolidovana' is NOT true and NOT
                # verified false; do not drop a valid annual filing solely
                # because this optional property was omitted.
                if year not in TARGET_YEARS or r.get("konsolidovana") is True:
                    continue
                found.append({
                    "statementId":statement_id,
                    "financialYear":year,
                    "periodFrom":r.get("obdobieOd"),
                    "periodTo":period,
                    "submitted":r.get("datumPodania"),
                    "prepared":r.get("datumZostavenia"),
                    "approved":r.get("datumSchvalenia"),
                    "statementType":str(r.get("typ") or "")[:55],
                    "basis":"official_registry_annual_filing_metadata",
                    "consolidationFlag":(
                        "explicit_non_consolidated" if r.get("konsolidovana") is False
                        else "not_specified_by_api"),
                    "sameIcoAndLegalNameConfirmed":True,
                    "profitOrDividendAmountsParsed":False,
                    "companyRegistryUrl":COMPANY_PAGE,
                    "reportIds":r.get("idUctovnychVykazov",[])[:6]
                       if isinstance(r.get("idUctovnychVykazov"),list) else []
                })
            except (ValueError,HTTPError,URLError,TimeoutError,OSError,KeyError) as err:
                failures+=1
                status["sourceQueriesFailed"]+=1
                status["sourceErrors"].append(type(err).__name__)
        # Multiple revisions or statements for a year must NOT be silently
        # treated as one definitive annual account.
        found.sort(key=lambda x:(x["financialYear"],x["statementId"]),reverse=True)
        status["statements"]=found[:8]
        if failures:
            status["statementAvailabilityStatus"]="partial_official_statement_lookup_failed"
        elif set(x["financialYear"] for x in found)==set(TARGET_YEARS):
            status["statementAvailabilityStatus"]="registered_annual_filing_metadata_for_both_years"
        elif len(all_ids)>DETAIL_LIMIT:
            status["statementAvailabilityStatus"]="bounded_recent_filing_ids_older_year_may_be_unchecked"
        else:
            status["statementAvailabilityStatus"]="one_or_more_years_not_identified_in_api"
        return status
    except (ValueError,HTTPError,URLError,TimeoutError,OSError,KeyError) as err:
        status["sourceQueriesFailed"]+=1
        status["sourceErrors"].append(type(err).__name__)
        status["companyIdentityStatus"]=(
            "official_source_error_or_exact_identity_unverified"
            if not status["companyIdentityVerified"]
            else status["companyIdentityStatus"])
        if status["companyIdentityVerified"]:
            status["statementAvailabilityStatus"]="official_statement_metadata_unavailable"
        return status

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="digests/slovakia_official_accounts_latest.json")
    args=parser.parse_args()
    report=registry_evidence()
    path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)
    print("Slovak government RUZ:",report["companyIdentityStatus"],
          "official annual filings",len(report["statements"]),
          "errors",report["sourceQueriesFailed"],
          "cash transfer verified 0")
if __name__=="__main__":main()
