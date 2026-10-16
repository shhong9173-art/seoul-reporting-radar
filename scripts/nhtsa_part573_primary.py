"""NHTSA Part 573 official manufacturer PDF chronology/parts reading queue.

A public U.S. Part 573 report proves what the manufacturer reported to NHTSA,
not that Korean-specification parts match, that there are Korean incidents,
or that Korea did not conduct a recall. PDF labels ('Park Outside', etc.)
also appear when their checkboxes are NOT selected; never infer flags.
"""
from __future__ import annotations

import argparse,hashlib,json,re
from pathlib import Path
from datetime import datetime,timedelta,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from slovak_ifrs_primary_pages import extract_pages

KST=timezone(timedelta(hours=9))
ROOT="https://static.nhtsa.gov/odi/rcl/2026/"
# Explicit official manufacturer report references, NOT constructed via model name.
# Documents are verified by actually downloading from official NHTSA host
# and locating the campaign number in the original PDF text.
NHTSA_REPORTS={
    "26V664000":("RCLRPT-26V664-0680.pdf",),
    "26V588000":("RCLRPT-26V588-5849.pdf","RCLRPT-26V588-0403.pdf")
}
MAX_PDF=8*1024*1024
MAX_DOCUMENTS=3
MAX_PASSAGES=9
TERMS=re.compile(
    r"chronology|description of (?:the )?defect|production dates|"
    r"component|power seat|seat motor|entrap|injur|fire|overheat|"
    r"recall number|corrective action|description of remedy|"
    r"number of potentially involved|manufacturer recall identification",
    re.I
)

def fetch_pdf(url):
    if not isinstance(url,str) or not any(
        url==ROOT+n for names in NHTSA_REPORTS.values() for n in names):
        raise ValueError("NHTSA_original_url_not_exact_allowlist")
    req=Request(url,headers={"Accept":"application/pdf",
          "User-Agent":"newsroom-official-part573-source-review/1.0"})
    with urlopen(req,timeout=22) as response:
        data=response.read(MAX_PDF+1)
    if not 2000<=len(data)<=MAX_PDF or not data.startswith(b"%PDF-"):
        raise ValueError("invalid_or_oversize_official_pdf")
    return data

# Semantic sections outrank the PDF form's generic headings. A label such
# as "Description of the safety risk, including crash, fire, death, injury"
# is printed in every Part 573 form and is NOT an actual fire allegation.
REVIEW_SECTIONS=(
    ("defect_description",re.compile(
        r"Description of the defect or noncompliance\s*:",re.I)),
    ("chronology",re.compile(
        r"Chronology of (?:Principal )?Events\s*:?",re.I)),
    ("remedy",re.compile(
        r"Description of remedy program\s*:",re.I)),
    ("production_dates",re.compile(
        r"Production Dates\s*:",re.I)),
    ("us_population",re.compile(
        r"Total number of potentially involved\s*:",re.I)),
    ("part_specification",re.compile(
        r"Part Number\s*:|component (?:part|description)\s*:",re.I))
)
US_POPULATION=re.compile(r"Total number of potentially involved\s*:\s*([\d,]+)",re.I)

def passages(pages):
    if not isinstance(pages,list):raise ValueError("missing_pdf_pages")
    flat_pages=[re.sub(r"\s+"," ",x).strip() if isinstance(x,str) else ""
                for x in pages[:90]]
    result=[]
    for kind,pattern in REVIEW_SECTIONS:
        for page_index,body in enumerate(flat_pages):
            if not body:continue
            match=pattern.search(body)
            if not match:continue
            # Preserve substantive text AFTER its specific form label, not
            # the generic risk labels printed on empty forms.
            text=body[max(0,match.start()-18):match.end()+315][:340]
            if not text:continue
            result.append({
              "page":page_index+1,
              "section":kind,
              "keyword":match.group(0)[:70],
              "literalPdfExcerpt":text,
              "incidentCountVerified":False,
              "partNumberVerifiedAgainstKoreanVehicle":False,
              "koreanRecallAbsenceVerified":False,
              "interpretation":"literal_manufacturer_part573_text_for_manual_crosscheck"
            })
            break
    # Once every unique substantive section had an opportunity to appear,
    # show additional key investigation/remedy context from later pages.
    # Limit one extra item per page. Never use generic "fire" form labels.
    if len(result)<MAX_PASSAGES:
        used={(x["page"],x["section"]) for x in result}
        for page_index,body in enumerate(flat_pages):
            if not body:continue
            for m in re.finditer(r"\b(?:investigation|supplier|confirmed|failure|thermal|overheat|"
                       r"software update|manufacturing records|complaints?)\b",body,re.I):
                if (page_index+1,"additional_context") in used:break
                # Keep a full surrounding sentence if possible.
                excerpt=body[max(0,m.start()-110):m.end()+180][:310]
                if "including crash, fire, death, injury" in excerpt.lower():
                    continue
                result.append({
                  "page":page_index+1,"section":"additional_context",
                  "keyword":m.group(0)[:50],"literalPdfExcerpt":excerpt,
                  "incidentCountVerified":False,
                  "partNumberVerifiedAgainstKoreanVehicle":False,
                  "koreanRecallAbsenceVerified":False,
                  "interpretation":"literal_manufacturer_part573_text_for_manual_crosscheck"
                })
                used.add((page_index+1,"additional_context"))
                break
            if len(result)>=MAX_PASSAGES:break
    return result[:MAX_PASSAGES]



KOREA_MARKET_PHRASE=re.compile(
    r"\b(?:Korean?\s+(?:domestic\s+)?market|Korea[- ]market"
    r"|Korean?\s+(?:domestic\s+)?(?:customer|vehicle)\s+(?:market|case|report))\b",
    re.I
)
INCIDENT_TERMS=re.compile(r"\b(?:fire|ignit(?:ion|ed)|thermal (?:incident|event)|"
    r"smoke|overheat|burned|burnt|fire allegation|alleged fire)\b",re.I)
THERMAL_ALLEGATION=re.compile(r"\bthermal\s+(?:event|incident)\s+allegations?\b",re.I)
EXPLICIT_KOREAN_INFO_DATE=re.compile(
    r"\bJuly\s+2,\s*2026\s*[-–—]\s*Hyundai\s+received\b",re.I)
BOILERPLATE_RISK="description of the safety risk, including crash, fire, death, injury"


def manufacturer_korea_market_mentions(pages):
    """Only literal source claims about Korea's market—not a verified fire.

    Production in South Korea for sale in the U.S. is NOT a Korean market
    incident. NHTSA boilerplate risk labels are not evidence of a fire.
    """
    if not isinstance(pages,list):raise ValueError("invalid_manufacturer_pdf_pages")
    findings=[]
    for i,page in enumerate(pages[:90],1):
        if not isinstance(page,str):continue
        text=re.sub(r"\s+"," ",page).strip()
        for match in KOREA_MARKET_PHRASE.finditer(text):
            snippet=text[max(0,match.start()-170):min(len(text),match.end()+200)]
            cleaned=snippet.lower().replace(BOILERPLATE_RISK,"")
            match_hazard=bool(INCIDENT_TERMS.search(cleaned))
            alleged_thermal=bool(THERMAL_ALLEGATION.search(cleaned))
            info_date=("2026-07-02" if alleged_thermal and
                        EXPLICIT_KOREAN_INFO_DATE.search(snippet) else None)
            findings.append({
              "pdfPage":i,
              "literalKoreanMarketPhrase":match.group(0),
              "contextFromUsManufacturer":snippet[:410],
              "incidentTermNearby":match_hazard,
              "incidentLanguageClassification":(
                 "thermal_event_allegation_unverified" if alleged_thermal
                 else "hazard_word_nearby_unverified" if match_hazard
                 else "market_reference_without_hazard_word"),
              "manufacturerInformationReceivedDateFromExactText":info_date,
              "explicitFireConfirmedByManufacturer":False,
              "sourceIsManufacturerClaimToNhtsa":True,
              "domesticIncidentVerified":False,
              "koreanGovernmentIncidentChecked":False,
              "domesticRecallAbsenceVerified":False,
              "koreanIdenticalPartVerified":False,
              "sameAnglePressFulltextChecked":False,
              "basis":"literal_korean_market_reference_in_us_part573"
            })
            if len(findings)>=6:return findings
    return findings


def scan(source,*,now=None,get=fetch_pdf,convert=extract_pages):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("timezone_required")
    if (not isinstance(source,dict)
        or source.get("status")!="official_us_recalls_to_review"
        or source.get("confirmedScoops")!=0
        or not isinstance(source.get("leads"),list)):
        raise ValueError("unverified_nhtsa_campaign_source")
    permitted={x.get("id") for x in source["leads"] if
        isinstance(x,dict) and x.get("usRecallExists") is True and
        x.get("koreanRecallChecked") is False and
        x.get("exclusiveConfirmed") is False}
    reports=[]
    for campaign,filenames in NHTSA_REPORTS.items():
        if campaign not in permitted:continue
        for filename in filenames:
            url=ROOT+filename
            d={
                "campaign":campaign,"reportFile":filename,
                "officialPdfUrl":url,
                "status":"not_read",
                "officialPdfDownloaded":False,
                "campaignNumberFoundInPdf":False,
                "pdfContentSHA256":None,"sourcePassages":[],
                "koreanMarketMentionsInOriginalPdf":[],
                "domesticIncidentIndependentlyVerified":False,
                "currentAmendmentVersionVerified":False,
                "exactKoreanVehiclePartMatched":False,
                "domesticRecallAbsenceVerified":False,
                "koreanIncidentsVerified":False,
                "exclusiveConfirmed":False
            }
            try:
                blob=get(url)
                if len(blob)>MAX_PDF or not blob.startswith(b"%PDF-"):
                    raise ValueError("not_bounded_real_pdf")
                pages=convert(blob)
                first=" ".join(re.sub(r"\s+"," ",x).upper()
                   for x in pages[:2] if isinstance(x,str))
                # NHTSA reports print the short campaign e.g. 26V664.
                short=campaign[:6]
                if short not in first:
                    raise ValueError("pdf_cannot_be_tied_to_exact_campaign")
                d["campaignNumberFoundInPdf"]=True
                d["officialPdfDownloaded"]=True
                d["pdfContentSHA256"]=hashlib.sha256(blob).hexdigest()
                d["sourcePassages"]=passages(pages)
                d["koreanMarketMentionsInOriginalPdf"]=manufacturer_korea_market_mentions(pages)
                exact=US_POPULATION.findall(first)
                if len(exact)==1 and exact[0].replace(",","").isdigit():
                    d["usManufacturerReportedPotentiallyAffectedVehicles"]=int(exact[0].replace(",",""))
                    d["usVehicleCountScope"]="us_market_manufacturer_part573_not_korea_sales"
                d["status"]=(
                   "nhtsa_original_part573_pdf_passages_for_review"
                   if d["sourcePassages"] else
                   "nhtsa_pdf_text_read_no_keyword_not_proof_of_no_defect")
            except (HTTPError,URLError,ValueError,TimeoutError,
                    OSError,TypeError) as err:
                d["status"]="nhtsa_original_pdf_download_or_text_error"
                d["sourceErrorType"]=type(err).__name__
            reports.append(d)
            if len(reports)>=MAX_DOCUMENTS:break
    reports.sort(key=lambda r:(r["campaign"],r["reportFile"]))
    return {
       "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
       "status":"us_official_part573_pdf_passages_not_korean_recall_conclusion",
       "sourceCampaignSnapshotAt":source.get("generatedAt"),
       "documentsAttempted":len(reports),
       "documentsRead":sum(x["officialPdfDownloaded"] for x in reports),
       "documentsWithErrors":sum(x["status"]=="nhtsa_original_pdf_download_or_text_error" for x in reports),
       "koreanEquivalentPartVerified":False,"koreanRecallAbsenceVerified":False,
       "manufacturerReportRevisionSequenceVerified":False,
       "officialPartNumberVersusKoreanVehicleVerified":False,
       "sameAnglePressFulltextVerified":False,
       "confirmedScoops":0,"approvedArticles":0,
       "warning":"NHTSA manufacturer Part 573 chronology and parts are U.S.-market reports, even if the same model name is sold in Korea. The printed Park Outside label is not itself a checked warning. Need Korean-specification parts, Korean authority actions, prior press and company public confirmation.",
       "reports":reports
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--us",default="digests/crossborder_safety_latest.json")
    ap.add_argument("--out",default="digests/nhtsa_part573_primary_latest.json")
    a=ap.parse_args()
    data=json.loads(Path(a.us).read_text(encoding="utf-8"))
    report=scan(data)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(target)
    print("NHTSA official Part573:",report["documentsAttempted"],"attempted",
          report["documentsRead"],"read",report["documentsWithErrors"],"errors",
          "Korean same parts/recall not established")
if __name__=="__main__":main()
