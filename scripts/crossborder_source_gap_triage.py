"""Reporter-grade overseas-vs-domestic evidence-gap dossiers.

This intentionally does NOT identify scoops automatically. An overseas
public record and absent Korean API connection are not a Korean non-recall,
a different Korea-sold part, unreported facts, or an actual money transfer.

Inputs are already-collected official NHTSA archive and OpenDART filing note
excerpts. The one-sentence issuer dividend recognition extractor is reused
to upgrade weak proximity evidence only when the text itself warrants it.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode

from dart_foreign_dividend_watch import exact_dividend_income_recognition

KST=timezone(timedelta(hours=9))
US_RECALL=re.compile(r"^\d{2}V\d{3,6}$")
DART_RECEIPT=re.compile(r"^20\d{12}$")
MAX_AGE_DAYS=45
DOMESTIC_RECALL_URL="https://www.car.go.kr/ri/stat/list.do"
# Known Korean names for model-name search only, never exact part mapping.
KOREAN_QUERY_MODELS={"G80":"G80","GENESIS":"제네시스",
                     "IONIQ 9":"아이오닉9","IONIQ9":"아이오닉9"}


def manual_korean_model_search(models):
    names=[]
    for row in models[:35] if isinstance(models,list) else []:
        if not isinstance(row,dict):continue
        name=KOREAN_QUERY_MODELS.get(str(row.get("model") or "").strip().upper())
        if name and name not in names:
            names.append(name)
    return [{
        "searchTerm":name,
        "officialSearchUrl":DOMESTIC_RECALL_URL+"?"+urlencode({
            "ctype":"O","currentPageNo":"1","searchProductName":name}),
        "searchResultRead":False,
        "matchingRecallVerified":False,
        "absenceOfRecallVerified":False,
        "koreanIdenticalComponentVerified":False
    } for name in names[:3]]


def parsed_time(stamp):
    try:
        value=datetime.fromisoformat(str(stamp))
        return value if value.utcoffset() is not None else None
    except (TypeError,ValueError):
        return None

def validated_nhtsa(item):
    no=item.get("id") if isinstance(item,dict) else None
    return (isinstance(no,str) and US_RECALL.fullmatch(no)
            and item.get("sourceUrl") ==
            "https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber="+no
            and item.get("usRecallExists") is True
            and item.get("exclusiveConfirmed") is False
            and item.get("koreanRecallChecked") is False
            and item.get("koreanIncidentVerified") is False)

def safety_dossier(row,now):
    if not validated_nhtsa(row):return None
    day=row.get("officialDate")
    try:
        public_day=datetime.strptime(day,"%Y%m%d").date()
    except (ValueError,TypeError):
        return None
    age=(now.date()-public_day).days
    if age<0:return None
    safety_flags=row.get("flags") or []
    high_harm=("fire_or_thermal_word_in_us_summary" in safety_flags
               or "us_park_outside_advice" in safety_flags)
    return {
      "id":"usrecall:"+row["id"],"type":"overseas_safety_domestic_comparison",
      "companyGroup":"현대차·기아·제네시스" if any(m in ("GENESIS","HYUNDAI","KIA")
                                 for m in row.get("makes",[])) else "other",
      "headline":"미국 리콜 "+row["id"]+" · 국내 동일 부품/시정조치 대조 필요",
      "officialPublicationDate":public_day.isoformat(),
      "publicationAgeDays":age,
      "reportingWindowStatus":(
          "recent_official_record_needs_domestic_checks" if age<=14
          else "older_public_record_background_only"),
      "reporterPriority":"domestic_crosscheck_first" if age<=14 and high_harm else "background_followup",
      "sourceEvidence":[{
          "system":"NHTSA","scope":"US vehicle recall campaign",
          "identifier":row["id"],"url":row["sourceUrl"],
          "verifiedFact":"U.S. campaign officially published",
          "originalDocumentRead":"archive_flat_record_only_not_Part573_chronology"
      }],
      "officialFact":{
          "usCampaign":row["id"],
          "usModelYears":[{"model":str(x.get("model") or "")[:70],
                           "year":str(x.get("year") or "")[:8]}
                          for x in (row.get("models") or [])[:30]
                          if isinstance(x,dict)],
          "usDefectSummary":str(row.get("defect") or "")[:550],
          "riskWordingFlagged":high_harm
      },
      "criticalEvidenceNotYetVerified":[
          "NHTSA Part 573 chronology, exact component and U.S. affected part/specification",
          "Korea-sold variant actual part number/production range; cannot infer it from U.S. model name",
          "Korean MOLIT/KATRI official recall and free-repair records for those exact parts",
          "Domestic incident report or absence of recall NOT established",
          "Previous publication of this precise Korea-US discrepancy by Korean/overseas press"
      ],
      "sourceAvailability":{
          "nhtsaArchive":"available",
          "part573Attachments":"not_collected",
          "koreanOfficialRecall":"api_not_connected_requires_authorization",
          "pressFulltext":"not_collected",
          "domesticIdenticalPart":"not_verified"
      },
      "officialComparisonLinks":[row["sourceUrl"],DOMESTIC_RECALL_URL],
      "koreanModelSearchLinks":manual_korean_model_search(row.get("models") or []),
      "domesticRecallSearchPageIsNotEvidenceOfNoRecall":True,
      "pitchGate":{
          "primaryUSRecord":True,
          "domesticOfficialChecked":False,
          "exactComponentMatch":False,
          "domesticIncidentVerified":False,
          "sameAnglePriorPressChecked":False,
          "companyImpactVerified":False,
          "approvedForPitch":False,
          "exclusiveConfirmed":False
      },
      "questionsForPublicSources":[
          "자동차리콜센터에서 해당 차종·연식과 실제 부품의 국내 리콜·무상수리 기록 확인",
          "NHTSA 제조사 Part 573 보고서에서 해당 부품·제작기간과 위험 설명 확인",
          "현대차·기아 홍보팀에 국내 판매 사양의 동일 부품 적용 여부 및 공개된 시정조치만 질의",
          "국내외 기보도 기사 전문에서 동일한 국내 적용 쟁점이 보도됐는지 확인"
      ],
      "publicationAloneIsNotScoop":True
    }

def validate_dividend_source(item):
    receipt=item.get("receiptNo") if isinstance(item,dict) else None
    return (isinstance(receipt,str) and DART_RECEIPT.fullmatch(receipt)
       and item.get("filingUrl")==
        "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt
       and item.get("company") in ("현대자동차","기아")
       and item.get("cashReceiptVerified") is False
       and item.get("scoopConfirmed") is False)

def recognized_dividend_dossiers(row):
    if not validate_dividend_source(row):
        return []
    if row.get("evidenceTier")=="exact_issuer_recognized_dividend_income":
        phrases=[row]
        reclassified=False
    else:
        # The persisted excerpt was derived from a public DART primary
        # document. Upgrade ONLY if named subsidiary + income recognition +
        # KRW amount are in the same exact phrase.
        raw=str(row.get("tableExcerpt") or "")
        phrases=exact_dividend_income_recognition(raw,row["company"],row["receiptNo"])
        reclassified=True
    results=[]
    for phrase in phrases[:6]:
        if (phrase.get("evidenceTier")!="exact_issuer_recognized_dividend_income"
            or phrase.get("cashReceiptVerified") is not False
            or phrase.get("separateFinancialStatementsVerified") is not False
            or not isinstance(phrase.get("issuerNamedRecognitionAmount"),str)
            or not re.fullmatch(r"\d{1,3}(?:,\d{3})+|\d{1,14}",
                                phrase["issuerNamedRecognitionAmount"])
            or phrase.get("issuerUnit")!="백만원"):
            continue
        amount=phrase["issuerNamedRecognitionAmount"]
        legal_entity=phrase.get("namedEntity")
        if not isinstance(legal_entity,str) or len(legal_entity)>110:continue
        receipt=row["receiptNo"]
        res={
          "id":"dart-dividend:"+receipt+":"+row["company"]+":"+str(len(results)+1),
          "type":"foreign_subsidiary_dividend_accounting",
          "companyGroup":row["company"],"headline":row["company"]+" 해외법인 배당수익 인식액 · 현금회수·현지 손익 교차검증",
          "officialPublicationDate":receipt[:4]+"-"+receipt[4:6]+"-"+receipt[6:8],
          "sourceEvidence":[{
              "system":"OpenDART","identifier":receipt,"url":row["filingUrl"],
              "scope":"issuer disclosed note; exact named entity recognition phrase",
              "originalDocumentRead":"saved_primary_filing_excerpt_exact_statement" if reclassified
                                     else "official_document_exact_phrase",
              "verifiedFact":"Issuer reported named-entity dividend income recognition, not cash remittance"
          }],
          "officialFact":{
              "recognizedFromEntity":legal_entity,
              "recognizedDividendIncomeText":amount+"백만원",
              "recognizedAmountInMillionKrw":int(amount.replace(",","")),
              "recognizedPeriodLabel":phrase.get("issuerRecognizedPeriod"),
              "companyAccountingLine":"배당금수익",
              "issuerOriginalPhrase":str(phrase.get("recognitionPhrase") or "")[:220],
              "unit":"백만원"
          },
          "sourceAvailability":{
              "dartIssuerNote":"exact_named_recognition_phrase_present",
              "foreignLocalRegistry":"not_connected",
              "koreanCashFlowPaymentEvidence":"not_verified",
              "issuerSeparateVsConsolidatedNote":"not_verified",
              "priorPressFulltext":"not_collected"
          },
          "criticalEvidenceNotYetVerified":[
              "Separate vs consolidated statements and issuer's accounting period",
              "Accounting recognition ≠ actual cash remittance; verify bank/cash-flow disclosures only if publicly available",
              "Slovak/Czech local company distribution resolutions and retained earnings / profit period",
              "Local currency exchange rates and any withholding taxes cannot be inferred from Korean note",
              "Prior coverage of exact amount and overseas-to-parent remittance claim"
          ],
          "pitchGate":{
              "issuerSpecificDividendRecognition":True,
              "cashReceivedByParentVerified":False,
              "foreignCompanyLegalAccountsVerified":False,
              "priorProfitYearVerified":False,
              "sameAnglePriorPressChecked":False,
              "companyImpactVerified":False,
              "approvedForPitch":False,
              "exclusiveConfirmed":False
          },
          "questionsForPublicSources":[
              "DART 원문의 별도/연결 재무제표 구분, 2026년 반기 배당수익 인식 계정 확인",
              "현지 법인의 공개 배당결의·감사재무제표에서 배당의 귀속 이익연도 확인",
              "회사 홍보팀에 공시 수치의 회계적 의미와 현금수령 여부 중 공개 가능한 자료만 확인",
              "같은 해외 법인·금액에 관한 국내외 기보도와 최초 공개일 확인"
          ],
          "reporterPriority":"accounting_meaning_and_prior_press_first",
          "reportingWindowStatus":"historical_public_filing_to_investigate",
          "publicationAloneIsNotScoop":True
        }
        results.append(res)
    return results

def attach_slovak_registry(dossier, registry):
    """Keep government annual-filing *metadata* separate from DART income."""
    if (not isinstance(registry,dict)
        or registry.get("status")!="official_slovak_registry_identity_and_filing_metadata"
        or registry.get("ico")!="35876832"
        or registry.get("companyIdentityVerified") is not True
        or registry.get("companyIdentityStatus")!="exact_registered_name_ico_unique"
        or registry.get("companyRegistryUrl")!=
          "https://www.registeruz.sk/cruz-public/domain/accountingentity/show/244945"
        or not isinstance(registry.get("statements"),list)
        or any(registry.get(x) is not False for x in (
            "actualNetProfitVerified","approvedDistributionAmountVerified",
            "dividendPaymentToKoreanParentVerified","parentCashReceiptVerified",
            "auditedLocalStatementsReadInFull","exclusiveConfirmed"))):
        dossier["slovakGovernmentAccounts"]={"status":
            "not_verified_or_official_source_failed",
            "individualAnnualFilings":[],"officialEntityVerified":False,
            "fundingSourceVerified":False,"dividendPaymentVerified":False}
        return dossier
    valid=[]
    for x in registry["statements"][:8]:
        if (not isinstance(x,dict)
            or x.get("financialYear") not in (2024,2025)
            or x.get("sameIcoAndLegalNameConfirmed") is not True
            or x.get("profitOrDividendAmountsParsed") is not False
            or x.get("basis")!="official_registry_annual_filing_metadata"):
            continue
        valid.append({
            "financialYear":x["financialYear"],"periodTo":x.get("periodTo"),
            "submitted":x.get("submitted"),"approved":x.get("approved"),
            "statementType":x.get("statementType"),
            "statementId":x.get("statementId"),
            "officialIfrsReportDetailUrl":(
                x.get("officialIfrsReportDetailUrl")
                if x.get("officialIfrsReportDetailUrl")==
                   "https://www.registeruz.sk/cruz-public/domain/financialreport/show/"+
                   str({2024:9718744,2025:10298519}[x["financialYear"]])
                else None),
            "profitAndDistributionAmountsNotInspected":True
        })
    dossier["slovakGovernmentAccounts"]={
        "status":registry.get("statementAvailabilityStatus"),
        "officialEntityVerified":True,
        "ico":"35876832",
        "registryUrl":registry["companyRegistryUrl"],
        "individualAnnualFilings":valid,
        "fundingSourceVerified":False,
        "dividendPaymentVerified":False,
        "companyCashReceivedVerified":False,
        "auditedPdfReviewed":False
    }
    dossier["sourceAvailability"]["foreignLocalRegistry"]=(
        "exact_company_official_filing_metadata_only"
    )
    dossier["criticalEvidenceNotYetVerified"].append(
        "2024/2025 IFRS auditor PDF notes must be opened to test distributable profits, dividends payable and cash settlement"
    )
    return dossier



def attach_verified_slovak_pdf_clues(dossier,registry,pdf):
    """Only PDF page references with verified official bytes; no cash inference."""
    result={"status":"official_pdf_review_not_completed",
            "governmentHashVerifiedReports":0,"passages":[],
            "amountsIndependentlyAudited":False,
            "parentCashReceiptVerified":False,
            "distributionResolutionVerified":False}
    dossier["slovakPdfPrimaryReview"]=result
    if (not isinstance(pdf,dict) or not isinstance(registry,dict) or
        pdf.get("status")!="official_slovak_ifrs_pdf_review_clues_not_validated_dividend_transfer" or
        pdf.get("ico")!="35876832" or
        registry.get("ico")!="35876832" or
        pdf.get("sourceRegistryGeneratedAt")!=registry.get("generatedAt") or
        not isinstance(pdf.get("reports"),list) or
        any(pdf.get(k) is not False for k in
            ("financialFiguresInterpreted","dividendDistributionResolutionVerified",
             "koreanParentCashReceiptVerified","dividendPaymentToParentVerified",
             "exclusiveConfirmed"))):
        return dossier
    expected={
        2024:(6499422,9718744),
        2025:(6995571,10298519)
    }
    known={(x.get("financialYear"),x.get("statementId"))
           for x in registry.get("statements",[]) if isinstance(x,dict)}
    for row in pdf["reports"]:
        if not isinstance(row,dict):continue
        year=row.get("year")
        if (year not in expected or
            (year,row.get("statementId")) not in known or
            row.get("reportId")!=expected[year][1] or
            row.get("pdfReadAndOfficialHashVerified") is not True or
            not isinstance(row.get("sha256"),str) or
            re.fullmatch(r"[a-f0-9]{64}",row["sha256"]) is None or
            row.get("status") not in (
                "official_pdf_text_passages_for_manual_review",
                "verified_pdf_no_indexed_words_not_proof_of_no_dividend")):
            continue
        url=row.get("attachmentUrl")
        if (not isinstance(url,str) or
            re.fullmatch(r"https://www\.registeruz\.sk/cruz-public/domain/financialreport/attachment/[1-9]\d{3,11}",url) is None):
            continue
        result["governmentHashVerifiedReports"]+=1
        for passage in row.get("pageClues",[])[:5]:
            if (not isinstance(passage,dict) or
                type(passage.get("page")) is not int or
                not 1<=passage["page"]<=90 or
                passage.get("containsFinancialAmountValidated") is not False or
                passage.get("cashPaidOrRetainedProfitValidated") is not False):
                continue
            result["passages"].append({
                "financialYear":year,"page":passage["page"],
                "sourceTextExcerpt":str(passage.get("sourceTextExcerpt") or "")[:310],
                "officialOriginalPdfUrl":url,
                "documentSha256":row["sha256"],
                "evidenceBasis":"exact_official_pdf_checksum_and_page_text_keyword",
                "businessImpactVerified":False,
                "companyParentCashTransferVerified":False
            })
    # Exact calendar-year accounting rows are stronger than search-word
    # snippets, but do NOT identify the recipient, 2026 distributions or
    # whether the Korean parent physically received cash.
    result["auditedCalendarYearRows"]=[]
    result["auditedYearRowConflicts"]=0
    eligible={(r["year"],r["attachmentUrl"],r["sha256"])
              for r in pdf["reports"] if isinstance(r,dict)
              and r.get("pdfReadAndOfficialHashVerified") is True
              and r.get("year") in (2024,2025)
              and isinstance(r.get("attachmentUrl"),str)
              and isinstance(r.get("sha256"),str)
              and re.fullmatch(r"[a-f0-9]{64}",r["sha256"])}
    for m in (pdf.get("annualAccountingMatrix") or [])[:12]:
        if (not isinstance(m,dict) or
            m.get("metric") not in ("dividend_cash_outflow",
                "annual_profit_cf_reconciliation","retained_earnings_balance")
            or m.get("calendarYear") not in (2023,2024,2025)
            or m.get("unit")!="EUR_thousands"
            or m.get("manualSourceTableReviewConfirmed") is not False
            or m.get("koreanParentCashReceiptVerified") is not False
            or m.get("samePeriodAs2026KiaDartDividendIncome") is not False
            or not isinstance(m.get("sourceDocuments"),list)
            or not m["sourceDocuments"]):
            continue
        documents=m["sourceDocuments"]
        if any((d.get("reportYear"),d.get("pdfUrl"),d.get("documentSha256"))
               not in eligible or
               d.get("reportedAs") not in ("reporting_year","comparative_previous_year")
               or type(d.get("sourcePdfPage")) is not int or
               d["sourcePdfPage"] not in (7,9)
               for d in documents if isinstance(d,dict)):
            continue
        if not all(isinstance(d,dict) for d in documents):
            continue
        conflict=m.get("annualValueWithheldBecauseContradiction") is True
        if conflict:
            result["auditedYearRowConflicts"]+=1
        value=m.get("value")
        if value is None and not conflict:continue
        if value is not None and (type(value) is not int or conflict):continue
        result["auditedCalendarYearRows"].append({
          "metric":m["metric"],"metricLabelKo":m.get("metricLabelKo"),
          "year":m["calendarYear"],"amountThousandEur":value,
          "sourceCount":len(documents),
          "annualReportComparativeConflict":conflict,
          "sourceDocuments":documents,
          "amountFromKiaParentDart2026":False,
          "parentRecipientVerified":False,
          "koreanCashReceiptVerified":False,
          "year2026LocalPaymentNotYetVerified":True,
          "humanAuditOfParsedRowCompleted":False
        })
    result["status"]=("verified_pdf_keyword_pages_for_manual_accounting_review"
                      if result["passages"] else
                      "official_pdf_verified_no_searchable_matching_phrase_not_proof_of_none"
                      if result["governmentHashVerifiedReports"] else
                      "not_verified")
    return dossier



def attach_nhtsa_part573_primary(dossier,source,us_archive):
    """Connect only exact campaign, official PDF host, recognized PDF text."""
    payload={"status":"not_downloaded_or_campaign_not_verified",
             "originalReportsRead":0,"passages":[],
             "koreanMarketSourceClaims":[],
             "koreanMarketIncidentIndependentlyVerified":False,
             "usManufacturerReportedAffectedCount":None,
             "usVehicleCountScope":"official_us_market_not_korean_sales",
             "differentPdfVersionsAffectedCountConflict":False,
             "koreanSameComponentVerified":False,
             "koreanRecallAbsenceVerified":False,
             "priorSameAngleNewsChecked":False}
    dossier["nhtsaPart573Original"]=payload
    if (not isinstance(source,dict) or
        source.get("status")!="us_official_part573_pdf_passages_not_korean_recall_conclusion" or
        source.get("sourceCampaignSnapshotAt")!=us_archive.get("generatedAt") or
        not isinstance(source.get("reports"),list) or
        any(source.get(field) is not False for field in (
             "koreanEquivalentPartVerified","koreanRecallAbsenceVerified",
             "manufacturerReportRevisionSequenceVerified",
             "officialPartNumberVersusKoreanVehicleVerified",
             "sameAnglePressFulltextVerified")) or
        source.get("confirmedScoops")!=0):
        return dossier
    campaign=dossier["officialFact"]["usCampaign"]
    valid_documents={
        "26V664000":{"RCLRPT-26V664-0680.pdf"},
        "26V588000":{"RCLRPT-26V588-5849.pdf","RCLRPT-26V588-0403.pdf"}
    }
    collected_us_counts=[]
    for r in source["reports"]:
        if (not isinstance(r,dict) or r.get("campaign")!=campaign or
            r.get("reportFile") not in valid_documents.get(campaign,set()) or
            r.get("officialPdfUrl")!=
              "https://static.nhtsa.gov/odi/rcl/2026/"+r["reportFile"] or
            r.get("officialPdfDownloaded") is not True or
            r.get("campaignNumberFoundInPdf") is not True or
            r.get("exactKoreanVehiclePartMatched") is not False or
            r.get("domesticRecallAbsenceVerified") is not False or
            not isinstance(r.get("pdfContentSHA256"),str) or
            re.fullmatch(r"[a-f0-9]{64}",r["pdfContentSHA256"]) is None):
            continue
        payload["originalReportsRead"]+=1
        # A verified original PDF may recount an allegation *in Korea*.
        # Quoting that source is NOT independent verification of an event.
        for mention in (r.get("koreanMarketMentionsInOriginalPdf") or [])[:5]:
            if (not isinstance(mention,dict) or
                mention.get("basis")!="literal_korean_market_reference_in_us_part573"
                or mention.get("sourceIsManufacturerClaimToNhtsa") is not True
                or any(mention.get(k) is not False for k in (
                  "domesticIncidentVerified","koreanGovernmentIncidentChecked",
                  "domesticRecallAbsenceVerified","koreanIdenticalPartVerified",
                  "sameAnglePressFulltextChecked"))
                or type(mention.get("pdfPage")) is not int
                or not 1<=mention["pdfPage"]<=90):
                continue
            payload["koreanMarketSourceClaims"].append({
                "pdfPage":mention["pdfPage"],
                "literalKoreanMarketPhrase":str(mention.get("literalKoreanMarketPhrase") or "")[:100],
                "usManufacturerContext":str(mention.get("contextFromUsManufacturer") or "")[:410],
                "incidentTermNearby":mention.get("incidentTermNearby") is True,
                "officialPdfUrl":r["officialPdfUrl"],
                "sourcePdfSHA256":r["pdfContentSHA256"],
                "sourceIsManufacturerAllegationOnly":True,
                "domesticIncidentIndependentlyVerified":False,
                "domesticIdenticalPartVerified":False,
                "koreanRecallAbsenceVerified":False
            })
        us_count=r.get("usManufacturerReportedPotentiallyAffectedVehicles")
        if (type(us_count) is int and 0<us_count<5_000_000
            and r.get("usVehicleCountScope")==
              "us_market_manufacturer_part573_not_korea_sales"):
            collected_us_counts.append(us_count)
        for z in r.get("sourcePassages",[])[:6]:
            if not isinstance(z,dict) or not isinstance(z.get("page"),int) or not 1<=z["page"]<=90 or z.get("koreanRecallAbsenceVerified") is not False or z.get("partNumberVerifiedAgainstKoreanVehicle") is not False:
                continue
            payload["passages"].append({
                "page":z["page"],"officialPart573PdfUrl":r["officialPdfUrl"],
                "literalPdfExcerpt":str(z.get("literalPdfExcerpt") or "")[:305],
                "sourcePdfSHA256":r["pdfContentSHA256"],
                "basis":"nhtsa_us_manufacturer_original_pdf_unmatched_to_korea",
                "koreanSamePartVerified":False,
                "domesticRecallAbsentVerified":False
            })
    if collected_us_counts:
        if len(set(collected_us_counts))==1:
            payload["usManufacturerReportedAffectedCount"]=collected_us_counts[0]
        else:
            payload["differentPdfVersionsAffectedCountConflict"]=True
    payload["status"]=(
      "us_manufacturer_part573_pages_require_korean_spec_check"
      if payload["originalReportsRead"] else "official_us_original_pdf_unavailable")
    return dossier


def build(safety,dividends,*,now=None,slovakia=None,czech=None,slovak_pdf=None,nhtsa_part573=None):
    now=now or datetime.now(KST)
    if now.utcoffset() is None:raise ValueError("timezone_required")
    if (not isinstance(safety,dict) or not isinstance(dividends,dict)
        or safety.get("status")!="official_us_recalls_to_review"
        or dividends.get("status")!="evidence_excerpts_not_verified_dividend_receipts"
        or safety.get("confirmedScoops")!=0
        or dividends.get("confirmedScoops")!=0
        or not isinstance(safety.get("leads"),list)
        or not isinstance(dividends.get("leads"),list)):
        raise ValueError("source_invalid_do_not_publish_zero")
    source_dates=[parsed_time(x.get("generatedAt")) for x in (safety,dividends)]
    if any(x is None or x>now+timedelta(minutes=20) for x in source_dates):
        raise ValueError("unverified_source_creation_time")
    source_states={
        "nhtsaOfficial":("checked" if
             safety.get("archiveLatestReceived") and
             isinstance(safety.get("campaignCount"),int)
             else "unverified_archive_status"),
        "dartOfficialDividendNotes":(
            "checked_some_receipts" if any(
              x.get("status")=="checked" for x in dividends.get("sourceChecks",[])
              if isinstance(x,dict))
            else "no_official_receipt_checked"),
        "koreanRecallAPI":"not_connected_permission_required",
        "foreignSubsidiaryRegistries":(
           "slovak_issuer_metadata_only" if isinstance(slovakia,dict) and
            slovakia.get("companyIdentityVerified") is True else
            "not_connected_or_official_api_failed"),
        "czechSubsidiaryRegistry":(
            "manufacturer_official_legal_identity_only"
            if isinstance(czech,dict) and czech.get("identityVerified") is True
            and czech.get("status")=="czech_official_ares_issuer_identity_only"
            and czech.get("ico")=="27773035"
            and czech.get("czechAuditedAccountsDocumentChecked") is False
            else "not_connected_or_ares_identity_unavailable"),
        "sameAngleNewsFulltext":"not_verified"
    }
    dossiers=[]
    for x in safety["leads"][:100]:
        y=safety_dossier(x,now.astimezone(KST))
        if y:
            attach_nhtsa_part573_primary(y,nhtsa_part573,safety)
            dossiers.append(y)
    for x in dividends["leads"][:100]:
        generated=recognized_dividend_dossiers(x)
        for d in generated:
            # Only the precisely named Slovak manufacturing entity can be
            # linked to the official registry. Czech entities are UNCONNECTED.
            if (d["companyGroup"]=="기아" and
                "kiaslovakia" in "".join(
                   str(d["officialFact"]["recognizedFromEntity"]).lower().split())):
                attach_slovak_registry(d,slovakia)
                attach_verified_slovak_pdf_clues(d,slovakia,slovak_pdf)
            dossiers.append(d)
    unique={}
    for d in dossiers:
        if d["id"] in unique:raise ValueError("duplicate_evidence_dossier")
        unique[d["id"]]=d
    dossiers.sort(key=lambda x:(x["type"]!="overseas_safety_domestic_comparison",
                                x["publicationAloneIsNotScoop"] is not True,x["id"]))
    return {
      "generatedAt":now.astimezone(KST).isoformat(timespec="seconds"),
      "status":"crossborder_reporter_evidence_gap_not_exclusive",
      "officialSourceGeneratedAt":{
          "nhtsa":safety["generatedAt"],"dartDividend":dividends["generatedAt"],
          "slovakGovernmentRegistry":slovakia.get("generatedAt")
              if isinstance(slovakia,dict) else None,
          "czechAresRegistry":czech.get("generatedAt")
              if isinstance(czech,dict) else None},
      "sourceHealth":source_states,
      "sourceStale48h":any((now-x).total_seconds()>48*3600 for x in source_dates),
      "slovakPdfOriginalEvidenceGeneratedAt":(
          slovak_pdf.get("generatedAt") if isinstance(slovak_pdf,dict) else None),
      "foreignLegalEntityLinks":{
          "kiaSlovakia":{
              "company":"Kia Slovakia s. r. o.","ico":"35876832",
              "identityVerified":slovakia.get("companyIdentityVerified") is True
                    if isinstance(slovakia,dict) else False,
              "officialRegisterUrl":"https://www.registeruz.sk/cruz-public/domain/accountingentity/show/244945",
              "auditedAccountsContentsReviewed":False,"dividendsPaidVerified":False,
          },
          "hyundaiCzechFactory":{
              "company":"Hyundai Motor Manufacturing Czech s.r.o.",
              "ico":"27773035",
              "identityVerified":czech.get("identityVerified") is True
                      if isinstance(czech,dict) and czech.get("status")==
                          "czech_official_ares_issuer_identity_only" else False,
              "officialCompanyUrl":"https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/27773035",
              "officialJusticeCollection":"https://www.or.justice.cz/ias/ui/rejstrik",
              "auditedAccountsContentsReviewed":False,
              "dividendsPaidVerified":False
          }
      },
      "dossierCount":len(dossiers),
      "usSafetyDossiers":sum(x["type"]=="overseas_safety_domestic_comparison" for x in dossiers),
      "issuerExactDividendDossiers":sum(x["type"]=="foreign_subsidiary_dividend_accounting" for x in dossiers),
      "domesticRecallAbsenceVerified":False,
      "foreignParentCashTransferVerified":False,
      "confirmedScoops":0,"approvedArticles":0,
      "warning":"US recall ≠ Korea recall absence. DART dividend income recognition ≠ cash transferred; original record already public, press same angle unknown. New first-monitor observation ≠ scoop.",
      "items":dossiers[:100]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--nhtsa",default="digests/crossborder_safety_latest.json")
    p.add_argument("--dividends",default="digests/overseas_dividend_evidence_latest.json")
    p.add_argument("--out",default="digests/crossborder_source_gap_latest.json")
    p.add_argument("--slovakia",default="digests/slovakia_official_accounts_latest.json")
    p.add_argument("--czech",default="digests/czech_factory_official_identity_latest.json")
    p.add_argument("--slovak-pdf",default="digests/slovak_ifrs_primary_pages_latest.json")
    p.add_argument("--part573",default="digests/nhtsa_part573_primary_latest.json")
    a=p.parse_args()
    src=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    try:
        government=src(a.slovakia)
    except (OSError,ValueError):
        government=None
    try:
        czech_identity=src(a.czech)
    except (OSError,ValueError):
        czech_identity=None
    try:
        pdf_note_index=src(a.slovak_pdf)
    except (OSError,ValueError):
        pdf_note_index=None
    try:
        manufacturer_reports=src(a.part573)
    except (OSError,ValueError):
        manufacturer_reports=None
    result=build(src(a.nhtsa),src(a.dividends),slovakia=government,
                 czech=czech_identity,slovak_pdf=pdf_note_index,
                 nhtsa_part573=manufacturer_reports)
    if result["sourceHealth"]["nhtsaOfficial"]!="checked":
        raise SystemExit("NHTSA source incomplete; preserve last good dossier")
    if result["sourceHealth"]["dartOfficialDividendNotes"]=="no_official_receipt_checked":
        raise SystemExit("DART source unverified; preserve last good dossier")
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_suffix(".json.tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(dest)
    print("Crossborder source gaps",result["dossierCount"],
          "US recalls",result["usSafetyDossiers"],
          "issuer named dividend evidence",result["issuerExactDividendDossiers"],
          "confirmed scoops 0")
if __name__=="__main__":main()
