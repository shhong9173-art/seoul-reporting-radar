import sys
import unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_reporting_triage as t

NOW=datetime(2026,10,13,14,22,tzinfo=timezone(timedelta(hours=9)))
A="1020260145290";B="1020260145560";C="1020260143786";D="1020260147965"
def fixtures():
    def lead(pub,rank,media=True,cautions=None):
        return {"publicationNumber":pub,"title":"검증 대상 "+pub,
                "publicationDate":"20261012","coveredCompanies":["LS전선"],
                "topic":"전력망·전력기기",
                "evidencePriorityScore":rank,"mediaReview":{"checked":media},
                "cautionFlags":cautions or [],"retrospectiveKnownCase":False}
    desk={"status":"research_priorities_only",
          "generatedAt":"2026-10-13T14:05:00+09:00",
          "officialSourceGeneratedAt":"2026-10-13T14:00:00+09:00",
          "storySourceGeneratedAt":"2026-10-13T14:03:00+09:00",
          "reviewQueue":[lead(A,90),lead(B,87),lead(C,93,False),lead(D,88,True,["known_case"])]}
    cross={"generatedAt":"2026-10-13T14:10:00+09:00",
           "deskSourceGeneratedAt":desk["generatedAt"],
           "reviews":[{"publicationNumber":x["publicationNumber"],
                       "independentDartTechnicalOverlap":[],
                       "sameIssuerBackgroundSources":[]}
                      for x in desk["reviewQueue"]]}
    editorial={"reviews":[]}
    checks={"checks":[]}
    quality={"officialSourceGeneratedAt":desk["officialSourceGeneratedAt"],
             "storySourceGeneratedAt":desk["storySourceGeneratedAt"],"humanReviewEvents":0}
    return [desk,cross,editorial,checks,quality]

def check(pub,kind,result="verified_public",url="https://example.com/evidence"):
    return {"publicationNumber":pub,"checkType":kind,"result":result,"evidenceUrl":url}

class ReportingTriageTests(unittest.TestCase):
    def test_no_human_decisions_keeps_metrics_null_and_unsearched_out(self):
        args=fixtures()
        r=t.build(*args,now=NOW)
        self.assertEqual(r["totalCandidates"],4)
        self.assertEqual(r["finalHumanSample"],0)
        self.assertIsNone(r["observedEditorialHitRate"])
        self.assertIsNone(r["observedFalsePositiveRate"])
        self.assertEqual([x["publicationNumber"] for x in r["shortlist"]],[A,B])
        self.assertEqual(r["holdCandidates"],1)
        self.assertEqual(r["unsearchedMediaCandidates"],1)
        self.assertEqual(r["approvedArticles"],0)

    def test_worth_reporting_and_public_documents_raise_process_priority(self):
        a=fixtures()
        a[2]["reviews"]=[{"publicationNumber":B,"decision":"worth_reporting"}]
        a[3]["checks"]=[check(B,"company_response"),check(B,"actual_application")]
        r=t.build(*a,now=NOW)
        self.assertEqual(r["shortlist"][0]["publicationNumber"],B)
        self.assertEqual(r["shortlist"][0]["stage"],"reporter_follow_up")
        self.assertEqual(r["shortlist"][0]["publicCheckCount"],2)
        self.assertEqual(r["finalHumanSample"],1)
        self.assertEqual(r["observedEditorialHitRate"],1.0)
        self.assertFalse(r["shortlist"][0]["companyReplyIndependentVerification"])
        self.assertFalse(r["shortlist"][0]["approvedForPublication"])
        self.assertFalse(r["editorialMetricsMatched"])  # old quality label snapshot

    def test_negative_and_published_are_suppressed_even_high_priority(self):
        a=fixtures()
        a[2]["reviews"]=[{"publicationNumber":A,"decision":"already_reported"},
                         {"publicationNumber":B,"decision":"published"}]
        r=t.build(*a,now=NOW)
        self.assertFalse(r["shortlist"])
        self.assertEqual(r["finalHumanSample"],2)
        self.assertEqual(r["observedFalsePositiveRate"],0.5)
        self.assertTrue(all(x["stage"]=="hold_for_review" for x in r["reviewQueue"] if
                            x["publicationNumber"] in (A,B)))

    def test_latest_human_outcome_supersedes_previous(self):
        a=fixtures()
        a[2]["reviews"]=[{"publicationNumber":B,"decision":"already_reported"},
                         {"publicationNumber":B,"decision":"worth_reporting"}]
        r=t.build(*a,now=NOW)
        self.assertEqual(r["finalHumanSample"],1)
        self.assertEqual(r["observedEditorialHitRate"],1.0)
        self.assertIn(B,[x["publicationNumber"] for x in r["shortlist"]])

    def test_incomplete_and_fake_https_checks_not_rewarded(self):
        a=fixtures()
        a[3]["checks"]=[check(B,"company_response","verified_public","http://example.com"),
                        check(B,"actual_application","needs_check",""),
                        check(B,"industry_impact","verified_public","")]
        r=t.build(*a,now=NOW)
        row=next(z for z in r["reviewQueue"] if z["publicationNumber"]==B)
        self.assertEqual(row["publicCheckCount"],0)
        self.assertIn("company_response",row["missingChecks"])

    def test_contradicted_public_impact_blocks_promotions(self):
        a=fixtures()
        a[2]["reviews"]=[{"publicationNumber":B,"decision":"worth_reporting"}]
        a[3]["checks"]=[check(B,"actual_application","contradicted_public")]
        r=t.build(*a,now=NOW)
        row=next(z for z in r["reviewQueue"] if z["publicationNumber"]==B)
        self.assertEqual(row["stage"],"hold_for_review")
        self.assertTrue(row["blockingReasons"])
        self.assertNotIn(B,[x["publicationNumber"] for x in r["shortlist"]])

    def test_all_five_checks_requires_human_editor_and_never_autopublishes(self):
        a=fixtures()
        a[3]["checks"]=[check(B,key) for key in t.CHECK_KINDS]
        r=t.build(*a,now=NOW)
        row=next(z for z in r["reviewQueue"] if z["publicationNumber"]==B)
        self.assertEqual(row["stage"],"source_review_company_call")
        self.assertFalse(row["approvedForPublication"])
        a[2]["reviews"]=[{"publicationNumber":B,"decision":"worth_reporting"}]
        r=t.build(*a,now=NOW)
        row=r["shortlist"][0]
        self.assertEqual(row["stage"],"reporter_editorial_review")
        self.assertEqual(row["publicCheckCount"],5)
        self.assertFalse(row["approvedForPublication"])
        self.assertFalse(row["exclusiveProven"])

    def test_cross_patent_number_gap_or_stale_digest_fails(self):
        a=fixtures()
        a[1]["deskSourceGeneratedAt"]="2026-10-12T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"mismatched"):t.build(*a)
        a=fixtures()
        a[1]["reviews"].pop()
        with self.assertRaisesRegex(ValueError,"Missing cross-check record"):t.build(*a)

    def test_stale_quality_measures_from_ledger_without_inventing_quality(self):
        a=fixtures()
        a[2]["reviews"]=[{"publicationNumber":B,"decision":"needs_reporting"}]
        r=t.build(*a,now=NOW)
        self.assertIsNone(r["observedEditorialHitRate"])
        self.assertEqual(r["finalHumanSample"],0)
        self.assertFalse(r["editorialMetricsMatched"])
        a[4]["humanReviewEvents"]=1
        self.assertTrue(t.build(*a,now=NOW)["editorialMetricsMatched"])

    def test_unreviewed_old_label_not_counted_in_current_cohort(self):
        a=fixtures()
        a[2]["reviews"]=[{"publicationNumber":"1020260999999","decision":"worth_reporting"}]
        r=t.build(*a,now=NOW)
        self.assertEqual(r["finalHumanSample"],0)
        self.assertIsNone(r["observedEditorialHitRate"])

    def test_dart_technical_overlap_is_not_a_patent_business_link_bonus(self):
        a=fixtures()
        zero=t.build(*a,now=NOW)
        r0=next(x for x in zero["reviewQueue"] if x["publicationNumber"]==A)
        a[1]["reviews"][0]["independentDartTechnicalOverlap"]=[{"kind":"keyword_only"}]
        yes=t.build(*a,now=NOW)
        r1=next(x for x in yes["reviewQueue"] if x["publicationNumber"]==A)
        self.assertEqual(r1["evidencePriorityScore"],r0["evidencePriorityScore"])
        self.assertFalse(r1["patentBusinessIdentityProven"])

    def test_ntis_partial_coverage_does_not_verify_exclusive(self):
        a=fixtures()
        ntis={A:{"status":"partially_inspected_no_official_pair_observed",
                 "frozenKiprisApplicationAvailable":True,
                 "keywordRelatedProjectCount":5,
                 "officialNumberPairsForHumanReview":0,
                 "uninspectedRelatedProjectCount":1,
                 "sourceStatus":"bounded_ntis_rpatent_reverse_not_a_business_link",
                 "projectParticipationVerified":False,
                 "businessApplicationVerified":False,"exclusiveProven":False}}
        base=t.build(*a,now=NOW)
        fresh=t.build(*a,now=NOW,ntis_evidence=ntis)
        original=next(x for x in base["reviewQueue"] if x["publicationNumber"]==A)
        row=next(x for x in fresh["reviewQueue"] if x["publicationNumber"]==A)
        self.assertEqual(row["evidencePriorityScore"],original["evidencePriorityScore"])
        self.assertEqual(row["ntisResearchEvidence"]["uninspectedRelatedProjectCount"],1)
        self.assertFalse(row["exclusiveProven"])
        self.assertIsNone(next(x for x in fresh["reviewQueue"]
            if x["publicationNumber"]==B)["ntisResearchEvidence"]["officialNumberPairsForHumanReview"])

if __name__=="__main__":
    unittest.main()
