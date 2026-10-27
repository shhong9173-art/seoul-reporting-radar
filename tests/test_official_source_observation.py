import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from official_source_observation import update_source_states

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,18,23,0,tzinfo=KST)


def item(title="기아 자동차 리콜",*,url="https://car.go.kr/recall/123",
         published="2026-10-18T08:00:00+09:00",direct=True):
    return {
        "title":title,"url":url,"published":published,
        "querySite":"car.go.kr",
        **({"signalType":"official_recall_notice"} if direct else {})
    }


class OriginObservationTest(unittest.TestCase):
    def test_first_harvest_is_baseline_not_new_scoop(self):
        first=update_source_states(None,{"car.go.kr":{"rssQueries":3,"errors":[]}},
             {"car-recalls":{"queriesAttempted":2,"queriesSucceeded":2,
                             "errors":[]}},[item()],now=NOW)
        d=first["sources"]["direct:car-recalls"]
        self.assertTrue(d["baselineOnly"])
        self.assertEqual(d["newlyObservedSincePreviousOk"],0)
        self.assertEqual(len(d["seenKeys"]),1)
        self.assertFalse(d["domesticUnreportedProved"])
        self.assertFalse(d["actualPublicationNoveltyProved"])
        self.assertEqual(first["confirmedScoops"],0)

    def test_recovery_after_outage_is_unknown_publication_novelty(self):
        good={"car-recalls":{"queriesAttempted":1,"queriesSucceeded":1,"errors":[]}}
        failed={"car-recalls":{"queriesAttempted":2,"queriesSucceeded":0,
                                "errors":["timeout"]}}
        start=update_source_states(None,{},good,[item()],now=NOW)
        outage=update_source_states(start,{},failed,[],now=NOW+timedelta(hours=1))
        self.assertEqual(outage["sources"]["direct:car-recalls"]["failStreak"],1)
        self.assertEqual(outage["sources"]["direct:car-recalls"]["lastOk"],
                         start["generatedAt"])
        self.assertIn("direct:car-recalls",outage["unknownOrFailedSources"])
        second=item(url="https://car.go.kr/recall/124")
        restored=update_source_states(outage,{},good,[second],
                                      now=NOW+timedelta(hours=2))
        d=restored["sources"]["direct:car-recalls"]
        self.assertEqual(d["failStreak"],0)
        self.assertTrue(d["observedAfterPriorGap"])
        self.assertEqual(d["rawNewlySeenAfterGap"],1)
        self.assertFalse(d["actualPublicationNoveltyProved"])
        self.assertFalse(d["domesticUnreportedProved"])

    def test_official_google_index_empty_is_not_empty_board(self):
        out=update_source_states(None,
            {"scourt.go.kr":{"rssQueries":3,"rssRawItems":0,"errors":[]}},
            {"scourt-case-releases":{"pagesAttempted":2,"pagesFetched":0,
                                     "errors":["timeout"]}},[],now=NOW)
        self.assertEqual(out["sources"]["rss:scourt.go.kr"]["status"],
                         "index_responded")
        self.assertEqual(out["sources"]["direct:scourt-case-releases"]["status"],
                         "failed")
        self.assertFalse(out["sources"]["rss:scourt.go.kr"]["domesticUnreportedProved"])

    def test_partial_irregular_provider_has_last_ok_and_failure(self):
        d={"iris-rnd-announcements":{"listPagesAttempted":4,"listPagesFetched":3,
                                     "collectionComplete":False,"errors":["retry"]},
           "ntis-announcements":{"queriesAttempted":2,"searchPagesFetched":2,
                                 "coverageLimited":True,"errors":[],
                                 "exclusions":{"detail_fetch_failed":2}},
           "kepco-enc":{"listFetched":True,"errors":[]}}
        out=update_source_states(None,{},d,[],now=NOW)
        self.assertEqual(out["sources"]["direct:iris-rnd-announcements"]["status"],"partial")
        self.assertEqual(out["sources"]["direct:ntis-announcements"]["status"],"partial")
        self.assertEqual(out["sources"]["direct:kepco-enc"]["status"],
                         "checked_list_not_exhaustive")
        self.assertIn("direct:iris-rnd-announcements",out["partiallyCollectedSources"])

    def test_design_coverage_limit_is_not_a_repeating_failure(self):
        # First search page only / detail cap, every page that was opened was read: not exhaustive, not failed.
        limited={"queriesAttempted":3,"searchPagesFetched":3,"coverageLimited":True,"collectionComplete":False,
                 "errors":[{"stage":"detail","attempt":1,"error":"timed out","retry":True}],
                 "exclusions":{"outside_lookback":6}}
        out=update_source_states(None,{},{"ntis-announcements":limited},[],now=NOW)
        self.assertEqual(out["sources"]["direct:ntis-announcements"]["status"],"checked_list_not_exhaustive")
        self.assertEqual(out["sources"]["direct:ntis-announcements"]["failStreak"],0)
        for extra in ({"errors":[{"stage":"detail","attempt":2,"error":"timed out","retry":False}]},
                      {"exclusions":{"detail_deferred_after_timeouts":4}}, {"detailCircuitOpen":True},
                      {"exclusions":{"list_detail_title_mismatch":1}}, {"invalidLinks":2}):
            with self.subTest(extra=extra):
                out=update_source_states(None,{},{"ntis-announcements":{**limited,**extra}},[],now=NOW)
                self.assertEqual(out["sources"]["direct:ntis-announcements"]["status"],"partial")

    def test_corrupt_last_success_state_is_not_silently_reset(self):
        good={"car-recalls":{"queriesAttempted":1,"queriesSucceeded":1,"errors":[]}}
        with self.assertRaises(ValueError):
            update_source_states({"status":"wrong","sources":{}},{},good,[],now=NOW)
        start=update_source_states(None,{},good,[],now=NOW)
        start["sources"]["direct:car-recalls"]["seenKeys"]=["bad"]
        with self.assertRaises(ValueError):
            update_source_states(start,{},good,[],now=NOW+timedelta(hours=1))

    def test_unattempted_sources_preserve_history_without_freshness(self):
        before=update_source_states(None,{},{
            "car-recalls":{"queriesAttempted":1,"queriesSucceeded":1,"errors":[]}},
            [item()],now=NOW)
        after=update_source_states(before,{}, {},[],now=NOW+timedelta(hours=1))
        d=after["sources"]["direct:car-recalls"]
        self.assertEqual(d["status"],"not_checked_this_run")
        self.assertEqual(d["lastOk"],NOW.isoformat(timespec="seconds"))
        self.assertFalse(d["domesticUnreportedProved"])

if __name__=="__main__":
    unittest.main()
