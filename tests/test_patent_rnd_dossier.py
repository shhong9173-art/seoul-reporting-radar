"""Regression checks for cross-source R&D dossiers; all sources synthetic."""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import patent_rnd_dossier as d

NOW = datetime(2026, 10, 13, 18, 52, tzinfo=timezone(timedelta(hours=9)))
PUB = "1020260145290"
OLD = "1020260145560"

def fixture():
    def patent(num, date, title, media=True, risk=None):
        return {"publicationNumber": num, "publicationDate": date,
                "title":title,"sourceAbstractExcerpt":"공식 초록 일부",
                "coveredCompanies":["LS전선"],
                "outsideBeatCoApplicants":["서울대학교산학협력단"],
                "claim1Review":{"verified":True, "claim1Excerpt":"청구항 원문"},
                "olderSameTitle":{"state":"searched_same_title_only"},
                "mediaReview":{"checked":media,"state":risk or "index_no_hits_not_proof"}}
    d0={"status":"research_priorities_only","generatedAt":"2026-10-13T14:30:00+09:00",
        "reviewQueue":[patent(PUB,"20261012","케이블 부착식 부분방전 센서"),
                       patent(OLD,"20260814","상변태 기반 판재 냉각 제어",False)]}
    c={"deskSourceGeneratedAt":d0["generatedAt"],"generatedAt":"2026-10-13T14:31:00+09:00",
       "reviews":[{"publicationNumber":PUB,
                   "independentDartTechnicalOverlap":[{
                       "sourceType":"dart_business_table",
                       "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814003379",
                       "published":"20260814","technicalTermsShared":["부분방전"]}],
                   "sameIssuerBackgroundSources":[]},
                  {"publicationNumber":OLD,"independentDartTechnicalOverlap":[],
                   "sameIssuerBackgroundSources":[]}]}
    t={"deskSourceGeneratedAt":d0["generatedAt"],"crossSourceGeneratedAt":c["generatedAt"],
       "generatedAt":"2026-10-13T14:32:00+09:00",
       "reviewQueue":[{"publicationNumber":PUB,"stage":"source_review_company_call"},
                      {"publicationNumber":OLD,"stage":"media_check_first"}]}
    return d0,c,t


class DossierTests(unittest.TestCase):
    def test_snapshots_have_to_match(self):
        a,b,c=fixture()
        c["crossSourceGeneratedAt"]="2026-10-12"
        with self.assertRaisesRegex(ValueError,"snapshot mismatch"):
            d.build(a,b,c,NOW)

    def test_missing_patent_identity_is_hard_failure(self):
        a,b,c=fixture()
        b["reviews"].pop()
        with self.assertRaisesRegex(ValueError,"identities"):
            d.build(a,b,c,NOW)

    def test_old_dart_is_context_not_new_business_event(self):
        a,b,c=fixture()
        result=d.build(a,b,c,NOW)
        row=result["dossiers"][0]
        self.assertTrue(row["recentPatentWithin3Days"])
        self.assertEqual(row["dartRecentDocuments"],0)
        self.assertFalse(row["dartDocuments"][0]["filedWithin3Days"])
        self.assertEqual(row["dartDocuments"][0]["filingDate"],"2026-08-14")
        self.assertIn("dart_evidence_is_historical_context",row["cautions"])
        self.assertFalse(row["patentToProjectIdentityVerified"])
        self.assertFalse(row["commercialApplicationVerified"])

    def test_unsearched_patent_is_blocked_and_not_counted_as_no_coverage(self):
        x=d.build(*fixture(),now=NOW)
        r=x["dossiers"][1]
        self.assertFalse(r["pressLookupCompleted"])
        self.assertFalse(r["eligibleForResearchQueue"])
        self.assertIn("media_lookup_incomplete",r["cautions"])

    def test_ntis_link_is_valid_query_not_api_award(self):
        report=d.build(*fixture(),now=NOW)
        q=report["dossiers"][0]["ntisResearchQueries"]
        self.assertEqual(len(q),2)
        self.assertIn("부분방전",parse_qs(urlparse(q[0]["url"]).query)["searchWord"][0])
        self.assertIn("LS전선",q[0]["query"])
        self.assertFalse(q[0]["participationConfirmed"])
        self.assertEqual(report["sourceStatus"]["ntisProjectApi"],"not_connected")
        self.assertEqual(report["verifiedPatentProjectMappings"],0)
        self.assertFalse(report["dossiers"][0]["officialResearchProjectAwardConfirmed"])

    def test_broad_generic_patent_generates_no_fake_precise_ntis_query(self):
        a,b,c=fixture()
        a["reviewQueue"][0]["title"]="차량 및 방법"
        r=d.build(a,b,c,NOW)
        self.assertEqual(r["dossiers"][0]["ntisResearchQueries"],[])

    def test_malicious_dart_url_is_dropped(self):
        a,b,c=fixture()
        b["reviews"][0]["independentDartTechnicalOverlap"][0]["url"]=(
            "https://dart.fss.or.kr.evil.test/dsaf001/main.do?rcpNo=20260814003379")
        r=d.build(a,b,c,NOW)
        self.assertEqual(r["dossiers"][0]["dartDocuments"],[])
        self.assertIn("no_dart_related_source_coverage",r["dossiers"][0]["cautions"])

    def test_recent_document_is_not_application_proof(self):
        a,b,c=fixture()
        event=b["reviews"][0]["independentDartTechnicalOverlap"][0]
        event["url"]="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261012000001"
        event["published"]="20261012"
        result=d.build(a,b,c,NOW)
        r=result["dossiers"][0]
        self.assertEqual(r["dartRecentDocuments"],1)
        self.assertFalse(r["dartDocuments"][0]["patentBusinessRelationshipProven"])
        self.assertFalse(r["publicationApproved"])

    def test_prior_patent_and_press_index_only_create_review_clues(self):
        a,b,c=fixture()
        a["reviewQueue"][0]["priorWithin35Days"]=[{
            "publicationNumber":"1020260131234","publicationDate":"20261006",
            "title":"케이블 부분방전 센서","titleSimilarity":0.87}]
        a["reviewQueue"][0]["olderSameTitle"]={
            "state":"searched_same_title_only","queryComplete":True,
            "matches":[{"publicationNumber":"1020250123000","title":"케이블 부착 센서"}]}
        a["reviewQueue"][0]["claim1Review"]["comparisons"]=[{"status":"text_different"}]
        a["reviewQueue"][0]["mediaReview"]["articleEvidence"]=[{
            "headline":"LS전선 케이블 부분방전 기술 개발",
            "url":"https://news.google.com/rss/articles/test-123",
            "headlineRelation":"technical_headline_overlap_review"}]
        r=d.build(a,b,c,NOW)["dossiers"][0]
        self.assertEqual(r["earlierPublicationsWithin35Days"][0]["publicationNumber"],"1020260131234")
        self.assertFalse(r["earlierPublicationsWithin35Days"][0]["samePatentOrClaimProven"])
        self.assertTrue(r["olderSameTitleSearchComplete"])
        self.assertEqual(len(r["olderSameTitlePublications"]),1)
        self.assertEqual(len(r["officialClaim1Comparisons"]),1)
        self.assertFalse(r["pressEarlierCoverageProven"])
        self.assertEqual(len(r["pressIndexArticlesForManualReview"]),1)
        self.assertFalse(r["patentNoveltyOrTechnicalSuperiorityProven"])
        self.assertIn("indexed_news_needs_full_article_review",r["cautions"])

    def test_future_prior_and_untrusted_press_urls_are_ignored(self):
        a,b,c=fixture()
        a["reviewQueue"][0]["priorWithin35Days"]=[
            {"publicationNumber":"1020260999999","publicationDate":"20261201","title":"미래 유사 특허"},
            {"publicationNumber":"bad","publicationDate":"20261005","title":"위조 ID"}]
        a["reviewQueue"][0]["mediaReview"]["articleEvidence"]=[
            {"headline":"악성 링크","url":"https://news.google.com.evil.test/rss/articles/x"},
            {"headline":"공식 사이트 아닌 기사","url":"https://example.test/story"}]
        r=d.build(a,b,c,NOW)["dossiers"][0]
        self.assertEqual(r["earlierPublicationsWithin35Days"],[])
        self.assertEqual(r["pressIndexArticlesForManualReview"],[])

    def test_old_patent_never_presented_as_new(self):
        a,b,c=fixture()
        x=d.build(a,b,c,NOW)
        self.assertFalse(x["dossiers"][1]["recentPatentWithin3Days"])
        self.assertIn("old_patent_publication_not_new_event",x["dossiers"][1]["cautions"])


if __name__ == "__main__":
    unittest.main()
