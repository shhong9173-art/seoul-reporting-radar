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
          "publisherOriginalUrl":"https://business.example.com/news/123",
          "publisherFirstPublishedAt":"2026-10-17T07:00:00+09:00",
          "publisherPublicationTimeVerifiedByHuman":True,
          "evidenceReason":"공개 원자료의 대상 범위와 숫자를 기사 전문과 직접 대조했다.",
          "verdict":verdict}
    if verdict in ("Y","P"):
        form.update(primarySourceType="vehicle_recall",
                    primarySourceUrl="https://www.nhtsa.gov/recalls",
                    primaryPublishedAt="2026-10-15T08:00:00+09:00",
                    primaryPublicationTimeVerifiedByHuman=True,
                    primaryTextComparedAgainstArticle=True,
                    publicTraceOverlap="exact" if verdict=="Y" else "partial")
    if verdict=="N":
        form.update(multiplePublicSourcesChecked=True,
                    reporterEvidenceReviewed=True,
                    publicTraceOverlap="none")
    return form


class ExclusiveReverseTrace(unittest.TestCase):
    def test_reviewed_and_official_source_cases_survive_newest_400_limit(self):
        rows=[]
        for i in range(405):
            row=article(chr(97+i%26),"[단독] 현대차 전기차 공장 %d"%i,
                        date="2026-10-18T%02d:00:00+09:00"%(i%24))
            row["id"]=("%024x"%(i+1))
            rows.append(row)
        past=rows[0]
        manual=rows[1]
        trace=build(index(*rows),[review(manual,"N")],now=NOW,
                    max_candidates=400,evidence_priority_ids=[past["id"]])
        ids={x["articleId"] for x in trace["items"]}
        self.assertEqual(trace["totalObservedExclusiveHeadlines"],400)
        self.assertEqual(trace["availableObservedExclusiveHeadlinesBeforeCap"],405)
        self.assertTrue(trace["sampleIncompleteBecauseOfCap"])
        self.assertIn(past["id"],ids)
        self.assertIn(manual["id"],ids)
        self.assertEqual(trace["evidencePriorityObservedItemsRetained"],2)
        self.assertEqual(trace["humanReviewedYPN"],1)
        self.assertEqual(trace["N"],1)
        self.assertEqual(trace["confirmedScoops"],0)

    def test_unobserved_curated_id_not_injected_as_fake_article(self):
        rows=[article("a","[단독] 현대차 전기차 리콜")]
        result=build(index(*rows),now=NOW,evidence_priority_ids=["f"*24])
        self.assertEqual(result["totalObservedExclusiveHeadlines"],1)
        self.assertEqual(result["evidencePriorityObservedItemsRetained"],0)
        self.assertEqual(result["evidencePriorityIdsNotObserved"],1)
        self.assertFalse(result["reliablePopulationReachEstimated"])

    def test_invalid_pin_or_too_many_pins_fails_closed(self):
        rows=[article("a","[단독] 현대차 전기차 리콜")]
        for pins in (["not-an-article-id"],[34],list(range(700))):
            with self.assertRaises(ValueError):
                build(index(*rows),now=NOW,evidence_priority_ids=pins)

    def test_actual_historical_sources_keep_samsung_original_ids_in_latest_sample(self):
        import json
        root=Path(__file__).resolve().parents[1]
        press=json.loads((root/"digests/press_coverage_index_latest.json").read_text(encoding="utf-8"))
        history=json.loads((root/"digests/historical_exclusive_press_index_latest.json").read_text(encoding="utf-8"))
        leads=json.loads((root/"data/reverse_trace_primary_original_leads.json").read_text(encoding="utf-8"))
        ids=[row["articleId"] for row in leads["items"]]
        observed={r["id"] for r in history["items"] if r.get("id")}
        if not set(ids).issubset(observed):
            self.skipTest("source index has not yet observed all pinned articles; do not invent them")
        result=build(press,history=history,now=NOW,evidence_priority_ids=ids)
        selected={row["articleId"] for row in result["items"]}
        self.assertTrue(set(ids).issubset(selected))
        self.assertEqual(result["humanReviewedYPN"],0)
        self.assertEqual(result["confirmedScoops"],0)

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
        rows=[article(key,title,company="현대차")
              for key,title in zip(("a","b","c"),list(actual)[:3])]
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


    def test_google_rss_time_does_not_prove_official_release_before_press(self):
        # Official source falls before indexed RSS but AFTER the publisher's
        # verified first release. Historically this could be mislabeled Y.
        row=article("a","[단독] 현대차 전기차 리콜",
                    date="2026-10-17T15:00:00+09:00")
        form=review(row,"Y")
        form["publisherFirstPublishedAt"]="2026-10-17T06:00:00+09:00"
        form["primaryPublishedAt"]="2026-10-17T10:00:00+09:00"
        out=build(index(row),[form],now=NOW)
        self.assertEqual(out["Y"],0)
        self.assertEqual(out["unreviewedU"],1)
        self.assertIsNone(out["items"][0]["primaryEvidence"])

    def test_verified_publisher_clock_is_required_even_for_N(self):
        row=article("a","[단독] 현대차 차량 결함")
        for missing in ("publisherFirstPublishedAt",
                        "publisherOriginalUrl",
                        "publisherPublicationTimeVerifiedByHuman"):
            form=review(row,"N")
            form.pop(missing)
            out=build(index(row),[form],now=NOW)
            self.assertEqual(out["N"],0,missing)
            self.assertEqual(out["unreviewedU"],1,missing)

    def test_google_news_redirect_is_not_publisher_original(self):
        row=article("a","[단독] 기아 신차 발매",company="기아")
        form=review(row,"P")
        form["publisherOriginalUrl"]="https://news.google.com/rss/articles/abc"
        out=build(index(row),[form],now=NOW)
        self.assertEqual(out["P"],0)

    def test_unverified_or_late_primary_clock_cannot_create_Y(self):
        row=article("a","[단독] 현대차 리콜")
        for key,value in (
            ("primaryPublicationTimeVerifiedByHuman",False),
            ("primaryPublishedAt","2026-10-17T07:00:00+09:00"),
            ("primaryPublishedAt","2026-10-18T22:00:00+09:00"),
        ):
            form=review(row,"Y")
            form[key]=value
            self.assertEqual(build(index(row),[form],now=NOW)["Y"],0,key)

    def test_verified_chronology_retains_reporter_evidence_not_feed_time(self):
        row=article("a","[단독] 현대차 리콜",
                    date="2026-10-17T21:00:00+09:00")
        form=review(row,"Y")
        out=build(index(row),[form],now=NOW)
        proof=out["items"][0]["primaryEvidence"]
        self.assertEqual(out["Y"],1)
        self.assertFalse(proof["rssTimestampUsedForChronology"])
        self.assertEqual(proof["publisherFirstPublishedAt"],
                         "2026-10-17T07:00:00+09:00")
        self.assertTrue(proof["publisherPublicationTimeVerifiedByHuman"])

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
