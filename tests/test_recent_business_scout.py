"""Latest 2026 interim DART evidence; no cross-quarter or false scoops."""
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import recent_business_scout as scout
import business_content as bc

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,13,tzinfo=KST)
COMPANY="01205851"


def filing(name,number,day,company=COMPANY):
    return {"report_nm":name,"rcept_no":number,"rcept_dt":day,"corp_code":company}


def response(*rows):
    return {"status":"000","total_page":1,"list":list(rows)}


def example(period="06",year=2026,receipt="20260814000001"):
    return {"period":period,"periodLabel":"반기","year":year,
            "receiptNo":receipt,"published":receipt[:8],
            "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt}


def evidence(receipt):
    row={"topic":"investment","unit":"백만원","receiptNo":receipt,
         "context":"1) 진행중인 투자 (단위: 백만원)",
         "rows":[["신규 공장","24.05~27.06","생산능력확충","123,456"]]}
    return {"status":"found","document":"business.xml",
            "section":"mock"}


class InterimBusinessTests(unittest.TestCase):
    def test_select_latest_reporting_period_not_latest_amendment(self):
        rs=[example("09",2026,"20261115000111"),
            example("06",2026,"20261225000555")]
        self.assertEqual(scout.select_period(rs)["period"],"09")

    def test_2026_half_and_q1_are_parsed(self):
        def source(url):
            return response(
                filing("반기보고서 (2026.06)","20260814000001","20260814"),
                filing("분기보고서 (2026.03)","20260515000001","20260515"),
                filing("분기보고서 (2026.09)","20261115000002","20261115"))
        docs=scout.reports_for_year("key",COMPANY,2026,fetch=source,now=NOW)
        self.assertEqual([d["period"] for d in docs],["06","03"])

    def test_last_correction_for_same_quarter(self):
        def source(url):
            return response(
                filing("반기보고서 (2026.06)","20260814000001","20260814"),
                filing("[기재정정]반기보고서 (2026.06)","20260915000222","20260915"))
        latest=scout.select_period(scout.reports_for_year(
            "key",COMPANY,2026,fetch=source,now=NOW))
        self.assertEqual(latest["receiptNo"],"20260915000222")

    def test_other_company_never_cross_linked(self):
        def source(url):
            return response(filing("반기보고서 (2026.06)","20260814000001","20260814","00164742"))
        self.assertEqual(scout.reports_for_year("key",COMPANY,2026,fetch=source,now=NOW),[])

    def test_wrong_form_and_year_rejected(self):
        def source(url):
            return response(
                filing("사업보고서 (2026.12)","20261231000001","20261231"),
                filing("반기보고서 (2025.06)","20260814000001","20260814"),
                filing("분기보고서 (2026.06)","20260814000002","20260814"),
                filing("반기보고서 (2026.09)","20261114000001","20261114"))
        self.assertEqual(scout.reports_for_year("key",COMPANY,2026,fetch=source,now=NOW),[])

    def test_list_truncation_is_an_error(self):
        with self.assertRaises(ValueError):
            scout.reports_for_year("key",COMPANY,2026,
                                   fetch=lambda _:{"status":"000","total_page":2,"list":[]},now=NOW)

    def test_provider_error_is_not_zero_results(self):
        with self.assertRaises(RuntimeError):
            scout.reports_for_year("key",COMPANY,2026,
                                   fetch=lambda _:{"status":"800"},now=NOW)

    def test_matching_prior_only_same_month(self):
        records=[example("03",2025,"20250515000222")]
        self.assertIsNone(scout.matching_prior(records,"06"))

    def test_project_candidate_is_not_new_investment_claim(self):
        now="20260814000001";old="20250814000003"
        prior={"status":"evidence_found","receiptNo":old,
               "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+old,
               "tables":[]}
        current={"status":"evidence_found","receiptNo":now,
                 "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+now,
                 "tables":[{"topic":"investment","unit":"백만원","receiptNo":now,
                            "context":"진행중인 투자","rows":[["청주 신공장","2024~2027","118,473"]]}]}
        leads=scout.signals_from_company("엘에스일렉트릭",prior,current,"06")
        self.assertEqual(len(leads),1)
        self.assertIn("신규 투자 확정 아님",leads[0]["observation"])
        self.assertIn("단독 미확정",leads[0]["status"])
        self.assertFalse(leads[0]["priorExcerptContainsName"])

    def test_old_project_name_preserves_already_seen(self):
        code="20260814000001";doc={"status":"evidence_found","receiptNo":code,
            "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+code,
            "tables":[{"topic":"investment","unit":"백만원","receiptNo":code,
                       "context":"진행중인 투자","rows":[["변압기 공장","2024~2027","118,473"]]}]}
        leads=scout.signals_from_company("HD현대일렉트릭",doc,doc,"06")
        self.assertTrue(leads[0]["priorExcerptContainsName"])

    def test_title_rows_and_irrelevant_cells_ignored(self):
        t=[{"topic":"investment","rows":[["합계","12,345"],["사업부문","123"],
                                         ["설명만 있는 사업","검토 중"]],
            "receiptNo":"20260814000001"}]
        self.assertEqual(scout.project_rows(t),[])

    def test_no_matching_prior_leaves_unconfirmed(self):
        current=example()
        def listing(key,code,year):
            return [current] if year==2026 else [example("03",2025,"20250515000001")]
        r=scout.scan_company("HD현대일렉트릭",COMPANY,"key",2026,list_fetch=listing,
                             doc_fetch=lambda *args:self.fail("no unsupported document read"))
        self.assertEqual(r["status"],"prior_matching_interim_not_found")
        self.assertEqual(r["signals"],[])

    def test_source_errors_visible_not_zero_new_events(self):
        def bad(*args):raise RuntimeError("server unavailable")
        r=scout.scan_company("HD현대일렉트릭",COMPANY,"key",2026,list_fetch=bad)
        self.assertEqual(r["status"],"source_error")
        self.assertEqual(r["errorType"],"RuntimeError")

    def test_cache_reuses_only_verified_matching_receipts(self):
        current=example("06",2026,"20260814000001")
        prior=example("06",2025,"20250814000002")
        def listing(key,corp,year): return [current] if year==2026 else [prior]
        previous={
            "company":"HD현대일렉트릭","corpCode":COMPANY,
            "status":"official_sections_retrieved",
            "current":{**current,"status":"evidence_found","tables":[]},
            "priorSamePeriod":{**prior,"status":"evidence_found","tables":[]},
            "signals":[]}
        record=scout.scan_company("HD현대일렉트릭",COMPANY,"key",2026,
            list_fetch=listing,doc_fetch=lambda *args:self.fail("cached docs must not refetch"),
            cache_record=previous)
        self.assertTrue(record["cacheHit"])
        self.assertEqual(record["current"]["receiptNo"],current["receiptNo"])

    def test_new_correction_must_invalidate_cached_documents(self):
        current=example("06",2026,"20260915000008")
        prior=example("06",2025,"20250814000002")
        oldcache={
            "company":"HD현대일렉트릭","corpCode":COMPANY,
            "status":"official_sections_retrieved",
            "current":{**example(),"status":"evidence_found","tables":[]},
            "priorSamePeriod":{**prior,"status":"evidence_found","tables":[]},
            "signals":[]}
        called=[]
        def get_doc(key,receipt):
            called.append(receipt)
            return {"status":"found","section":"<SECTION-1></SECTION-1>","document":"test.xml"}
        with patch.object(scout,"evidence_tables",return_value=[{"topic":"investment","unit":"백만원",
          "receiptNo":"20260915000008","context":"진행중인 투자","rows":[["변압기 공장","2025","50"]]}]):
            record=scout.scan_company("HD현대일렉트릭",COMPANY,"key",2026,
                list_fetch=lambda k,c,y:[current] if y==2026 else [prior],
                doc_fetch=get_doc,cache_record=oldcache)
        self.assertFalse(record.get("cacheHit",False))
        self.assertEqual(len(called),2)

    def test_only_direct_beat_corp_code(self):
        report=scout.source_report(
            {"삼성전기":{"corp_code":"00126371"}},
            "key",2026,names=("HD현대일렉트릭",),
            scan=lambda *a:self.fail("unexpected company"))
        self.assertEqual(report["companies"][0]["status"],"corp_code_unavailable")
        self.assertEqual(report["scoopCountConfirmed"],0)

    def test_news_only_tracked_one_per_company(self):
        signals=[{"company":"HD현대일렉트릭","topic":"investment","project":"청주 신공장",
                  "coverage":{"status":"미검색"}}]
        data={"businessYear":2026,"companies":[{"company":"HD현대일렉트릭",
            "status":"official_sections_retrieved","signals":signals*3}]}
        calls=[]
        def fake(query):
            calls.append(query)
            return {"status":"검색상 미발견: 단독 여부 판단 불가","articles":[]}
        scout.enrich_coverage(data,lookup=fake)
        self.assertEqual(len(calls),1)
        self.assertIn("단독",data["companies"][0]["signals"][0]["coverage"]["decision"])

    def test_no_false_negative_when_blank_rss(self):
        signal={"company":"현대자동차","topic":"investment","project":"해외 공장",
                "coverage":{"status":"미검색"}}
        data={"businessYear":2026,"companies":[{"company":"현대자동차",
            "status":"official_sections_retrieved","signals":[signal]}]}
        scout.enrich_coverage(data,lookup=lambda _:{"status":"검색상 미발견: 단독 여부 판단 불가","articles":[]})
        self.assertNotIn("단독 확정",str(data))


if __name__=="__main__":
    unittest.main()
