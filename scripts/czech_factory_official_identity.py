"""Czech government ARES legal identity for Hyundai's Nosovice factory.

ARES confirms the legal entity (IČO), not audited annual statements or a
dividend from Czech factory to Korean parent. Justice's official collection
of documents requires a separate authenticated document-by-document check.
"""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

KST=timezone(timedelta(hours=9))
ICO="27773035"
OFFICIAL_API="https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/"+ICO
JUSTICE="https://www.or.justice.cz/ias/ui/rejstrik"
COMPANY_NAME="Hyundai Motor Manufacturing Czech s.r.o."

def load_company():
    req=Request(OFFICIAL_API,headers={"Accept":"application/json",
                  "User-Agent":"industry-newsroom-registered-entity-check/1.0"})
    with urlopen(req,timeout=20) as response:
        data=response.read(500_001)
    if len(data)>500_000:raise ValueError("oversized_official_api")
    return json.loads(data)

def verify(fetch=load_company,*,now=None):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("timezone required")
    result={
      "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
      "status":"czech_official_ares_issuer_identity_only",
      "company":COMPANY_NAME,"ico":ICO,"sourceUrl":OFFICIAL_API,
      "justiceCollectionSearchUrl":JUSTICE,
      "identityVerified":False,"identityStatus":"not_checked",
      "czechAuditedAccountsDocumentChecked":False,
      "czechDividendDistributionVerified":False,
      "koreanParentCashReceiptVerified":False,
      "exclusiveConfirmed":False,
      "warnings":["ARES company identity is not a financial statement",
                  "Czech justice Collection of Documents PDF filings must be checked independently for reporting period, net income and distribution resolutions",
                  "Hyundai Czech vehicle importer (IČO 28399757) is a distinct company from the manufacturing plant (IČO 27773035)"]
    }
    try:
        doc=fetch()
        if not isinstance(doc,dict):raise ValueError("invalid_ares_result")
        if str(doc.get("ico"))!=ICO:raise ValueError("wrong_company_ico")
        norm=lambda x:re.sub(r"[^a-z0-9]","",str(x).lower())
        if norm(doc.get("obchodniJmeno"))!=norm(COMPANY_NAME):
            raise ValueError("wrong_registered_legal_name")
        result["identityVerified"]=True
        result["identityStatus"]="exact_company_ico_and_registered_name"
        result["companyFormationDate"]=doc.get("datumVzniku")
        result["legalFormCode"]=doc.get("pravniForma")
        return result
    except (ValueError,KeyError,TypeError,HTTPError,URLError,OSError,TimeoutError) as err:
        result["identityStatus"]="official_api_unavailable_or_wrong_legal_entity"
        result["errorType"]=type(err).__name__
        return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default="digests/czech_factory_official_identity_latest.json")
    a=parser.parse_args()
    report=verify()
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
    print("Czech ARES Hyundai plant",report["identityStatus"],
          "accounts audited/PDF 0, money remitted 0")
if __name__=="__main__":main()
