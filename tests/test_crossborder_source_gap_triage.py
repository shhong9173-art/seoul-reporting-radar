"""Real-user scoop archetypes: foreign recall/domestic comparison and recognized dividends."""
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import crossborder_source_gap_triage as t

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,16,11,0,tzinfo=KST)

def safety_record():
    return {
      "id":"26V664000","officialDate":"20261008",
      "sourceUrl":"https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber=26V664000",
      "makes":["GENESIS","HYUNDAI"],
      "models":[{"model":"G80","year":"2017"},{"model":"GENESIS","year":"2015"}],
      "defect":"The front power seat motors may overheat; fire while parked or driving.",
      "flags":["fire_or_thermal_word_in_us_summary","us_park_outside_advice"],
      "usRecallExists":True,"exclusiveConfirmed":False,
      "koreanRecallChecked":False,"koreanIncidentVerified":False
    }

def note():
    return {
      "receiptNo":"20260916000427","company":"기아",
      "filingUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260916000427",
      "evidenceTier":"low_confidence_proximity",
      "tableExcerpt":("당반기 중 투자손익. (단위: 백만원) 제83기 반기 "
         "배당금수익 1,747,732, 전반기 배당금수익 146,488. "
         "당반기 배당금수익은 Kia Slovakia s.r.o.(KaSK)로부터 인식한 "
         "1,610,458백만원, 현대모비스로부터 인식한 82,135백만원 등으로 구성됩니다."),
      "cashReceiptVerified":False,"scoopConfirmed":False
    }

def sources():
    return (
      {"status":"official_us_recalls_to_review","confirmedScoops":0,
       "generatedAt":"2026-10-16T03:28:49+09:00",
       "archiveLatestReceived":"2026-10-15","campaignCount":1,"leads":[safety_record()]},
      {"status":"evidence_excerpts_not_verified_dividend_receipts",
       "confirmedScoops":0,"generatedAt":"2026-10-16T03:28:52+09:00",
       "foreignRegistryStatus":"not_connected",
       "sourceChecks":[{"company":"기아","period":"current","status":"checked"}],
       "leads":[note()]}
    )

class CrossBorderDossiers(unittest.TestCase):
    def test_genesis_nhtsa_only_us_recall_no_korea_absence(self):
        n,d=sources()
        data=t.build(n,d,now=NOW)
        safety=next(x for x in data["items"] if x["type"]=="overseas_safety_domestic_comparison")
        self.assertEqual(safety["officialFact"]["usCampaign"],"26V664000")
        self.assertEqual(safety["reporterPriority"],"domestic_crosscheck_first")
        self.assertFalse(safety["pitchGate"]["domesticOfficialChecked"])
        self.assertFalse(safety["pitchGate"]["exactComponentMatch"])
        self.assertFalse(safety["pitchGate"]["exclusiveConfirmed"])
        self.assertEqual(safety["sourceAvailability"]["koreanOfficialRecall"],
                         "api_not_connected_requires_authorization")
        self.assertEqual(data["confirmedScoops"],0)
        self.assertFalse(data["domesticRecallAbsenceVerified"])

    def test_korean_recall_center_model_jump_is_not_domestic_matching_evidence(self):
        result=t.build(*sources(),now=NOW)
        genesis=next(x for x in result["items"] if x["id"]=="usrecall:26V664000")
        self.assertEqual([q["searchTerm"] for q in genesis["koreanModelSearchLinks"]],
                         ["G80","제네시스"])
        for query in genesis["koreanModelSearchLinks"]:
            self.assertIn("https://www.car.go.kr/ri/stat/list.do?",query["officialSearchUrl"])
            self.assertFalse(query["searchResultRead"])
            self.assertFalse(query["matchingRecallVerified"])
            self.assertFalse(query["absenceOfRecallVerified"])
            self.assertFalse(query["koreanIdenticalComponentVerified"])
        self.assertFalse(genesis["pitchGate"]["domesticOfficialChecked"])
        self.assertFalse(genesis["pitchGate"]["exclusiveConfirmed"])

    def test_unknown_us_model_generates_no_invented_korean_variant(self):
        self.assertEqual(t.manual_korean_model_search([{"model":"UNKNOWN X"}]),[])

    def test_kia_recognized_issuer_dividend_not_cash_and_not_a_new_20261016_event(self):
        n,d=sources()
        result=t.build(n,d,now=NOW)
        row=next(x for x in result["items"] if x["type"]=="foreign_subsidiary_dividend_accounting")
        self.assertEqual(row["officialFact"]["recognizedFromEntity"],
                         "Kia Slovakia s.r.o.(KaSK)")
        self.assertEqual(row["officialFact"]["recognizedAmountInMillionKrw"],1610458)
        self.assertEqual(row["officialFact"]["recognizedDividendIncomeText"],"1,610,458백만원")
        self.assertEqual(row["officialPublicationDate"],"2026-09-16")
        self.assertEqual(row["reportingWindowStatus"],"historical_public_filing_to_investigate")
        self.assertFalse(row["pitchGate"]["cashReceivedByParentVerified"])
        self.assertFalse(row["pitchGate"]["foreignCompanyLegalAccountsVerified"])
        self.assertFalse(row["pitchGate"]["sameAnglePriorPressChecked"])
        self.assertFalse(result["foreignParentCashTransferVerified"])

    def test_real_official_slovak_metadata_enriches_accounting_case_without_cash_claim(self):
        from slovakia_official_accounts import registry_evidence
        from test_slovakia_official_accounts import api_data
        registry=registry_evidence(api_data,now=NOW)
        n,d=sources()
        result=t.build(n,d,now=NOW,slovakia=registry)
        row=next(x for x in result["items"]
                 if x["type"]=="foreign_subsidiary_dividend_accounting")
        sk=row["slovakGovernmentAccounts"]
        self.assertTrue(sk["officialEntityVerified"])
        self.assertEqual(sk["ico"],"35876832")
        self.assertEqual([x["financialYear"] for x in sk["individualAnnualFilings"]],
                         [2025,2024])
        self.assertFalse(sk["companyCashReceivedVerified"])
        self.assertFalse(sk["fundingSourceVerified"])
        self.assertFalse(sk["auditedPdfReviewed"])
        self.assertFalse(row["pitchGate"]["cashReceivedByParentVerified"])
        self.assertEqual(result["sourceHealth"]["foreignSubsidiaryRegistries"],
                         "slovak_issuer_metadata_only")
        self.assertEqual(result["sourceHealth"]["czechSubsidiaryRegistry"],
                         "not_connected_or_ares_identity_unavailable")
        self.assertEqual(result["confirmedScoops"],0)

    def test_failed_slovak_api_is_unknown_not_zero_or_verified(self):
        n,d=sources()
        sk={"status":"official_slovak_registry_identity_and_filing_metadata",
            "ico":"35876832","companyIdentityVerified":False,
            "companyIdentityStatus":"official_source_error_or_exact_identity_unverified",
            "statements":[]}
        result=t.build(n,d,now=NOW,slovakia=sk)
        target=next(x for x in result["items"] if
                    x["type"]=="foreign_subsidiary_dividend_accounting")
        self.assertFalse(target["slovakGovernmentAccounts"]["officialEntityVerified"])
        self.assertFalse(target["slovakGovernmentAccounts"]["dividendPaymentVerified"])
        self.assertFalse(target["pitchGate"]["cashReceivedByParentVerified"])

    def test_wrong_ico_registry_metadata_must_not_attach(self):
        n,d=sources()
        sk={"status":"official_slovak_registry_identity_and_filing_metadata",
            "ico":"35942894","companyIdentityVerified":True,
            "companyIdentityStatus":"exact_registered_name_ico_unique",
            "statements":[]}
        result=t.build(n,d,now=NOW,slovakia=sk)
        target=next(x for x in result["items"] if
                    x["type"]=="foreign_subsidiary_dividend_accounting")
        self.assertFalse(target["slovakGovernmentAccounts"]["officialEntityVerified"])

    def test_czech_manufacturing_identity_not_dividend_or_importer(self):
        from czech_factory_official_identity import verify
        row=verify(lambda:{"ico":"27773035",
            "obchodniJmeno":"Hyundai Motor Manufacturing Czech s.r.o."},now=NOW)
        n,d=sources()
        result=t.build(n,d,now=NOW,czech=row)
        x=result["foreignLegalEntityLinks"]["hyundaiCzechFactory"]
        self.assertTrue(x["identityVerified"])
        self.assertEqual(x["ico"],"27773035")
        self.assertFalse(x["auditedAccountsContentsReviewed"])
        self.assertFalse(x["dividendsPaidVerified"])
        self.assertEqual(result["sourceHealth"]["czechSubsidiaryRegistry"],
                         "manufacturer_official_legal_identity_only")
        self.assertFalse(result["foreignParentCashTransferVerified"])

    def test_hash_verified_slovak_ifrs_page_clues_attached_but_no_dividend_amount_claim(self):
        import hashlib
        n,d=sources()
        from slovakia_official_accounts import registry_evidence
        from test_slovakia_official_accounts import api_data
        government=registry_evidence(api_data,now=NOW)
        checksum=hashlib.sha256(b"%PDF-1.4 official mock").hexdigest()
        evidence={
          "status":"official_slovak_ifrs_pdf_review_clues_not_validated_dividend_transfer",
          "ico":"35876832","sourceRegistryGeneratedAt":government["generatedAt"],
          "financialFiguresInterpreted":False,
          "dividendDistributionResolutionVerified":False,
          "koreanParentCashReceiptVerified":False,
          "dividendPaymentToParentVerified":False,
          "exclusiveConfirmed":False,
          "reports":[{
             "year":2025,"statementId":6995571,"reportId":10298519,
             "status":"official_pdf_text_passages_for_manual_review",
             "pdfReadAndOfficialHashVerified":True,
             "sha256":checksum,
             "attachmentUrl":"https://www.registeruz.sk/cruz-public/domain/financialreport/attachment/12345678",
             "pageClues":[{
                "page":32,"sourceTextExcerpt":"Note 19: Dividends were discussed",
                "containsFinancialAmountValidated":False,
                "cashPaidOrRetainedProfitValidated":False
             }]
          }]
        }
        # Synthetic registry includes distinct report IDs; metadata parent
        # matching is re-checked at the source fetch stage.
        got=t.build(n,d,now=NOW,slovakia=government,slovak_pdf=evidence)
        target=next(x for x in got["items"] if
                    x["type"]=="foreign_subsidiary_dividend_accounting")
        p=target["slovakPdfPrimaryReview"]
        self.assertEqual(p["governmentHashVerifiedReports"],1)
        self.assertEqual(p["passages"][0]["page"],32)
        self.assertFalse(p["amountsIndependentlyAudited"])
        self.assertFalse(p["parentCashReceiptVerified"])
        self.assertFalse(target["pitchGate"]["cashReceivedByParentVerified"])
        evidence["sourceRegistryGeneratedAt"]="2025-01-01T00:00:00+09:00"
        rejected=t.build(n,d,now=NOW,slovakia=government,slovak_pdf=evidence)
        self.assertEqual(next(x for x in rejected["items"] if x["type"]==
          "foreign_subsidiary_dividend_accounting")["slovakPdfPrimaryReview"]["governmentHashVerifiedReports"],0)

    def test_wrong_entity_or_total_dividend_is_not_subsidiary_amount(self):
        x=note()
        x["tableExcerpt"]="당반기 배당금수익은 1,747,732백만원입니다. Kia Slovakia 현지공장 매출 32억원"
        self.assertEqual(t.recognized_dividend_dossiers(x),[])

    def test_unverified_source_failure_cannot_be_zero(self):
        n,d=sources()
        n["status"]="provider_error"
        with self.assertRaisesRegex(ValueError,"source_invalid"):
            t.build(n,d,now=NOW)
        n,d=sources()
        d["confirmedScoops"]=1
        with self.assertRaisesRegex(ValueError,"source_invalid"):
            t.build(n,d,now=NOW)

    def test_wrong_recall_url_and_korean_recall_claim_both_rejected(self):
        x=safety_record()
        x["sourceUrl"]="https://not-nhtsa.example/recall"
        self.assertIsNone(t.safety_dossier(x,NOW))
        x=safety_record()
        x["koreanRecallChecked"]=True
        self.assertIsNone(t.safety_dossier(x,NOW))

    def test_input_from_future_and_stale_note_state_visible(self):
        n,d=sources()
        n["generatedAt"]="2026-10-18T13:01:00+09:00"
        with self.assertRaisesRegex(ValueError,"unverified_source_creation_time"):
            t.build(n,d,now=NOW)
        n,d=sources()
        n["generatedAt"]="2026-10-13T03:00:00+09:00"
        result=t.build(n,d,now=NOW)
        self.assertTrue(result["sourceStale48h"])
        self.assertEqual(result["confirmedScoops"],0)

    def test_real_committed_official_datasets_if_both_still_available(self):
        import json
        a=ROOT/"digests/crossborder_safety_latest.json"
        b=ROOT/"digests/overseas_dividend_evidence_latest.json"
        if not (a.exists() and b.exists()):
            self.skipTest("Official snapshots not committed")
        n=json.loads(a.read_text(encoding="utf-8"))
        d=json.loads(b.read_text(encoding="utf-8"))
        # Use exact first run time rather than a frozen NOW to avoid future-data false failures.
        dynamic=max(NOW,datetime.fromisoformat(n["generatedAt"])+timedelta(minutes=1),
                    datetime.fromisoformat(d["generatedAt"])+timedelta(minutes=1))
        out=t.build(n,d,now=dynamic)
        self.assertFalse(out["domesticRecallAbsenceVerified"])
        self.assertFalse(out["foreignParentCashTransferVerified"])
        self.assertEqual(out["confirmedScoops"],0)
        self.assertEqual(out["approvedArticles"],0)
        for x in out["items"]:
            self.assertTrue(x["publicationAloneIsNotScoop"])
            self.assertFalse(x["pitchGate"]["exclusiveConfirmed"])

if __name__=="__main__":unittest.main()
