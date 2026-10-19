import unittest
from datetime import datetime,timezone
from scripts.recent_exclusive_recall_audit import audit,STATUS

KST=timezone.utc
NOW=datetime(2026,10,19,17,30,tzinfo=KST)
def item(title,ref,when="2026-10-19T15:30:00+00:00"):
    return {"title":title,"sourceName":"언론사",
            "url":"https://news.google.com/rss/articles/"+ref,
            "published":when,"global":False}
def hist(items):
    return {"status":"historical_industry_exclusive_rss_partial_index",
            "generatedAt":"2026-10-19T16:00:00+00:00",
            "itemCount":len(items),"items":items,
            "allDomesticIndustryExclusivesCovered":False}

class CompareRecentObservedExclusives(unittest.TestCase):
    def test_reports_two_way_misses_but_never_scoop(self):
        a=item("[단독] 현대제철 사고","steel")
        b=item("[단독] 천보 배터리 수출","chem")
        c=item("[단독] 현대차 새 공장","auto")
        out=audit([a,b],hist([a,c]),now=NOW)
        self.assertEqual(out["status"],STATUS)
        self.assertEqual(out["newsIndexObservedExclusive"],2)
        self.assertEqual(out["historyIndexObservedExclusive"],2)
        self.assertEqual(out["observedInBoth"],1)
        self.assertEqual(out["newsOnlyObserved"],1)
        self.assertEqual(out["historyOnlyObserved"],1)
        self.assertEqual(out["newsOnlyExamples"][0]["title"],b["title"])
        self.assertFalse(out["domesticUnreportedProved"])
        self.assertFalse(out["rssCoverageExhaustive"])
        self.assertEqual(out["confirmedScoops"],0)

    def test_invalid_or_old_dates_and_nonexclusive_not_new_competitor(self):
        old=item("[단독] 포스코 작년 계약","old","2026-10-01T12:00:00+00:00")
        naive=item("[단독] 기아 신차","naive","2026-10-19T12:00:00")
        normal=item("기아 어제 뉴스","normal")
        out=audit([old,naive,normal],hist([]),now=NOW)
        self.assertEqual(out["newsIndexObservedExclusive"],0)
        self.assertEqual(out["newsOnlyObserved"],0)
        self.assertFalse(out["domesticUnreportedProved"])

    def test_corrupt_historical_source_never_marked_empty(self):
        for bad in [None,{},{"status":"unavailable","items":[],"itemCount":0},
                    {**hist([]),"itemCount":4},
                    {**hist([]),"allDomesticIndustryExclusivesCovered":True}]:
            with self.assertRaises(ValueError):
                audit([],bad,now=NOW)
        with self.assertRaises(ValueError):
            audit([],hist([]),now=datetime(2026,10,20,2,0))

if __name__=="__main__":
    unittest.main()
