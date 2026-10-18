"""Offline reverse-trace review must not fabricate Y/P/N or source reach."""
import copy
import sys
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.exclusive_reverse_trace import build,kind_for

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,22,0,tzinfo=KST)


def article(key,title,company="현대차",date="2026-10-17T08:00:00+09:00"):
    return {"id":key*24,"title":title,"published":date,
            "sourceName":"경제뉴스","url":"https://news.example/articles/"+key,
            "companies":[company],"global":False,
            "fulltextReviewed":False,"coverageIndexOnly":True}


def index(*rows):
    return {"status":"observed_domestic_press_index_not_complete_coverage",
            "generatedAt":"2026-10-18T21:10:00+09:00",
            "itemCount":len(rows),"items":list(rows)}


def review(item,verdict="Y"):
    form={"articleId":item["id"],"reviewer":"현장 검증기자",
          "reviewedByHuman":True,"articleFulltextReviewed":True,
          "reviewedAt":"2026-10-18T21:30:00+09:00",
          "evidenceReason":"공개 원자료의 대상 범위와 숫자를 기사 전문과 직접 대조했다.",
          "verdict":verdict}
    if verdict in ("Y","P"):
        form.update(primarySourceType="vehicle_recall",
                    primarySourceUrl="https://www.nhtsa.gov/recalls",
                    primaryPublishedAt="2026-10-15T08:00:00+09:00",
                    primaryTextComparedAgainstArticle=True,
                    publicTraceOverlap="exact" if verdict=="Y" else "partial")
    if verdict=="N":
        form.update(multiplePublicSourcesChecked=True,
                    reporterEvidenceReviewed=True,
                    publicTraceOverlap="none")
    return form


class ExclusiveReverseTrace(unittest.TestCase):
    def test_actual_2026_industry_exclusive_titles_have_subject_categories(self):
        actual={
            "[단독] 현대차 새만금 9조 투자 첫삽 코앞…정부 지원 51개 중 4개 완료":
                "공장·생산·투자",
            "[단독]현대차 ‘R&D거점’ 찾는 與野…자율주행 입법 시동 거나":
                "정책·규제·입법",
            "[단독] 현대차 스타리아 EV 모터룸 빗물 유입에 ‘분통’":
                "리콜·안전",
            "[단독] 현대제철 철강 관세 적용 확대":
                "통상·관세",
            "[단독] 현대모비스 사업부 물적분할 추진":
                "자본·지배구조",
            "[단독] 대한전선 신규 수주 계약":
                "수주·입찰",
        }
        for title,category in actual.items():
            self.assertEqual(kind_for(title),category,title)
        rows=[article("a",title,company="현대차")
              for title in list(actual)[:3]]
        res=build(index(*rows),now=NOW)
        self.assertEqual(res["humanReviewedYPN"],0)
        self.assertEqual(res["unreviewedU"],3)
        self.assertEqual(len(res["byType"]),3)
        self.assertTrue(all(v["measuredSourceReach"] is None
                            for v in res["byType"].values()))
        self.assertEqual(res["confirmedScoops"],0)

    def test_all_unknown_first_baseline_is_not_measured(self):
        rows=[article("a","[단독] 현대차 전기차 리콜 9만대"),
              article("b","[단독] 기아 신차 인증",company="기아"),
              article("c","[단독] KIA 타이거즈 투수 명단"),
              article("d","자동차 공장 발표")]
        result=build(index(*rows),now=NOW)
        self.assertEqual(result["totalObservedExclusiveHeadlines"],2)
        self.assertEqual(result["humanReviewedYPN"],0)
        self.assertEqual(result["unreviewedU"],2)
        self.assertFalse(result["couldMeasureReach"])
        self.assertFalse(result["reliablePopulationReachEstimated"])
        self.assertTrue(all(x["publicTraceClass"]=="U" for x in result["items"]))
        self.assertEqual(result["confirmedScoops"],0)
        self.assertEqual(result["approvedArticles"],0)

    def test_only_manually_verified_Y_P_N_count_as_reviewed(self):
        a=article("a","[단독] 현대차 리콜"),
        b=article("b","[단독] 기아 공장 증설",company="기아")
        c=article("c","[단독] 포스코 공급 계약",company="포스코")
        d=article("d","[단독] 현대모비스 신형 부품",company="현대모비스")
        a=a[0]
        result=build(index(a,b,c,d),[
            review(a,"Y"),review(b,"P"),review(c,"N")],now=NOW)
        self.assertEqual([result[x] for x in ("Y","P","N","unreviewedU")],
                         [1,1,1,1])
        self.assertEqual(result["humanReviewedYPN"],3)
        self.assertFalse(result["couldMeasureReach"])
        self.assertFalse(result["reliablePopulationReachEstimated"])
        self.assertEqual(result["byType"]["리콜·안전"]["Y"],1)
        self.assertIsNone(result["byType"]["리콜·안전"]["measuredSourceReach"])
        self.assertEqual(result["verifiedPublicSourceCategories"]["vehicle_recall"],2)

    def test_false_claim_exact_must_be_unknown_not_Y(self):
        a=article("a","[단독] 현대차 리콜")
        form=review(a)
        form["primaryPublishedAt"]="2026-10-18T20:00:00+09:00"
        out=build(index(a),[form],now=NOW)
        self.assertEqual(out["items"][0]["publicTraceClass"],"U")
        self.assertIsNone(out["items"][0]["primaryEvidence"])

    def test_no_source_research_for_N_cannot_create_synthetic_N(self):
        a=article("a","[단독] 현대차 리콜")
        form=review(a,"N")
        form["multiplePublicSourcesChecked"]=False
        out=build(index(a),[form],now=NOW)
        self.assertEqual(out["N"],0)
        self.assertEqual(out["unreviewedU"],1)

    def test_missing_article_fulltext_or_person_only_stays_unknown(self):
        a=article("a","[단독] 현대차 리콜")
        form=review(a,"Y")
        form["articleFulltextReviewed"]=False
        out=build(index(a),[form],now=NOW)
        self.assertEqual(out["Y"],0)
        self.assertEqual(out["items"][0]["humanReviewStatus"],
                         "not_reviewed_or_invalid_evidence")

    def test_wrong_or_ambiguous_source_must_be_unknown(self):
        a=article("a","[단독] 현대차 리콜")
        for wrong in [
            {"primarySourceUrl":"https://www.nhtsa.gov.evil.example/recalls",
             "primarySourceType":"not-a-recognized-source"},
            {"primaryPublishedAt":"2026-10-17T08:00:00+09:00"},
            {"publicTraceOverlap":"partial"},
            {"primaryTextComparedAgainstArticle":False},
            {"reviewedAt":"unknown"}]:
            candidate=review(a,"Y")
            candidate.update(wrong)
            result=build(index(a),[candidate],now=NOW)
            self.assertEqual(result["items"][0]["publicTraceClass"],"U")

    def test_duplicate_human_review_rejected_and_no_unsafe_guess(self):
        a=article("a","[단독] 현대차 리콜")
        with self.assertRaises(ValueError):
            build(index(a),[review(a),review(a)],now=NOW)

    def test_historical_september_exclusive_adds_to_current_three_without_autovalidation(self):
        from scripts.historical_exclusive_press_collector import (
            STATUS as HISTORY_STATUS)
        september=article(
            "f","[단독] 포스코 제철소 신규 투자 2026년 9월",company="포스코",
            date="2026-09-15T08:00:00+09:00")
        september.update(rssIndexedHeadlineOnly=True,
            publisherOriginalUrlVerified=False,
            publisherPublicationTimeVerified=False)
        history={
            "status":HISTORY_STATUS,"generatedAt":"2026-10-18T21:40:00+09:00",
            "itemCount":1,"items":[september],"windowHealth":{},
            "allDomesticIndustryExclusivesCovered":False,"confirmedScoops":0,
            "failedWindowsThisRun":0}
        current=article("a","[단독] 현대차 전기차 9만대 리콜")
        out=build(index(current),now=NOW,history=history)
        self.assertEqual(out["totalObservedExclusiveHeadlines"],2)
        self.assertEqual(out["historicalSearchObservedRows"],1)
        self.assertEqual(out["historicalSearchIndexAt"],history["generatedAt"])
        self.assertEqual(out["unreviewedU"],2)
        self.assertFalse(out["historicalSearchAllSourcesChecked"])
        self.assertFalse(out["reliablePopulationReachEstimated"])
        old=next(x for x in out["items"] if x["articleId"]==september["id"])
        self.assertTrue(old["historicalSearchHeadlineOnly"])
        self.assertFalse(old["publisherOriginalUrlVerifiedByCollector"])
        self.assertFalse(old["confirmedExclusive"])

    def test_duplicate_article_in_history_and_current_is_one_review_candidate(self):
        row=article("a","[단독] 현대차 차량 리콜")
        row.update(rssIndexedHeadlineOnly=True,
            publisherOriginalUrlVerified=False)
        history={
            "status":"historical_industry_exclusive_rss_partial_index",
            "generatedAt":"2026-10-18T21:00:00+09:00",
            "itemCount":1,"items":[row],"windowHealth":{},
            "allDomesticIndustryExclusivesCovered":False,"confirmedScoops":0}
        out=build(index(row),history=history,now=NOW)
        self.assertEqual(out["totalObservedExclusiveHeadlines"],1)

    def test_invalid_historical_data_fails_instead_of_erasing_verified_history(self):
        row=article("a","[단독] 포스코 후판 증설",company="포스코")
        row.update(rssIndexedHeadlineOnly=True,
            publisherOriginalUrlVerified=False)
        history={
            "status":"historical_industry_exclusive_rss_partial_index",
            "itemCount":1,"items":[row],"windowHealth":{},
            "allDomesticIndustryExclusivesCovered":False,"confirmedScoops":0}
        history["items"][0]["fulltextReviewed"]=True
        with self.assertRaises(ValueError):
            build(index(),history=history,now=NOW)

    def test_seed_only_index_yields_no_estimated_reach(self):
        raw=index()
        raw["seedOnly"]=True
        raw["generatedAt"]=None
        result=build(raw,now=NOW)
        self.assertEqual(result["humanReviewedYPN"],0)
        self.assertTrue(result["pressIndexSeedOnly"])
        self.assertFalse(result["couldMeasureReach"])

    def test_reject_invalid_index_without_interpreting_as_zero_stories(self):
        with self.assertRaises(ValueError):
            build({"status":"unavailable","items":[]},now=NOW)
        with self.assertRaises(ValueError):
            build({"status":"observed_domestic_press_index_not_complete_coverage",
                   "itemCount":1,"items":[]},now=NOW)


if __name__=="__main__":
    unittest.main()
