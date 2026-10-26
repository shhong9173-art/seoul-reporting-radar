"""Prior official filing candidate comparison stays strictly unlinked."""
import copy
import json
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dart_correction_history as m
from dart_lineage import source_link

NOW=datetime(2026,10,15,17,35,tzinfo=timezone(timedelta(hours=9)))
NEW="20260930800924"
OLD="20260226801263"
COMPANY="효성중공업"

def current_row():
    return {
        "receiptNo":NEW,"published":NEW[:8],"company":COMPANY,"corpCode":"00000001",
        "report":"[기재정정]단일판매ㆍ공급계약체결","category":"공급계약",
        "isCorrection":True,"sourceUrl":source_link(NEW),
        "originalReceiptNo":None,"status":"original_not_verified",
        "issuerCorrectionTable":{
          "status":"issuer_table_material_changes_for_review",
          "sourceUrl":source_link(NEW),
          "independentOriginalDocumentCompared":False,
          "changes":[{
            "fieldLabel":"2. 계약내역 - 계약금액(원)",
            "before":"372,324,339,860","after":"383,338,819,710",
            "category":"amount","basis":"issuer_reported_amendment_table_only",
            "amendedSourceUrl":source_link(NEW),
            "originalReceiptIndependentlyVerified":False,
            "commercialEffectVerified":False,"sameEventPriorCoverageVerified":False
          }]
        },
        "unverifiedSameDateCandidates":[{"receiptNo":OLD,"date":OLD[:8],
          "url":source_link(OLD),"report":"[기재정정]단일판매ㆍ공급계약체결",
          "status":m.TRUSTED_CANDIDATE_STATUS}]
    }

def review_fixture():
    return {"generatedAt":"2026-10-15T17:24:55+09:00",
      "dartSourceGeneratedAt":"2026-10-15T17:24:39+09:00",
      "confirmedScoops":0,"approvedArticles":0,
      "items":[{"receiptNo":NEW,"pressSearchCompleted":True,
        "pressSearchQueries":[{"status":"hits","articles":[
            {"title":"효성중공업 이달 공급계약 관련",
             "url":"https://news.google.com/rss/articles/officialindex",
             "publishedAt":"2026-09-01T18:00:00+09:00"},
            {"title":"효성중공업 공시 10월 이후",
             "url":"https://news.google.com/rss/articles/late",
             "publishedAt":"2026-10-01T18:00:00+09:00"}
        ]}]}]}

def prior_doc():
    return ["""
    <TABLE><TR><TD>정정항목</TD><TD>정정 전</TD><TD>정정 후</TD></TR>
    <TR><TD>2. 계약내역 - 계약금액(원)</TD>
     <TD>300,000,000,000</TD><TD>372,324,339,860</TD></TR></TABLE>
    """]

def source_pair():
    return (
      {"generatedAt":"2026-10-15T17:24:39+09:00",
       "items":[current_row()]},
      review_fixture()
    )

class ContractHistory(unittest.TestCase):
    def test_prior_corrected_filing_text_matches_but_linkage_never_proven(self):
        l,n=source_pair()
        calls=[]
        def docs(key,receipt):
            calls.append(receipt)
            return prior_doc()
        result=m.build(l,n,now=NOW,key="TEST",fetch_documents=docs)
        self.assertEqual(calls,[OLD])
        self.assertEqual(result["historicalDocumentsRetrieved"],1)
        self.assertEqual(result["verifiedSameContractHistory"],0)
        self.assertEqual(result["confirmedScoops"],0)
        item=result["items"][0]
        prev=item["priorOfficialCandidateDocuments"][0]
        self.assertEqual(prev["relationshipStatus"],"UNLINKED_same_company_category_reference_date")
        self.assertEqual(prev["matchingTextRows"],1)
        self.assertFalse(prev["sameContractVerified"])
        self.assertFalse(prev["unlinkedComparisons"][0]["sameContractVerified"])
        self.assertFalse(item["revisionFirstReportedAfterPreviousCoverageVerified"])
        self.assertEqual(len(item["pressEvidence"]["olderIndexedArticles"]),1)
        self.assertFalse(item["pressEvidence"]["coverageOfSameRevisionVerified"])

    def test_prior_issuer_revision_three_stage_text_is_not_a_contract_link(self):
        row=current_row()
        prior=m.candidate_issuer_proof(row,row["unverifiedSameDateCandidates"][0],prior_doc())
        self.assertEqual(prior["matchingTextRows"],1)
        self.assertEqual(prior["priorIssuerDeclaredRevisions"][0]["before"],
                         "300,000,000,000")
        self.assertEqual(prior["priorIssuerDeclaredRevisions"][0]["after"],
                         "372,324,339,860")
        bridge=prior["unlinkedComparisons"][0]
        self.assertEqual(bridge["priorCandidateSaidBefore"],"300,000,000,000")
        self.assertEqual(bridge["priorCandidatePublishedValue"],"372,324,339,860")
        self.assertEqual(bridge["currentIssuerSaidBefore"],"372,324,339,860")
        self.assertEqual(bridge["currentIssuerSaidAfter"],"383,338,819,710")
        self.assertFalse(bridge["sameContractVerified"])
        self.assertFalse(prior["currentAmendmentLinkedToThisOrigin"])

    def test_prior_candidate_explicit_origin_is_only_a_hint_until_issuer_list_verification(self):
        row=current_row()
        doc=prior_doc()[0]+(
            "<p>원공시 접수번호: 20250102800011</p>")
        candidate=m.candidate_issuer_proof(row,row["unverifiedSameDateCandidates"][0],[doc])
        self.assertEqual(candidate["priorCandidateExplicitOriginReceipt"],
                         "20250102800011")
        self.assertEqual(candidate["priorCandidateExplicitOriginReferenceStatus"],
                         "prior_candidate_mentions_earlier_receipt_not_current_linkage")
        self.assertFalse(candidate["priorCandidateExplicitOriginVerifiedInIssuerList"])
        self.assertFalse(candidate["currentAmendmentLinkedToThisOrigin"])
        self.assertFalse(candidate["unlinkedComparisons"][0]["sameContractVerified"])

    def test_unlabeled_old_receipt_is_not_promoted_to_origin(self):
        row=current_row()
        doc=prior_doc()[0]+("<p>선행 접수: 20250102800011</p>")
        candidate=m.candidate_issuer_proof(row,row["unverifiedSameDateCandidates"][0],[doc])
        self.assertIsNone(candidate["priorCandidateExplicitOriginReceipt"])
        self.assertFalse(candidate["currentAmendmentLinkedToThisOrigin"])

    def test_previous_initial_notice_terms_are_only_candidates(self):
        row=current_row()
        row["unverifiedSameDateCandidates"][0]["report"]="단일판매ㆍ공급계약체결"
        doc="<TABLE><TR><TD>계약금액(원)</TD><TD>372,324,339,860</TD></TR></TABLE>"
        p=m.candidate_issuer_proof(row,row["unverifiedSameDateCandidates"][0],[doc])
        self.assertEqual(p["priorCandidateKind"],"prior_filing_official_terms")
        self.assertEqual(p["matchingTextRows"],1)
        self.assertFalse(p["unlinkedComparisons"][0]["sameContractVerified"])

    def test_current_before_differs_from_past_candidate_after_no_join(self):
        row=current_row()
        prior=prior_doc()[0].replace("372,324,339,860","111,111,111,111")
        p=m.candidate_issuer_proof(row,row["unverifiedSameDateCandidates"][0],[prior])
        self.assertEqual(p["conflictingTextRows"],1)
        self.assertEqual(p["matchingTextRows"],0)

    def test_fake_url_wrong_day_future_date_wrong_category_all_rejected(self):
        row=current_row()
        for key,value in (
            ("url","https://example.com/?rcpNo="+OLD),
            ("date","20260227"),
            ("date","20261001"),
            ("report","생산중단"),
            ("status","original_verified")):
            prior=copy.deepcopy(row["unverifiedSameDateCandidates"][0])
            prior[key]=value
            self.assertFalse(m.trustworthy_candidate(row,prior),
                             "unexpected accepted candidate "+key)

    def test_no_key_is_explicitly_not_checked_and_never_zero_prior(self):
        l,n=source_pair()
        result=m.build(l,n,now=NOW,key="",fetch_documents=lambda *a: self.fail("network"))
        self.assertEqual(result["totalHistoricalCandidateDocs"],1)
        self.assertEqual(result["historicalDocumentsRetrieved"],0)
        self.assertEqual(result["requestsAttempted"],0)
        self.assertEqual(result["items"][0]["priorOfficialCandidateDocuments"][0]["status"],
                         "not_checked_without_DART_key")

    def test_index_failure_unknown_and_not_zero_prior_reports(self):
        l,n=source_pair()
        n["items"][0]["pressSearchCompleted"]=False
        n["items"][0]["pressSearchQueries"]=[]
        item=m.build(l,n,now=NOW,key="").get("items")[0]
        self.assertEqual(item["pressEvidence"]["status"],"partial_or_unsearched_index")
        self.assertFalse(item["pressEvidence"]["articleFulltextRead"])
        self.assertFalse(item["revisionFirstReportedAfterPreviousCoverageVerified"])

    def test_dated_candidate_duplicate_not_counted_twice_and_request_bound(self):
        l,n=source_pair()
        row=l["items"][0]
        row["unverifiedSameDateCandidates"].append(copy.deepcopy(row["unverifiedSameDateCandidates"][0]))
        result=m.build(l,n,now=NOW,key="TEST",fetch_documents=lambda *a:prior_doc())
        self.assertEqual(result["totalHistoricalCandidateDocs"],1)
        self.assertLessEqual(result["requestsAttempted"],m.RUN_DOCUMENT_MAX)

    def test_source_stamp_drift_rejected(self):
        l,n=source_pair()
        n["dartSourceGeneratedAt"]="2026-10-14T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"source_provenance_mismatch"):
            m.build(l,n,now=NOW)

    def test_real_committed_sources_without_key_do_not_claim_completed_research(self):
        # The committed ledger is live operating data refreshed by the same
        # workflow that runs this test. Pinning its daily counts made the job
        # fail before it could refresh, freezing the ledger (2026-10-22~).
        # Derive expectations from the ledger and assert the invariants.
        l=json.loads((ROOT/"digests/recent_contracts_latest.json").read_text(encoding="utf-8"))
        n=json.loads((ROOT/"digests/dart_contract_followup_latest.json").read_text(encoding="utf-8"))
        result=m.build(l,n,now=NOW,key="",fetch_documents=lambda *a: self.fail("offline"))
        corrections=[x for x in l["items"] if isinstance(x,dict) and x.get("isCorrection")]
        self.assertEqual(result["corrections"],len(corrections))
        self.assertEqual(len(result["items"]),len(corrections))
        self.assertEqual({x["receiptNo"] for x in result["items"]},
                         {x["receiptNo"] for x in corrections})
        self.assertLessEqual(result["totalHistoricalCandidateDocs"],
                             len(corrections)*m.CANDIDATE_MAX)
        self.assertEqual(result["historicalDocumentsRetrieved"],0)
        self.assertEqual(result["requestsAttempted"],0)
        self.assertEqual(result["verifiedSameContractHistory"],0)
        self.assertEqual(result["confirmedScoops"],0)
        self.assertEqual(result["approvedArticles"],0)
        for item in result["items"]:
            self.assertFalse(item["linkageVerified"])
            self.assertFalse(item["confirmedExclusive"])
            self.assertFalse(item["approvedForPitch"])
            self.assertEqual(item["retrievalsAttempted"],0)
            for doc in item["priorOfficialCandidateDocuments"]:
                self.assertEqual(doc["status"],"not_checked_without_DART_key")
                self.assertFalse(doc["priorDocumentRetrieved"])
                self.assertFalse(doc["sameContractVerified"])

    def test_live_count_change_does_not_break_invariants(self):
        # Regression for the frozen-ledger failure: dropping a correction from
        # the rolling window must change counts, not fail the safety checks.
        l,n=source_pair()
        extra=current_row()
        extra["receiptNo"]="20260929800111"
        extra["published"]=extra["receiptNo"][:8]
        extra["sourceUrl"]=source_link(extra["receiptNo"])
        extra["unverifiedSameDateCandidates"]=[]
        l["items"].append(extra)
        n["items"].append(dict(n["items"][0],receiptNo=extra["receiptNo"]))
        both=m.build(l,n,now=NOW,key="",fetch_documents=lambda *a: self.fail("offline"))
        l["items"].pop(); n["items"].pop()
        one=m.build(l,n,now=NOW,key="",fetch_documents=lambda *a: self.fail("offline"))
        self.assertEqual((both["corrections"],one["corrections"]),(2,1))
        for r in (both,one):
            self.assertEqual(r["historicalDocumentsRetrieved"],0)
            self.assertEqual(r["confirmedScoops"],0)

if __name__=="__main__":unittest.main()
