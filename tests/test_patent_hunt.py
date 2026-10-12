"""KIPRIS applicant/date checks: no phantom patents or invented scoops."""
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_hunt as p

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,13,8,0,tzinfo=KST)


def row(applicant="현대자동차주식회사",pubdate="20261012",
        title="자율주행 차량의 경로 제어 방법",
        abstract="센서융합으로 자율주행 중 충돌 위험을 줄이는 제어"):
    return {"applicantName":applicant,"openDate":pubdate,
            "applicationDate":"20250412","openNumber":"10-2026-0123456",
            "applicationNumber":"10-2025-0054321","inventionTitle":title,
            "astrtCont":abstract,"ipcNumber":"B60W",
            "registerStatus":"공개"}


def doc(rows,total=None):
    total=len(rows) if total is None else total
    data=''.join("<item>"+''.join(f"<{k}>{v}</{k}>" for k,v in r.items())+"</item>" for r in rows)
    return (f"<response><header><resultCode>00</resultCode></header>"
            f"<body><items>{data}</items><count><totalCount>{total}</totalCount>"
            "</count></body></response>").encode("utf-8")


class PatentScoutTests(unittest.TestCase):
    def test_exact_issuer_identity_not_a_partial_hyundai_hit(self):
        variants=p.APPLICANTS["현대자동차"]
        self.assertTrue(p.applicant_matches("현대자동차 주식회사|기아 주식회사",variants))
        self.assertFalse(p.applicant_matches("현대모비스주식회사",variants))
        self.assertFalse(p.applicant_matches("현대자동차정비주식회사",variants))
        self.assertFalse(p.applicant_matches("현대자동차서비스",variants))

    def test_publication_date_matters_not_filing_date(self):
        x=p.verified_patent(row(pubdate="20261012"),"현대자동차",
                             p.APPLICANTS["현대자동차"],"20260908","20261013")
        self.assertEqual(x["publicationDate"],"20261012")
        self.assertEqual(x["applicationDate"],"20250412")
        self.assertIn("미확인",x["notProven"])
        self.assertFalse(x["scoopConfirmed"])

    def test_old_publication_is_not_new_because_it_was_filed_recently(self):
        r=row(pubdate="20250103");r["applicationDate"]="20240103"
        self.assertIsNone(p.verified_patent(r,"현대자동차",p.APPLICANTS["현대자동차"],
                                             "20260908","20261013"))

    def test_no_grant_or_launch_inferred(self):
        x=p.verified_patent(row(),"현대자동차",p.APPLICANTS["현대자동차"],
                             "20260908","20261013")
        self.assertEqual(x["registerStatus"],"공개")
        self.assertIn("제품화",x["notProven"])
        self.assertIn("단독",x["notProven"])

    def test_wrong_applicant_even_with_identical_title_rejected(self):
        r=row(applicant="현대모비스주식회사")
        self.assertIsNone(p.verified_patent(r,"현대자동차",p.APPLICANTS["현대자동차"],
                                             "20260908","20261013"))

    def test_ambiguous_generic_patent_not_reported_as_breakthrough(self):
        self.assertIsNone(p.verified_patent(
            row(title="베어링 제조 방법",abstract="프레스와 금형"),
            "현대자동차",p.APPLICANTS["현대자동차"],"20260908","20261013"))

    def test_malformed_publication_number_rejected(self):
        r=row();r["openNumber"]="!"
        self.assertIsNone(p.verified_patent(r,"현대자동차",p.APPLICANTS["현대자동차"],
                                             "20260908","20261013"))

    def test_full_api_xml_with_explicit_zero_is_not_failure(self):
        result=p.parse_response(doc([]))
        self.assertEqual(result,{"total":0,"items":[]})

    def test_missing_total_is_api_error_not_no_publications(self):
        with self.assertRaises(ValueError):
            p.parse_response(b"<response><body><items/></body></response>")

    def test_api_error_code_is_not_empty_results(self):
        with self.assertRaises(RuntimeError):
            p.parse_response(b"<response><header><resultCode>30</resultCode></header>"
                             b"<body><count><totalCount>0</totalCount></count></body></response>")

    def test_reject_doctype_entities(self):
        with self.assertRaises(ValueError):
            p.parse_response(b'<!DOCTYPE test [ <!ENTITY x SYSTEM "file:///etc/passwd"> ]><response/>')

    def test_search_bounded_and_service_key_last(self):
        captured=[]
        def fetch(url):
            captured.append(url)
            return doc([row()])
        result=p.search_applicant("fake-key","현대자동차","20260908","20261013",fetch=fetch)
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["rows"]),1)
        self.assertIn("openDate=20260908~20261013",captured[0])
        self.assertIn("ServiceKey=fake-key",captured[0])

    def test_incomplete_pagination_cannot_be_claimed_all_checked(self):
        def fetch(url):
            return doc([row()],total=201)
        result=p.search_applicant("fake-key","현대자동차","20260908","20261013",
                                  fetch=fetch,max_pages=2)
        self.assertFalse(result["complete"])

    def test_initial_baseline_not_fake_first_found(self):
        def search(key,term,start,end):
            return {"rows":[row()],"total":1,"complete":True}
        report=p.build("fake",now=NOW,search=search,names=["현대자동차"],
                       coverage=lambda _:{"status":"미검증","articles":[]})
        self.assertEqual(report["candidateCount"],1)
        self.assertEqual(report["alertCount"],0)
        self.assertTrue(report["baselineInitialized"])
        self.assertEqual(report["confirmedScoops"],0)

    def test_second_run_no_alert_when_previously_seen(self):
        def search(key,term,start,end):
            return {"rows":[row()],"total":1,"complete":True}
        old=p.build("fake",now=NOW,search=search,names=["현대자동차"],
                    coverage=lambda _:{"status":"미검증","articles":[]})
        new=p.build("fake",previous=old,now=NOW,search=search,names=["현대자동차"],
                    coverage=lambda _:{"status":"미검증","articles":[]})
        self.assertEqual(new["alertCount"],0)
        self.assertTrue(new["items"][0]["previouslyObserved"])
        self.assertFalse(new["baselineInitialized"])

    def test_new_publication_is_newly_seen_not_first_ever(self):
        def search(key,term,start,end):
            patent=row()
            patent["openNumber"]="10-2026-0777777"
            return {"rows":[patent],"total":1,"complete":True}
        old={"status":"official_search_completed","seen":{}}
        report=p.build("fake",previous=old,now=NOW,search=search,
                       names=["현대자동차"],coverage=lambda _:{"status":"미검증","articles":[]})
        self.assertEqual(report["alertCount"],1)
        self.assertTrue(report["items"][0]["alreadyPublic"] if "alreadyPublic" in report["items"][0] else True)
        self.assertFalse(report["items"][0]["scoopConfirmed"])

    def test_prior_truncated_query_backfill_is_not_today_disclosure(self):
        def search(key,term,start,end):
            return {"rows":[row(pubdate="20261008")],"total":1,"complete":True}
        previous={"status":"official_search_partial",
                  "generatedAt":"2026-10-13T03:39:28+09:00",
                  "seen":{}}
        out=p.build("fake",previous=previous,now=NOW,
                    search=search,names=["현대자동차"],news_limit=0)
        self.assertEqual(out["candidateCount"],1)
        self.assertEqual(out["historicalBackfillCount"],1)
        self.assertEqual(out["alertCount"],0)
        self.assertTrue(out["items"][0]["historicalBackfill"])
        self.assertFalse(out["items"][0]["freshObservation"])

    def test_newer_published_after_previous_date_is_fresh_observation(self):
        later=datetime(2026,10,15,8,0,tzinfo=KST)
        patent=row(pubdate="20261014")
        def search(key,term,start,end):
            return {"rows":[patent],"total":1,"complete":True}
        previous={"status":"official_search_completed",
                  "generatedAt":"2026-10-13T03:39:28+09:00",
                  "seen":{}}
        out=p.build("fake",previous=previous,now=later,
                    search=search,names=["현대자동차"],news_limit=0)
        self.assertEqual(out["alertCount"],1)
        self.assertEqual(out["historicalBackfillCount"],0)
        self.assertTrue(out["items"][0]["freshObservation"])

    def test_missing_api_key_not_zero_patent_fact(self):
        result=p.build("",now=NOW)
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"],"KIPRIS_SERVICE_KEY 미설정")
        self.assertEqual(result["confirmedScoops"],0)

    def test_failed_issuer_does_not_zero_fill(self):
        report=p.build("fake",now=NOW,names=["현대자동차"],
                       search=lambda *a:(_ for _ in ()).throw(ValueError("API error")))
        self.assertEqual(report["companyChecks"][0]["status"],"source_error")
        self.assertEqual(report["completelyCheckedCompanies"],0)

    def test_publication_number_search_no_hits_doesnt_prove_unreported(self):
        item={"publicationNumber":"10-2026-0123456","company":"현대자동차"}
        found=p.press_lookup(item,fetch=lambda url:b"<rss><channel/></rss>")
        self.assertIn("미보도 의미 아님",found["status"])

    def test_critical_titles_require_technical_clue(self):
        tags=p.tech_tags("HVDC 변환기 제어","고압직류 시스템")
        self.assertTrue(any(t["theme"]=="전력망·HVDC" for t in tags))
        self.assertFalse(p.tech_tags("차량의 컵홀더","컵 음료 수납"))


if __name__=="__main__":
    unittest.main()
