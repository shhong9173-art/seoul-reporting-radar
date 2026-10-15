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

from dart_foreign_dividend_watch import exact_dividend_income_recognition

KST=timezone(timedelta(hours=9))
US_RECALL=re.compile(r"^\d{2}V\d{3,6}$")
DART_RECEIPT=re.compile(r"^20\d{12}$")
MAX_AGE_DAYS=45
DOMESTIC_RECALL_URL="https://www.car.go.kr/ri/stat/list.do"

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


def build(safety,dividends,*,now=None,slovakia=None,czech=None):
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
        if y:dossiers.append(y)
    for x in dividends["leads"][:100]:
        generated=recognized_dividend_dossiers(x)
        for d in generated:
            # Only the precisely named Slovak manufacturing entity can be
            # linked to the official registry. Czech entities are UNCONNECTED.
            if (d["companyGroup"]=="기아" and
                "kiaslovakia" in "".join(
                   str(d["officialFact"]["recognizedFromEntity"]).lower().split())):
                attach_slovak_registry(d,slovakia)
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
    result=build(src(a.nhtsa),src(a.dividends),slovakia=government,
                 czech=czech_identity)
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
