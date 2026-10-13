import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_editorial_desk as d

NOW=datetime(2026,10,13,10,0,tzinfo=timezone(timedelta(hours=9)))
PUB="1020260147965"
PRIOR="1020260131234"
CJ="1020260147319"


def fixtures():
    current={"publicationNumber":PUB,"publicationDate":"20261012","title":"휠체어 승하차용 도어 구조 및 램프 장치","abstract":"휠체어 승하차 보조 램프",
             "applicationNumber":"1020250042700","applicants":["현대자동차주식회사","기아 주식회사","주식회사 광진"]}
    previous={"publicationNumber":PRIOR,"publicationDate":"20261006","title":"휠체어 승하차용 도어 구조 및 램프 시스템",
              "abstract":"전동 램프 시스템"}
    other={"publicationNumber":CJ,"publicationDate":"20261008","title":"차량 플라스틱을 분해 효소로 재활용하는 방법"}
    official={"generatedAt":"2026-10-13T10:00:00+09:00",
              "sourceWindowComplete":True,"items":[current,previous,other]}
    deep={"generatedAt":"2026-10-13T10:02:00+09:00",
          "patentDatasetGeneratedAt":official["generatedAt"],"investigations":[{
              "publicationNumber":PUB,
              "priorFullTitleCheck":{"status":"동일 제목 공보 발견",
                                     "complete":True,"matches":[{"publicationNumber":PRIOR}]}}]}
    story={"generatedAt":"2026-10-13T10:03:00+09:00",
           "officialSourceGeneratedAt":official["generatedAt"],
           "deepSourceGeneratedAt":deep["generatedAt"],"investigations":[{
            "publicationNumber":PUB,"publicationDate":"20261012","title":current["title"],
            "rank":77,"topic":"차체·교통약자 접근성","applicants":current["applicants"],
            "sourceAbstractExcerpt":"휠체어 승하차 보조","coveredCompanies":["현대자동차","기아"],
            "outsideBeatCoApplicants":["주식회사 광진"],
            "reportingTitleDraft":"현대차·기아·광진, '휠체어 승하차용 도어' 공동출원",
            "pressCoverage":{"status":"미조회 · 미보도 확정 불가"}},
           {"publicationNumber":CJ,"publicationDate":"20261008","title":other["title"],
            "rank":68,"topic":"순환소재·폐차재활용","applicants":["현대차","기아","CJ"],
            "coveredCompanies":["현대차","기아"],"outsideBeatCoApplicants":["CJ"],
            "reportingTitleDraft":"CJ·현대차 효소 공동출원",
            "pressCoverage":{"status":"미조회 · 미보도 확정 불가"}}]}
    claims={"generatedAt":"2026-10-13T10:04:00+09:00",
            "patentDatasetGeneratedAt":official["generatedAt"],
            "deepDatasetGeneratedAt":deep["generatedAt"],"reviews":[{
             "publicationNumber":PUB,"claimVerified":True,
             "claim1Excerpt":"청구항 제1항에서 램프 장치와 도어를 결합",
             "priorComparisons":[]}]}
    labels={"reviews":[]}
    cases={"cases":[{"publicationNumber":CJ,"caseName":"이미 기보도된 CJ 협력 특허"}]}
    return official,deep,story,claims,labels,cases


class DeskTests(unittest.TestCase):
    def test_no_press_search_means_no_scoop_and_no_shortlist(self):
        report=d.evaluate(*fixtures(),now=NOW)
        self.assertEqual(report["candidateCount"],2)
        self.assertEqual(report["shortlistCount"],0)
        self.assertEqual(report["confirmedScoops"],0)
        self.assertFalse(report["reviewQueue"][0]["scoopConfirmed"])

    def test_partial_rss_failure_is_not_counted_as_press_check_complete(self):
        f=fixtures()
        f[1]["investigations"][0]["priorFullTitleCheck"]["matches"]=[]
        f[2]["investigations"][0]["pressCoverage"]={
            "queries":[{"query":"정확한 공개번호","status":"no_hits","articles":[]},
                       {"query":"기술어 대조","status":"error","articles":[]}],
            "completeSearch":False}
        report=d.evaluate(*f,now=NOW)
        row=next(x for x in report["reviewQueue"] if x["publicationNumber"]==PUB)
        self.assertFalse(row["mediaReview"]["checked"])
        self.assertEqual(row["mediaReview"]["state"],"search_errors_not_cleared")
        self.assertEqual(row["mediaReview"]["searchErrors"],1)
        self.assertEqual(row["deskStatus"],"research_first_media_not_checked")
        self.assertEqual(report["newsSearched"],0)
        self.assertEqual(report["newsAttempted"],1)
        self.assertEqual(report["newsIncomplete"],1)
        self.assertEqual(report["newsNotAttempted"],1)
        self.assertEqual(report["shortlistCount"],0)

    def test_media_hit_and_other_query_error_still_blocks_shortlist(self):
        f=fixtures()
        f[1]["investigations"][0]["priorFullTitleCheck"]["matches"]=[]
        f[2]["investigations"][0]["pressCoverage"]={
            "queries":[{"query":"일반 기사","status":"hits","articles":[{
                "title":"완성차 업계, 2026년 수출 실적 점검",
                "url":"https://news.google.com/rss/articles/abc"}]},
                       {"query":"별도 기술 검색","status":"error","articles":[]}]}
        report=d.evaluate(*f,now=NOW)
        row=next(x for x in report["reviewQueue"] if x["publicationNumber"]==PUB)
        self.assertEqual(row["mediaReview"]["hits"],1)
        self.assertFalse(row["mediaReview"]["checked"])
        self.assertEqual(report["newsIncomplete"],1)
        self.assertEqual(report["shortlistCount"],0)

    def test_all_successful_queries_count_completed_but_not_exclusivity(self):
        f=fixtures()
        f[1]["investigations"][0]["priorFullTitleCheck"]["matches"]=[]
        f[2]["investigations"][0]["pressCoverage"]={
            "queries":[{"query":"공개번호","status":"no_hits","articles":[]},
                       {"query":"특허명","status":"no_hits","articles":[]}]}
        report=d.evaluate(*f,now=NOW)
        row=next(x for x in report["reviewQueue"] if x["publicationNumber"]==PUB)
        self.assertTrue(row["mediaReview"]["checked"])
        self.assertEqual(report["newsSearched"],1)
        self.assertEqual(report["newsIncomplete"],0)
        self.assertEqual(report["shortlistCount"],1)
        self.assertFalse(row["scoopConfirmed"])

    def test_official_prior_within_window_not_worldwide_patent_novelty(self):
        report=d.evaluate(*fixtures(),now=NOW)
        row=next(x for x in report["reviewQueue"] if x["publicationNumber"]==PUB)
        self.assertEqual(row["priorWithin35Days"][0]["publicationNumber"],PRIOR)
        self.assertIn("35일",row["priorWithin35Days"][0]["comparisonScope"])
        self.assertEqual(row["claim1Review"]["state"],"official_claim1_verified")
        self.assertFalse(row["publicationNoveltyConfirmed"])
        self.assertEqual(row["olderSameTitle"]["state"],"searched_same_title_only")

    def test_early_article_hit_marks_risk_not_confirmed_repeat(self):
        f=fixtures()
        f[2]["investigations"][0]["pressCoverage"]={
            "queries":[{"query":"현대차 광진","status":"hits","articles":[{
               "title":"현대차, 휠체어 승하차용 도어 구조 및 램프 장치 특허",
               "url":"https://news.google.com/rss/articles/abc",
               "publishedAt":"Mon, 12 Oct 2026 11:00:00 GMT"}]}]}
        report=d.evaluate(*f,now=NOW)
        row=next(x for x in report["reviewQueue"] if x["publicationNumber"]==PUB)
        self.assertIn("indexed_similar_article_needs_manual_review",row["cautionFlags"])
        self.assertEqual(report["shortlistCount"],0)
        self.assertFalse(row["mediaReview"]["articleEvidence"][0]["samePatentConfirmed"])

    def test_article_without_matching_technical_title_not_auto_duplicate(self):
        f=fixtures()
        # Test unrelated press indexing separately from a genuine older
        # same-title patent, which deliberately blocks the shortlist.
        f[1]["investigations"][0]["priorFullTitleCheck"]["matches"]=[]
        f[2]["investigations"][0]["pressCoverage"]={
            "queries":[{"query":"회사","status":"hits","articles":[{
               "title":"완성차 업계, 2026년 수출 실적 점검",
               "url":"https://news.google.com/rss/articles/abc"}]}]}
        report=d.evaluate(*f,now=NOW)
        row=next(x for x in report["reviewQueue"] if x["publicationNumber"]==PUB)
        self.assertEqual(row["mediaReview"]["state"],"indexed_articles_need_review")
        self.assertEqual(report["shortlistCount"],1)

    def test_alternative_cj_enzyme_headline_matches_official_abstract_concepts_only(self):
        relation,score=d.headline_match(
            {"publicationNumber":CJ,
             "title":"자동차용 플라스틱 부품을 재생하는 방법, 폴리에스테르 수지를 제조하는 방법",
             "sourceAbstractExcerpt":"PET 플라스틱을 폴리에스테르 분해 효소로 분해해 테레프탈산을 얻는다"},
            "현대차·CJ, 플라스틱 먹는 효소 기술 특허")
        self.assertEqual(relation,"abstract_tech_headline_overlap_review")
        self.assertGreaterEqual(score,0.6)

    def test_generic_title_does_not_trigger_strong_identity(self):
        status,score=d.headline_match({"title":"차량 제어 장치 및 방법",
                                        "publicationNumber":PUB},
                                       "미래차 제어장치 기술 경쟁")
        self.assertEqual(status,"weak_or_generic_index_hit")
        self.assertLess(score,0.55)

    def test_retrospective_known_case_never_top_pitch(self):
        f=fixtures()
        f[2]["investigations"][1]["pressCoverage"]={
            "queries":[{"query":"효소","status":"no_hits","articles":[]}]}
        r=d.evaluate(*f,now=NOW)
        known=next(x for x in r["reviewQueue"] if x["publicationNumber"]==CJ)
        self.assertEqual(known["deskStatus"],"known_or_reported_not_scoop")
        self.assertEqual(r["shortlistCount"],0)

    def test_negative_human_evidence_suppresses_shortlist(self):
        f=fixtures()
        f[2]["investigations"][0]["pressCoverage"]={
            "queries":[{"query":"도어","status":"no_hits","articles":[]}]}
        f[4]["reviews"]=[{"publicationNumber":PUB,"decision":"already_reported"}]
        r=d.evaluate(*f,now=NOW)
        self.assertEqual(r["shortlistCount"],0)
        self.assertEqual(r["reviewQueue"][0]["humanEditorialDecision"],"already_reported")

    def test_missing_claim_or_mismatched_claim_is_unverified_not_reused(self):
        f=fixtures()
        f[1]["investigations"][0]["priorFullTitleCheck"]["matches"]=[]
        f[3]["patentDatasetGeneratedAt"]="2026-01-01"
        f[2]["investigations"][0]["pressCoverage"]={"queries":[{"query":"x","status":"no_hits","articles":[]}]}
        r=d.evaluate(*f,now=NOW)
        x=next(y for y in r["reviewQueue"] if y["publicationNumber"]==PUB)
        self.assertFalse(r["claimSnapshotConsistent"])
        self.assertEqual(x["claim1Review"]["state"],"not_checked")
        self.assertEqual(r["shortlistCount"],1)

    def test_source_mismatch_fails_closed(self):
        f=fixtures()
        f[2]["officialSourceGeneratedAt"]="2026-01-01"
        with self.assertRaisesRegex(ValueError,"do not match"):
            d.evaluate(*f,now=NOW)

    def test_recent_prior_excludes_future_publications_and_same_number(self):
        f=fixtures()
        official=f[0]
        official["items"].append({"publicationNumber":"1020260155555",
                                  "publicationDate":"20261015",
                                  "title":"휠체어 승하차용 도어 구조 및 램프"})
        lead=f[2]["investigations"][0]
        ids=[x["publicationNumber"] for x in d.recent_priors(lead,official)]
        self.assertNotIn("1020260155555",ids)
        self.assertNotIn(PUB,ids)
        self.assertIn(PRIOR,ids)


if __name__=="__main__":
    unittest.main()
