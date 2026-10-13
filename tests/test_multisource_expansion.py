import sys,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import research_procurement as g
import customs_hs6 as hs
from business_content import CORPS
NOW=datetime(2026,10,13,tzinfo=timezone(timedelta(hours=9)))

class Tests(unittest.TestCase):
    def test_dart_direct_beat_21_companies(self):
        self.assertEqual(len(CORPS),21)
        self.assertEqual(len(set(CORPS)),21)
        self.assertIn("현대모비스",CORPS)
        self.assertIn("고려아연",CORPS)
        self.assertIn("두산에너빌리티",CORPS)

    def test_research_call_is_not_project_award(self):
        payload={"response":{"header":{"resultCode":"00"},
            "body":{"totalCount":1,"items":{"item":[
                {"subject":"2026 수소 연구개발 R&D 신규 모집",
                 "pressDt":"2026-10-11",
                 "viewUrl":"https://www.msit.go.kr/bbs/view.do?id=101"}]}}}}
        data=g.normalized_research(payload,NOW)
        self.assertEqual(len(data["items"]),1)
        self.assertEqual(data["items"][0]["status"],"official_open_call_not_project_award")
        self.assertTrue(data["items"][0]["sourceType"]=="msit_research_call")

    def test_procurement_bid_is_not_award(self):
        payload={"response":{"header":{"resultCode":"00"},
           "body":{"items":{"item":[{"bidNtceNm":"HVDC 전력망 송전 공사",
             "bidNtceNo":"R26BK00012560","bidNtceDt":"2026-10-12",
             "dminsttNm":"한국전력"}]},"totalCount":1}}}
        p=g.normalized_bids(payload,NOW)
        self.assertEqual(p["items"][0]["noticeNumber"],"R26BK00012560")
        self.assertEqual(p["items"][0]["status"],"bid_notice_not_awarded_or_signed")

    def test_missing_keys_are_not_empty_results(self):
        p=g.build("", "",NOW)
        self.assertEqual(p["matchedItems"],0)
        self.assertFalse(p["sourceComplete"])
        self.assertEqual(p["checks"]["research"]["status"],"key_not_configured")
        self.assertEqual(p["checks"]["procurement"]["status"],"key_not_configured")
        self.assertEqual(p["grantsAwardedVerified"],0)

    def test_one_provider_fails_other_kept_with_no_key_leak(self):
        def handler(url):
            if "msitannouncementinfo" in url:raise ValueError("Fake invalid key")
            return {"response":{"header":{"resultCode":"00"},"body":{"items":[],"totalCount":0}}}
        p=g.build("top-secret","not-secret",NOW,handler)
        self.assertEqual(p["checks"]["research"]["status"],"source_error")
        self.assertEqual(p["checks"]["procurement"]["status"],"checked")
        self.assertNotIn("top-secret",str(p))
        self.assertNotIn("not-secret",str(p))

    def test_total_count_with_missing_items_never_zero(self):
        with self.assertRaises(ValueError):
            g.normalized_api({"response":{"header":{"resultCode":"00"},
                 "body":{"totalCount":6,"items":[]}}})
    def test_hs6_period_comparison_without_issuer_attribution(self):
        def fake(key,code,start,end,country):
            self.assertEqual(len(code),6)
            if start.startswith("2025"):month="202508"
            elif start.startswith("2026"):month="202608"
            else:return []
            return [{"year":month,"expDlr":"1000","expWgt":"200",
                     "impDlr":"100","impWgt":"20"}]
        report=hs.verify_dataset("secret","202501","202609",2026,fetch=fake)
        self.assertEqual(len(report["items"]),6)
        self.assertEqual(report["items"][2]["hs6"],"850423")
        self.assertEqual(report["items"][2]["country"],"ALL")
        self.assertEqual(report["confirmedScoops"],0)
        self.assertIn("기업별",report["items"][2]["claimScope"])
    def test_customs_no_key_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError,"KEY"):
            hs.verify_dataset("","202501","202609",2026)

if __name__=="__main__":unittest.main()
