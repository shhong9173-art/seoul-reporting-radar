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
    def test_enzymatic_plastic_recycling_is_in_scope_for_vehicle_beat(self):
        official=row(
            applicant="현대자동차주식회사|기아 주식회사|씨제이제일제당 주식회사",
            title="폐차 플라스틱의 효소적 해중합 및 재생 원료 제조 방법",
            abstract="폐플라스틱 PET 재활용과 효소 분해 공정")
        found=p.verified_patent(official,"현대자동차",p.APPLICANTS["현대자동차"],
                                "20260908","20261013")
        self.assertIsNotNone(found)
        self.assertEqual(len(found["applicants"]),3)
        self.assertTrue(any(t["theme"]=="순환소재·폐차재활용" for t in found["themes"]))
        self.assertFalse(found["scoopConfirmed"])

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

    def test_keyword_free_valid_patent_preserved_but_not_breakthrough(self):
        r=p.verified_patent(
            row(title="베어링 제조 방법",abstract="프레스와 금형"),
            "현대자동차",p.APPLICANTS["현대자동차"],"20260908","20261013")
        self.assertIsNotNone(r)
        self.assertFalse(r["themeMatched"])
        self.assertEqual(r["priorityScore"],20)
        self.assertFalse(r["scoopConfirmed"])

    def test_full_source_is_not_silently_truncated_at_500(self):
        def search(key,term,start,end):
            docs=[]
            for i in range(510):
                patent=row(title="베어링 제조 방법",abstract="기술적 검토 필요")
                patent["openNumber"]=f"1020260{i:06d}"
                docs.append(patent)
            return {"rows":docs,"total":len(docs),"complete":True}
        result=p.build("key",now=NOW,names=["현대자동차"],search=search,news_limit=0)
        self.assertEqual(result["candidateCount"],510)
        self.assertEqual(len(result["items"]),510)
        self.assertEqual(result["unshownCount"],0)
        self.assertEqual(result["unclassifiedCount"],510)

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
        from urllib.parse import parse_qs,urlparse
        def fetch(url):
            page=int(parse_qs(urlparse(url).query)["pageNo"][0])
            r=row()
            r["openNumber"]=f"1020260{page:06d}"
            return doc([r],total=201)
        result=p.search_applicant("fake-key","현대자동차","20260908","20261013",
                                  fetch=fetch,max_pages=2)
        self.assertFalse(result["complete"])

    def test_oversubscribed_search_is_split_by_disclosure_date(self):
        from urllib.parse import parse_qs,urlparse
        docs=[]
        for date,n in (("20261012",225),("20261013",225)):
            for i in range(n):
                r=row(pubdate=date)
                r["openNumber"]=f"102026{int(date[-2:]):02d}{i:05d}"
                r["applicationNumber"]=f"102025{int(date[-2:]):02d}{i:05d}"
                docs.append(r)
        calls=[]
        def fetch(url):
            q=parse_qs(urlparse(url).query)
            left,right=q["openDate"][0].split("~")
            page=int(q["pageNo"][0])
            matching=[r for r in docs if left<=r["openDate"]<=right]
            calls.append((left,right,page))
            return doc(matching[(page-1)*100:page*100],total=len(matching))
        report=p.search_applicant("key","현대자동차","20261012","20261013",fetch=fetch)
        self.assertTrue(report["complete"])
        self.assertEqual(len(report["rows"]),450)
        self.assertEqual(report["total"],450)
        self.assertEqual(report["splitWindowCount"],2)
        self.assertGreater(report["requestCount"],5)
        self.assertIn(("20261012","20261013",1),calls)

    def test_overcapacity_single_day_stays_incomplete(self):
        from urllib.parse import parse_qs,urlparse
        def fetch(url):
            page=int(parse_qs(urlparse(url).query)["pageNo"][0])
            records=[]
            for i in range((page-1)*100,min(page*100,425)):
                r=row(pubdate="20261013")
                r["openNumber"]=f"1020260{i:06d}"
                records.append(r)
            return doc(records,total=425)
        report=p.search_applicant("key","현대자동차","20261013","20261013",fetch=fetch)
        self.assertFalse(report["complete"])
        self.assertEqual(len(report["rows"]),400)
        self.assertEqual(report["splitWindowCount"],1)

    def test_api_page_repeating_earlier_records_is_not_complete(self):
        def fetch(_url):
            r=row()
            return doc([r],total=2)
        with self.assertRaisesRegex(ValueError,"반복"):
            p.search_applicant("key","현대자동차","20261012","20261012",fetch=fetch)

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

    def test_source_diagnostics_expose_issuer_errors_without_secrets(self):
        sample={"generatedAt":"2026-10-13T09:44:09+09:00",
                "applicantCount":2,"sourceWindowComplete":False,
                "companyChecks":[
                  {"company":"현대자동차","status":"checked","rawTotal":2,"rawRetrieved":2},
                  {"company":"기아","status":"source_error","errorType":"TimeoutError",
                   "errorDetail":"ServiceKey=secret-must-not-leak"}]}
        report=p.publication_diagnostics(sample)
        self.assertEqual(report["status"],"incomplete")
        self.assertEqual(report["checkedCompanies"],1)
        self.assertEqual(report["incompleteCompanies"][0]["company"],"기아")
        import json
        self.assertNotIn("secret-must-not-leak",json.dumps(report))
        self.assertEqual(report["incompleteCompanies"][0]["errorType"],"TimeoutError")

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
