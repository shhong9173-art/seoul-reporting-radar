"""Official source scope and high-precision contract/permit identity tests."""
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import overseas_official as overseas
import recent_contracts as dart
import recent_business_scout as interim

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,13,tzinfo=KST)
CORP="00145880"
NO="20261012000123"
ORIGINAL="20260814000234"


class OfficialSourceTests(unittest.TestCase):
    def test_federal_notice_title_evidence_not_permit(self):
        record={"document_number":"2026-12345",
                "title":"Hyundai Motor: Environmental impact statement",
                "abstract":"Notice of public comment",
                "publication_date":"2026-10-12",
                "html_url":"https://www.federalregister.gov/documents/2026/10/12/2026-12345/example"}
        ans=overseas.federal_register("Hyundai Motor","2026-09-13",
                        fetch=lambda req:{"results":[record],"count":1})
        self.assertEqual(ans["items"][0]["companiesMentioned"],["현대자동차"])
        self.assertTrue(ans["items"][0]["nameVerified"])
        self.assertIn("미확인",ans["items"][0]["notProven"])
        self.assertNotIn("허가 확정",ans["items"][0]["exclusiveStatus"])

    def test_no_inference_from_fulltext_only(self):
        r={"document_number":"2026-12345","title":"Generic energy policy",
           "abstract":"Discussion of regulations","publication_date":"2026-10-12",
           "html_url":"https://www.federalregister.gov/documents/2026/10/12/2026-12345/energy"}
        ans=overseas.federal_register("Hyundai Motor","2026-09-13",fetch=lambda req:{"results":[r]})
        self.assertEqual(len(ans["items"]),1)
        self.assertFalse(ans["items"][0]["nameVerified"])
        self.assertEqual(ans["items"][0]["companiesMentioned"],[])
        self.assertIn("원문에서 확인하지 못함",ans["items"][0]["evidence"])

    def test_short_substring_is_not_company(self):
        self.assertEqual(overseas.match_company("Kia Motors wins?"),["기아"])
        self.assertEqual(overseas.match_company("Hyundai Motorsports"),[])
        self.assertEqual(overseas.match_company("Doosan Enerbility JV"),["두산에너빌리티"])

    def test_ted_actual_notice_title_and_link(self):
        notice={"publication-number":"778811-2026",
                "notice-title":{"eng":["Transformers from HD Hyundai Electric"]},
                "buyer-name":{"eng":["City of Paris"]},
                "publication-date":"2026-10-12","notice-type":"cn-standard"}
        ans=overseas.ted_procurement("HD Hyundai Electric","2026-09-13",
            fetch=lambda req:{"notices":[notice],"timedOut":False,"totalNoticeCount":1})
        self.assertEqual(len(ans["items"]),1)
        self.assertTrue(ans["items"][0]["nameVerified"])
        self.assertEqual(ans["items"][0]["sourceUrl"],
                         "https://ted.europa.eu/en/notice/778811-2026/html")
        self.assertIn("낙찰",ans["items"][0]["notProven"])

    def test_ted_body_only_mentions_not_asserted(self):
        notice={"publication-number":"778811-2026",
                "notice-title":{"deu":["Neue Transformatoren"]},
                "buyer-name":{"eng":["Utility Stadtwerke"]},
                "publication-date":"2026-10-12"}
        ans=overseas.ted_procurement("Hyosung Heavy Industries","2026-09-13",
            fetch=lambda req:{"notices":[notice]})
        self.assertEqual(len(ans["items"]),1)
        self.assertFalse(ans["items"][0]["nameVerified"])
        self.assertEqual(ans["items"][0]["companiesMentioned"],[])
        self.assertIn("확인 전",ans["items"][0]["evidence"])

    def test_ted_timeout_not_no_match(self):
        with self.assertRaises(ValueError):
            overseas.ted_procurement("Hyundai Motor","2026-09-13",
                fetch=lambda req:{"notices":[],"timedOut":True})

    def test_partial_sources_show_error_not_zero(self):
        checked=overseas.collect(now=NOW,
            fr=lambda q,d:{"items":[],"returned":1},
            ted=lambda q,d:(_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(checked["sourceErrors"],4)
        self.assertEqual(checked["matchedCount"],0)
        self.assertTrue(any(c["status"]=="source_error" for c in checked["checks"]))
        self.assertEqual(checked["scoopConfirmed"],0)

    def test_invalid_external_document_number_no_link(self):
        rec={"document_number":"bad","title":"Hyundai Motor",
             "abstract":"","publication_date":"2026-10-12",
             "html_url":"https://malicious.test/doc"}
        result=overseas.federal_register("Hyundai Motor","2026-09-13",
                fetch=lambda r:{"results":[rec]})
        self.assertFalse(result["items"])


class DartContractTests(unittest.TestCase):
    def row(self,name="단일판매ㆍ공급계약체결",company=CORP):
        return {"corp_code":company,"rcept_no":NO,
                "rcept_dt":"20261012","report_nm":name}

    def test_company_and_contract_events_exact(self):
        result=dart.company_filings("key","현대제철",CORP,"20260922","20261013",
                 fetch=lambda u:{"status":"000","list":[self.row()]})
        self.assertEqual(result[0]["category"],"공급계약")
        self.assertFalse(result[0]["isCorrection"])

    def test_unrelated_report_and_issuer_do_not_enter(self):
        rows=[self.row("대표이사변경"),self.row(company="99999999")]
        result=dart.company_filings("key","현대제철",CORP,"20260922","20261013",
                 fetch=lambda u:{"status":"000","list":rows})
        self.assertEqual(result,[])

    def test_unpaginated_list_must_fail(self):
        with self.assertRaises(ValueError):
            dart.company_filings("key","현대제철",CORP,"20260922","20261013",
                        fetch=lambda u:{"status":"000","total_page":3,"list":[]})

    def test_unrelated_company_is_blocked(self):
        with self.assertRaises(ValueError):
            dart.company_filings("key","삼성전기",CORP,"20260922","20261013")

    def test_correction_unverified_original_has_no_changes(self):
        item={"company":"현대제철","corpCode":CORP,"receiptNo":NO,
              "report":"[기재정정]단일판매ㆍ공급계약체결","isCorrection":True}
        result=dart.document_evidence(item,"key",
             lineage=lambda row,codes,api_key:{
                 "originalDocumentVerified":False,"status":"original_unverified",
                 "reason":"원공시 접수번호 없음",
                 "candidateOrigins":[{"receiptNo":ORIGINAL}]})
        self.assertEqual(result["changes"],[])
        self.assertEqual(result["status"],"original_not_verified")
        self.assertIsNone(result["originalReceiptNo"])

    def test_correction_original_explicit_checked(self):
        item={"company":"현대제철","corpCode":CORP,"receiptNo":NO,
              "report":"[기재정정]단일판매ㆍ공급계약체결","isCorrection":True}
        result=dart.document_evidence(item,"key",
             lineage=lambda row,codes,api_key:{
                 "originalDocumentVerified":True,"status":"original_verified_changes",
                 "originReceiptNo":ORIGINAL,
                 "originSourceUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+ORIGINAL,
                 "changes":[{"field":"contract_amount","before":"120","after":"150"}],
                 "reason":"공식 원문 확인"})
        self.assertEqual(result["changes"][0]["after"],"150")
        self.assertEqual(result["originalReceiptNo"],ORIGINAL)
        self.assertIn("단독 미확정",result["scoopStatus"])

    def test_new_listing_not_a_confirmed_contract_without_document(self):
        item={"company":"현대제철","corpCode":CORP,"receiptNo":NO,
              "report":"단일판매ㆍ공급계약체결","isCorrection":False}
        ans=dart.document_evidence(item,"key",
           documents=lambda *args:(_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(ans["status"],"document_unavailable")
        self.assertNotIn("observedFields",ans)

    def test_no_false_scoop_with_zero_events(self):
        codes={"현대제철":{"corp_code":CORP}}
        def empty(key,company,corp,start,end):
            self.assertLessEqual(start,end)
            return []
        result=dart.collect(codes,"key",now=NOW,fetch=empty)
        self.assertEqual(result["totalMatchingListEvents"],0)
        self.assertEqual(result["scoopConfirmed"],0)
        self.assertTrue(any(x["status"]=="checked" for x in result["sourceChecks"]))

    def test_latest_corrections_prioritized(self):
        codes={"현대제철":{"corp_code":CORP}}
        def listing(key,company,corp,start,end):
            return ([{"company":company,"corpCode":corp,"published":"20261011",
                      "report":"단일판매ㆍ공급계약체결","receiptNo":"20261011000123",
                      "isCorrection":False},
                     {"company":company,"corpCode":corp,"published":"20261010",
                      "report":"[기재정정]단일판매ㆍ공급계약체결","receiptNo":"20261010000123",
                      "isCorrection":True}] if company=="현대제철" else [])
        result=dart.collect(codes,"key",now=NOW,fetch=listing,
                            detail=lambda x,k:{**x,"status":"not_checked"},limit=1)
        self.assertTrue(result["items"][0]["isCorrection"])
        self.assertFalse(result["allEventsInspected"])


class InvestmentNoiseTests(unittest.TestCase):
    def test_bogus_project_dates_and_generic_subsidiaries_filtered(self):
        rows=[["2025년 7월~2028년 6월","100","300"],
              ["해외법인外","100","300"],
              ["미래 성장동력 확보 및중장기 탄소저감 체제 전환","100","300"],
              ["미국공장","100","300"],
              ["청주 배전캠퍼스 신축(*)","100","300"],
              ["변압기 철심공장","200","300"]]
        found=interim.project_rows([{"topic":"investment","receiptNo":NO,"rows":rows}])
        self.assertEqual([x["name"] for x in found],
                         ["청주 배전캠퍼스 신축(*)","변압기 철심공장"])


if __name__=="__main__":
    unittest.main()
