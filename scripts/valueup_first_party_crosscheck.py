"""Attach a verifiable first-party historical target to a new issuer DART title.

This is a research cross-reference, not an automatic claim that targets rose.
Today's figures have only an indexed, already published press summary here;
the underlying issuer-uploaded DART attachment is still unread.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit,parse_qs

RECEIPT=re.compile(r"20\d{12}\Z")
STOCK=re.compile(r"\d{6}\Z")
CORP=re.compile(r"\d{8}\Z")
OFFICIAL_PRESS={"KG스틸":"www.kg-steel.co.kr"}
COVERAGE={"KG스틸":"www.digitaltoday.co.kr"}

def _public_url(url,host,*,path=None):
    if not isinstance(url,str):return False
    try:
        u=urlsplit(url)
        return (u.scheme=="https" and u.hostname==host and u.port is None
                and u.username is None and u.password is None
                and not u.fragment and (path is None or u.path==path))
    except ValueError:return False

def _day(value):
    if not isinstance(value,str):return None
    try:
        v=date.fromisoformat(value)
    except ValueError:return None
    return v if 2020<=v.year<=2030 else None

def match_official_prior(new_receipt, evidence):
    """Return only official 2025 fact + independently linked 2026 headline.

    Binding to current DART issuer, code and receipt must come from the DART
    collector, not from secondary media search or a coincidental company name.
    """
    if not isinstance(new_receipt,dict) or not isinstance(evidence,dict):return None
    if evidence.get("status")!="checked_public_issuer_release_and_earlier_news_not_primary_filing_body":
        return None
    records=evidence.get("records")
    if not isinstance(records,list) or len(records)>30:return None
    for plan in records:
        if not isinstance(plan,dict):continue
        company=plan.get("company")
        code=plan.get("corpCode")
        receipt=plan.get("currentReceiptNo")
        when=_day(plan.get("currentDate"))
        prior_announced=_day(plan.get("priorPlanAnnouncedDate"))
        prior_publication=_day(plan.get("priorCorporatePublicationDate"))
        press_day=_day(plan.get("currentHeadlineMediaPublishedDate"))
        if (company not in OFFICIAL_PRESS or
            not isinstance(code,str) or not CORP.fullmatch(code) or
            not isinstance(receipt,str) or not RECEIPT.fullmatch(receipt) or
            not isinstance(plan.get("listedStockCode"),str) or
            not STOCK.fullmatch(plan["listedStockCode"]) or
            when is None or prior_announced is None or prior_publication is None or
            press_day is None or not prior_announced<=prior_publication<when or
            press_day!=when or receipt[:8]!=when.strftime("%Y%m%d") or
            new_receipt.get("company")!=company or
            new_receipt.get("corpCode")!=code or
            new_receipt.get("receiptNo")!=receipt or
            new_receipt.get("published")!=receipt[:8] or
            new_receipt.get("sourceType")!="official_list_receipt" or
            new_receipt.get("isCorrection") is not False or
            not isinstance(new_receipt.get("report"),str) or
            not "".join(new_receipt["report"].split()).startswith("기업가치제고계획") or
            new_receipt.get("sourceUrl")!=plan.get("currentOfficialUrl")):
            continue
        current=plan.get("currentOfficialUrl")
        if not _public_url(current,"dart.fss.or.kr",path="/dsaf001/main.do"):
            continue
        if parse_qs(urlsplit(current).query)!={"rcpNo":[receipt]}:
            continue
        prior=plan.get("priorOriginalIssuerReleaseUrl")
        report=plan.get("currentHeadlineMediaUrl")
        if not (_public_url(prior,OFFICIAL_PRESS[company],path="/html/PR_view.html")
                and _public_url(report,COVERAGE[company],path="/disclosure/articleView.html")):
            continue
        if parse_qs(urlsplit(prior).query).get("no")!=["822"]:
            continue
        if parse_qs(urlsplit(report).query)!={"idxno":["707878"]}:
            continue
        a=plan.get("priorIssuerStatedTargets")
        b=plan.get("currentMediaReportedTargets")
        if not isinstance(a,dict) or not isinstance(b,dict):continue
        if (type(a.get("roeTargetPercentAtLeast")) is not int or
            a["roeTargetPercentAtLeast"]!=13 or
            type(a.get("shareholderReturnTargetPercent")) is not int or
            a["shareholderReturnTargetPercent"]!=30 or
            type(b.get("shareholderReturnPercent")) is not int or
            b["shareholderReturnPercent"]!=50 or
            b.get("shareholderReturnWindow")!="5개년" or
            type(b.get("pbrMultipleTargetAtLeast")) is not float or
            b["pbrMultipleTargetAtLeast"]!=0.5 or
            b.get("pbrTargetYear")!=2029):
            continue
        gates=("currentOfficialFilingBodyRetrieved",
               "priorAndCurrentDenominatorDefinitionVerified",
               "priorAndCurrentPeriodComparableVerified",
               "companyImpactVerified","sameAngleDomesticCoverageFulltextChecked",
               "exclusiveConfirmed","approvedForPitch")
        if any(plan.get(k) is not False for k in gates):
            continue
        if plan.get("alreadyCoveredCurrentPlanAsDisclosure") is not True:
            continue
        return {
            "kind":"historical_issuer_plan_and_new_official_title_comparison_not_equivalent",
            "currentDartReceiptNo":receipt,
            "priorIssuerAnnouncementDate":prior_announced.isoformat(),
            "priorIssuerPublishedAt":prior_publication.isoformat(),
            "priorIssuerSourceUrl":prior,
            "priorRoeTargetAtLeastPercent":13,
            "priorShareholderReturnTargetPercent":30,
            "newOfficialDartTitleVerified":True,
            "newDartUrl":current,
            "newMediaSourceUrl":report,
            "newPressReportedShareholderReturnTargetPercent":50,
            "newPressReportedWindow":"5개년",
            "newPressReportedPbrAtLeast":0.5,
            "newPressReportedPbrTargetYear":2029,
            "newOfficialAttachmentContentVerified":False,
            "denominatorMatched":False,
            "periodDefinitionMatched":False,
            "canClaimTwentyPercentagePointIncrease":False,
            "targetAchieved":False,
            "alreadyReportedNewPlanHeadline":True,
            "coverageFulltextMatched":False,
            "exclusiveConfirmed":False,
            "approvedForPitch":False,
            "editorialNote":"2025년 회사 공식 발표는 주주환원율 30%·ROE 13% 목표. 2026년 공식 DART 접수 제목은 확인했지만 50%·2029 PBR 수치는 기존 언론의 공시 소개에 기재돼 있음. 원공시 첨부 PDF의 환원율 분모·배당/자사주 범위와 5개년 기간 일치 여부를 확인하기 전 20%p 확대 또는 단독 보도라고 하지 않음."
        }
    return None
