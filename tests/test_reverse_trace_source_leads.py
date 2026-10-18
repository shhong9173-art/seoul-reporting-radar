"""Offline and checked-in replay of real, *not yet chronologically verified*, originals."""
import copy
import json
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.reverse_trace_source_leads import (
    STATUS,attach_primary_original_leads,official_candidate_url,verify_curated_lead
)
from scripts.exclusive_reverse_trace import build

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,19,0,10,tzinfo=KST)
LEAD_A="cb9608ce6570bffb5c7329fd"
LEAD_B="8eca1266723f4d77a94a42f1"


def sample_trace():
    articles=[
        {"id":LEAD_A,"title":"[단독]삼성SDI, 솔리드파워·BMW와 '전고체 배터리' 협력 - 더트래커",
         "published":"2025-10-31T16:00:00+09:00","sourceName":"더트래커",
         "url":"https://news.google.com/rss/articles/a","companies":["삼성SDI"],
         "global":False},
        {"id":LEAD_B,"title":"[단독] 삼성SDI, BMW·솔리드파워와 전고체배터리 동맹 구축 - 더구루",
         "published":"2025-10-31T16:00:00+09:00","sourceName":"더구루",
         "url":"https://news.google.com/rss/articles/b","companies":["삼성SDI"],
         "global":False},
    ]
    press={
        "status":"observed_domestic_press_index_not_complete_coverage",
        "generatedAt":"2026-10-19T00:00:00+09:00",
        "itemCount":len(articles),"items":articles}
    return build(press,now=NOW)


def source_sheet():
    return json.loads((ROOT/"data/reverse_trace_primary_original_leads.json").read_text(
        encoding="utf-8"))


class SourceLeads(unittest.TestCase):
    def test_two_actual_samsung_press_titles_one_original_no_ypn(self):
        trace=sample_trace()
        sheet=source_sheet()
        result=attach_primary_original_leads(trace,sheet)
        self.assertEqual(result["locatedOriginalCandidateArticleCount"],2)
        self.assertEqual(result["distinctLocatedOfficialOriginalDocuments"],2)
        self.assertEqual(result["locatedSupplementaryForeignOriginalReferences"],2)
        self.assertTrue(result["secOfficialAcceptanceTimestampChecked"])
        self.assertEqual(result["primaryDocumentPublishedBeforeMediaVerifiedCount"],0)
        self.assertEqual(result["pressFulltextMatchedToOfficialOriginalCount"],0)
        self.assertFalse(result["sourcePrioritizationEvidenceSufficient"])
        self.assertEqual(result["Y"]+result["P"]+result["N"],0)
        self.assertEqual(result["humanReviewedYPN"],0)
        self.assertEqual(result["unreviewedU"],2)
        for item in result["items"]:
            proof=item["locatedOfficialOriginalCandidate"]
            self.assertEqual(proof["documentUrl"],
                "https://news.samsungsdi.com/ko/articleView?seq=371")
            self.assertTrue(proof["sameDayDoesNotProveEarlierRelease"])
            self.assertFalse(proof["releasedBeforeStoryVerified"])
            self.assertFalse(proof["documentAndStoryFactsCompared"])
            self.assertFalse(proof["publicationClockVerified"])
            self.assertFalse(proof["automaticYPNDecision"])
            self.assertEqual(item["publicTraceClass"],"U")
            foreign=item["locatedSupportingOfficialOriginals"]
            self.assertEqual(len(foreign),1)
            sec=foreign[0]
            self.assertEqual(sec["sourceType"],"regulatory_filing")
            self.assertEqual(sec["documentDay"],"2025-10-30")
            self.assertEqual(sec["secAcceptedAtOfficialEastern"],
                             "2025-10-30T16:15:52-04:00")
            self.assertTrue(sec["documentCalendarDayEarlierThanIndexedRssDay"])
            self.assertTrue(sec["secAcceptedAtIsNotPressFirstPublishedAt"])
            self.assertFalse(sec["releasedBeforeStoryVerified"])
            self.assertFalse(sec["sourceAndStoryFactsDirectlyMatched"])
            self.assertFalse(sec["automaticYPNDecision"])
            self.assertEqual(item["researchSourcePlatformsSuggested"][0],
                             "회사 공식 공개자료")

    def test_no_guess_for_unlinked_steel_and_policy(self):
        trace=sample_trace()
        trace["items"][0]["kind"]="통상·관세"
        sheet={"status":STATUS,"lastCuratedAt":"2026-10-19T00:00:00+09:00",
               "confirmedScoops":0,"humanYPNFromLeads":0,"items":[]}
        result=attach_primary_original_leads(trace,sheet)
        self.assertEqual(result["locatedOriginalCandidateArticleCount"],0)
        self.assertTrue(result["items"][0]["sourcePlatformSuggestionsOnly"])
        self.assertIn("미국 상무부·ITC 공고",
                      result["items"][0]["researchSourcePlatformsSuggested"])
        self.assertNotIn("locatedOfficialOriginalCandidate",result["items"][0])
        self.assertEqual(result["confirmedScoops"],0)

    def test_domain_exactness_and_attack_links(self):
        valid=source_sheet()["items"][0]
        self.assertTrue(official_candidate_url(valid["officialUrl"]))
        for suffix in (
            "https://news.samsungsdi.com.evil.example/ko/articleView?seq=371",
            "http://news.samsungsdi.com/ko/articleView?seq=371",
            "https://news.samsungsdi.com:443/ko/articleView?seq=371",
            "https://news.samsungsdi.com/ko/articleView?seq=371#new",
            "https://news.samsungsdi.com/ko/articleView?seq=1",
            "https://news.samsungsdi.com/ko/articleView?seq=371&claim=Y",
        ):
            self.assertFalse(official_candidate_url(suffix),suffix)

    def test_forged_publication_time_or_automatic_ypn_cannot_pass(self):
        for key,value in (
            ("humanYPNAssigned",True),
            ("officialPublicationClockVerified",True),
            ("primaryReleasedBeforeStoryVerified",True),
            ("articleFulltextCompared",True),
            ("officialFactOverlapIndependentlyVerified",True),
            ("publisherArticleFirstPublishedClockVerified",True),
            ("officialDocumentDate","2025-02-30"),
            ("sourceType","invented_original"),
        ):
            sheet=source_sheet()
            sheet["items"][0][key]=value
            with self.assertRaises(ValueError,msg=key):
                attach_primary_original_leads(sample_trace(),sheet)

    def test_sec_source_domain_url_and_acceptance_cannot_be_forged(self):
        sheet=source_sheet()
        official=sheet["items"][0]["supportingOfficialOriginals"][0]
        self.assertTrue(official_candidate_url(official["officialUrl"]))
        for invalid in (
            "https://www.sec.gov.attacker.example/Archives/edgar/data/1844862/000110465925104388/0001104659-25-104388-index.html",
            "https://www.sec.gov/Archives/edgar/data/1844862/000110465925104388/0001104659-25-104388-index.html?isExclusive=true",
            "http://www.sec.gov/Archives/edgar/data/1844862/000110465925104388/0001104659-25-104388-index.html",
        ):
            self.assertFalse(official_candidate_url(invalid),invalid)
        for field,value in (
            ("officialAcceptanceAt","2025-10-31T03:00:00+09:00"),
            ("publicFirstAvailabilityTimeVerified",True),
            ("publisherStoryFulltextCompared",True),
            ("releasedBeforeStoryVerified",True),
            ("humanYPNAssigned",True),
            ("officialDocumentDate","2025-10-31"),
            ("sourceType","company_notice"),
        ):
            tampered=source_sheet()
            tampered["items"][0]["supportingOfficialOriginals"][0][field]=value
            with self.assertRaisesRegex(ValueError,"unsafe_curated_official"):
                attach_primary_original_leads(sample_trace(),tampered)

    def test_sec_filing_dated_after_indexed_rss_story_not_linked(self):
        trace=sample_trace()
        for row in trace["items"]:
            row["published"]="2025-10-29T16:00:00+09:00"
        out=attach_primary_original_leads(trace,source_sheet())
        self.assertEqual(out["locatedOriginalCandidateArticleCount"],0)
        self.assertEqual(out["distinctLocatedOfficialOriginalDocuments"],0)
        self.assertEqual(out["primaryDocumentPublishedBeforeMediaVerifiedCount"],0)

    def test_source_release_after_article_date_is_never_linked(self):
        sheet=source_sheet()
        for row in sheet["items"]:
            row["officialDocumentDate"]="2025-11-01"
        result=attach_primary_original_leads(sample_trace(),sheet)
        self.assertEqual(result["locatedOriginalCandidateArticleCount"],0)
        self.assertEqual(result["staleOrUnmatchedCuratedLeadRows"],2)
        self.assertEqual(result["primaryDocumentPublishedBeforeMediaVerifiedCount"],0)

    def test_source_article_id_stale_or_name_mismatch_no_claim(self):
        trace=sample_trace()
        trace["items"][0]["companies"]=["현대차"]
        trace["items"][1]["title"]="[단독] 삼성SDI 외부 소송 기사"
        result=attach_primary_original_leads(trace,source_sheet())
        self.assertEqual(result["locatedOriginalCandidateArticleCount"],0)
        self.assertEqual(result["staleOrUnmatchedCuratedLeadRows"],2)
        self.assertEqual(len(result["staleLinkageCandidateIds"]),2)

    def test_duplicate_or_invalid_curated_sheet_rejected_not_zeroed(self):
        sheet=source_sheet()
        sheet["items"].append(copy.deepcopy(sheet["items"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_official"):
            attach_primary_original_leads(sample_trace(),sheet)
        sheet=source_sheet()
        sheet["status"]="source_unavailable"
        with self.assertRaisesRegex(ValueError,"invalid_official"):
            attach_primary_original_leads(sample_trace(),sheet)

    def test_actual_main_reverse_trace_snapshot_candidate_links(self):
        snapshot=json.loads((ROOT/"digests/reverse_trace_latest.json").read_text(
            encoding="utf-8"))
        result=attach_primary_original_leads(snapshot,source_sheet())
        matched=[x for x in result["items"] if
                 x.get("locatedOfficialOriginalCandidate")]
        # Source index rotates; file may age out later. Any linked article must
        # still meet the strict same-day and publisher-source guards.
        for item in matched:
            self.assertEqual(item["publicTraceClass"],"U")
            self.assertFalse(item["locatedOfficialOriginalCandidate"]
                             ["releasedBeforeStoryVerified"])
        self.assertEqual(result["confirmedScoops"],0)
        self.assertEqual(result["humanReviewedYPN"],snapshot["humanReviewedYPN"])


if __name__=="__main__":
    unittest.main()
