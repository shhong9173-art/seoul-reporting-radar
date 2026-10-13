import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_cross_evidence as x
import patent_public_factcheck as e

NOW=datetime(2026,10,13,14,tzinfo=timezone(timedelta(hours=9)))
PUB="1020260145560"
def samples():
    lead={"publicationNumber":PUB,"coveredCompanies":["현대제철"],
          "title":"상변태 기반 판재 냉각 제어 장치",
          "sourceAbstractExcerpt":"판재 상변태 제어 및 냉각수 공급량 조절",
          "topic":"제조공정·자동화",
          "mediaReview":{"checked":True},"retrospectiveKnownCase":False,
          "cautionFlags":[]}
    desk={"status":"research_priorities_only",
          "generatedAt":"2026-10-13T13:59:00+09:00","reviewQueue":[lead],
          "shortlist":[{"publicationNumber":PUB}]}
    dart={"generatedAt":"2026-10-13T12:00:00+09:00",
          "companies":[{"company":"현대제철","status":"official_sections_retrieved",
             "current":{"receiptNo":"20260814003228","published":"20260814",
                        "tables":[{"topic":"productionCapacity",
                                   "rows":[["상변태 기반 냉각 설비","1식"],["조강","150톤"]]}]}},
             {"company":"기아","status":"official_sections_retrieved",
              "current":{"receiptNo":"20260814003229","published":"20260814",
                         "tables":[{"topic":"productionCapacity","rows":[["상변태 냉각","2식"]]}]}}]}
    contracts={"generatedAt":"2026-10-13T12:31:00+09:00","items":[
        {"company":"현대제철","receiptNo":"20261001000000","published":"20261001",
         "report":"시설투자 신규(일반 항목)"}]}
    delta={"generatedAt":"2026-10-13T13:00:00+09:00","investigations":[]}
    ledger={"schemaVersion":1,"checks":[]}
    return desk,dart,contracts,delta,ledger


class EvidenceTests(unittest.TestCase):
    def test_same_company_and_technical_phrase_is_lead_not_project_proof(self):
        p=x.evaluate(*samples(),now=NOW)
        row=p["prioritized"][0]
        self.assertEqual(len(row["independentDartTechnicalOverlap"]),1)
        self.assertIn("상변태",row["independentDartTechnicalOverlap"][0]["technicalTermsShared"])
        self.assertEqual(row["stage"],"cross_document_context_needs_company_confirmation")
        self.assertFalse(row["specificProjectLinkVerified"])
        self.assertFalse(row["approvedForPublication"])
        self.assertEqual(p["approvedArticles"],0)

    def test_other_company_same_term_never_links(self):
        args=list(samples())
        args[1]["companies"][0]["current"]["tables"]=[{"rows":[["봉형강","10톤"]]}]
        p=x.evaluate(*args,now=NOW)
        self.assertEqual(p["prioritized"][0]["independentDartTechnicalOverlap"],[])
        self.assertEqual(p["prioritized"][0]["stage"],"patent_only_no_project_identity")

    def test_no_generic_keyword_battery_false_link(self):
        args=list(samples())
        args[1]["companies"][0]["current"]["tables"]=[{"rows":[["냉각 공정","8"]]}]
        p=x.evaluate(*args,now=NOW)
        self.assertEqual(p["candidateWithSpecificTermOverlap"],0)

    def test_empty_sources_do_not_invent_projects(self):
        desk,*_=samples()
        p=x.evaluate(desk,{}, {},{}, {"checks":[]})
        self.assertEqual(p["candidateWithSpecificTermOverlap"],0)
        self.assertFalse(p["inputAvailability"]["dartBusiness"])

    def test_only_exact_company_alias_not_subsidiary_inference(self):
        self.assertEqual(x.issuer("현대제철 주식회사"),"현대제철")
        self.assertEqual(x.issuer("현대제철미국법인"),"")
        self.assertEqual(x.issuer("엘에스일렉트릭"),"LS일렉트릭")
        self.assertEqual(x.issuer("엘에스전선"),"LS전선")

    def test_latest_public_check_and_history_append_preserved(self):
        args=list(samples())
        args[4]["checks"]=[
            {"publicationNumber":PUB,"checkType":"company_response","result":"needs_check"},
            {"publicationNumber":PUB,"checkType":"company_response","result":"verified_public",
             "evidenceUrl":"https://example.org/press"},
        ]
        p=x.evaluate(*args,now=NOW)
        r=p["reviews"][0]
        self.assertEqual(r["humanPublicCheckStatuses"]["company_response"],"verified_public")
        self.assertFalse(r["approvedForPublication"])
        self.assertIn("actual_application",r["missingVerification"])

    def test_public_checks_require_url_and_authenticated_actor(self):
        d,*_=samples()
        with self.assertRaisesRegex(ValueError,"URL"):
            e.append_event({"checks":[]},d,PUB,"company_response","verified_public","","reporter")
        with self.assertRaises(ValueError):
            e.append_event({"checks":[]},d,PUB,"company_response","verified_public",
                           "http://example.org/press","reporter")
        with self.assertRaises(ValueError):
            e.append_event({"checks":[]},d,PUB,"company_response","needs_check","","bad actor")

    def test_no_private_note_fields_ever_written(self):
        d,*_=samples()
        row,event=e.append_event({"checks":[]},d,PUB,"prior_coverage","verified_public",
                                 "https://example.org/press","reporter",NOW)
        self.assertEqual(len(row["checks"]),1)
        self.assertEqual(event["reviewer"],"reporter")
        self.assertNotIn("note",event)
        self.assertNotIn("sourceName",event)
        self.assertFalse(x.evaluate(d,{},{},{},row)["reviews"][0]["confirmedExclusive"])

    def test_disproved_application_blocks_reporting(self):
        args=list(samples())
        args[4]["checks"]=[
            {"publicationNumber":PUB,"checkType":"actual_application","result":"contradicted_public"}
        ]
        p=x.evaluate(*args,now=NOW)
        self.assertEqual(p["reviews"][0]["stage"],"hold_claim_disproved")

    def test_no_unofficial_number_and_missing_desk_fails_closed(self):
        args=list(samples())
        args[0]["status"]="unverified"
        with self.assertRaises(ValueError):x.evaluate(*args,now=NOW)
        d,*_=samples()
        with self.assertRaises(ValueError):
            e.append_event({"checks":[]},d,"1020250123456","needs_check","needs_check","","reporter")


if __name__=="__main__":unittest.main()
