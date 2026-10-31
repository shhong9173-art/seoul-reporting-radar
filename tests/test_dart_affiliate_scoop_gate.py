"""Primary-file replay: avoid confusing in-group contracts with new clients."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from dart_affiliate_scoop_gate import review_hold,exact_dart_source
ROOT=Path(__file__).resolve().parents[1]


def entry(receipt,company,report):
    return {"corpName":company,"receiptNo":receipt,"reportName":report,
            "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt}


def monitor_for(r,relation="자회사"):
    return {"status":"industry_beat_official_receipt_review","records":[{
        "company":r["corpName"],"receiptNo":r["receiptNo"],"sourceUrl":r["url"],
        "status":"official_document_read","detailStatus":"official_document_read",
        "isCorrection":False,"documentFieldExtractionStatus":"official_table_terms_not_business_effect",
        "observedFields":{
            "counterparty":"TAIHAN ELECTRIC USA LTD.",
            "counterparty_relationship":relation},
        "observedFieldEvidence":{"counterparty_relationship":{
            "sourceLabel":"- 회사와의 관계","basis":"same_official_table_row"}}
    }]}


class DARTAffiliateGate(unittest.TestCase):
    def test_actual_production_dart_documents_are_not_external_scoops(self):
        dart=json.loads((ROOT/"dart.json").read_text(encoding="utf-8"))
        monitor=json.loads((ROOT/"digests/dart_beat_monitor_latest.json").read_text(encoding="utf-8"))
        current={str(x.get("receiptNo")):x for x in dart.get("items",[])}
        # The live DART window rolls forward; production replay is conditional.
        # Historical fixed document facts are tested independently below.
        if "20261016000056" in current:
            equity=review_hold(current["20261016000056"],monitor)
            self.assertEqual(equity["reason"],"related_party_equity_not_new_external_business")
        if ("20261015800054" in current and
            any(x.get("receiptNo")=="20261015800054"
                for x in monitor.get("records",[]))):
            contract=review_hold(current["20261015800054"],monitor)
            self.assertEqual(contract["reason"],"official_contract_counterparty_is_affiliate")
            self.assertIn("TAIHAN ELECTRIC USA LTD.",contract["whatVerified"])
            self.assertIn("신규 외부",contract["notVerified"])

    def test_real_intragroup_relationship_requires_exact_filing_identity(self):
        source=entry("20261015800054","대한전선","단일판매ㆍ공급계약체결")
        self.assertEqual(review_hold(source,monitor_for(source))["reason"],
                         "official_contract_counterparty_is_affiliate")
        forged=monitor_for(source)
        forged["records"][0]["company"]="가짜주식회사"
        self.assertIsNone(review_hold(source,forged))
        forged=monitor_for(source)
        forged["records"][0]["sourceUrl"]="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800055"
        self.assertIsNone(review_hold(source,forged))
        forged=monitor_for(source)
        forged["records"][0]["observedFieldEvidence"]["counterparty_relationship"]["basis"]="infer_from_company_name"
        self.assertIsNone(review_hold(source,forged))

    def test_external_customer_or_unknown_relationship_not_suppressed(self):
        contract=entry("20261015800054","대한전선","단일판매ㆍ공급계약체결")
        self.assertIsNone(review_hold(contract,monitor_for(contract,"외부고객")))
        self.assertIsNone(review_hold(contract,{"status":"degraded","records":[]}))
        self.assertIsNone(review_hold(contract,None))
        self.assertIsNone(review_hold(entry("20261015800055","대한전선","단일판매ㆍ공급계약체결"),
                                      monitor_for(contract)))

    def test_actual_korea_zinc_intragroup_goods_services_change(self):
        d=json.loads((ROOT/"dart.json").read_text(encoding="utf-8"))
        matching=[x for x in d.get("items",[])
                  if x.get("receiptNo")=="20261014000138"]
        if matching:
            hold=review_hold(matching[0],None)
            self.assertIsNotNone(hold)
            self.assertEqual(hold["reason"],
                "related_party_goods_services_change_not_external_customer")
            self.assertIn("공시 접수",hold["whatVerified"])
            self.assertIn("신규",hold["notVerified"])
        r=entry("20261014000138","고려아연",
            "동일인등출자계열회사와의상품ㆍ용역거래변경")
        hold=review_hold(r,None)
        self.assertIsNotNone(hold)
        self.assertEqual(hold["reason"],
            "related_party_goods_services_change_not_external_customer")

    def test_related_party_notice_does_not_hide_material_nonrelated_contracts(self):
        # 처음 공시도 같은 계열사 간 거래 양식이라 보류(10-31 운영: GS칼텍스 매출 대비 0.02~0.03%가 '단독 유력' 87점)
        r=entry("20261014000138","고려아연",
            "동일인등출자계열회사와의상품ㆍ용역거래")
        hold=review_hold(r,None)
        self.assertEqual(hold["reason"],"related_party_goods_services_change_not_external_customer")
        self.assertEqual(hold["whatVerified"],"동일인 등 출자계열회사와의 상품·용역거래 공시 접수")
        r["reportName"]="주요사항보고서(신규시설투자)"
        self.assertIsNone(review_hold(r,None))
        r["reportName"]="동일인등출자계열회사와의상품ㆍ용역거래변경"
        r["url"]="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261014000139"
        self.assertIsNone(review_hold(r,None))

    def test_unrelated_material_equity_not_blocked(self):
        r=entry("20261016000056","한화솔루션","신규시설투자")
        self.assertIsNone(review_hold(r,None))
        r["reportName"]="특수관계인에 대한 출자"
        self.assertEqual(review_hold(r,None)["reason"],
                         "related_party_equity_not_new_external_business")

    def test_dart_url_host_and_receipt_require_exact_match(self):
        self.assertTrue(exact_dart_source("20261015800054",
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800054"))
        for u in [
            "https://dart.fss.or.kr.evil.test/dsaf001/main.do?rcpNo=20261015800054",
            "https://evil.test/dsaf001/main.do?rcpNo=20261015800054",
            "javascript:evil()",
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800055",
            "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800054&x=y",
        ]:
            self.assertFalse(exact_dart_source("20261015800054",u))

    def test_held_sources_not_promoted_by_scoop_radar(self):
        script=(ROOT/"scoop_scout.py").read_text(encoding="utf-8")
        self.assertIn("hold=review_hold(d,monitor)",script)
        self.assertIn('dart_suppression[category]+=1',script)
        self.assertIn('"classification":"source_review_only_not_a_scoop"',script)
        self.assertIn('"externalNewCustomerVerified":False',script)
        self.assertLess(script.index("hold=review_hold(d,monitor)"),
                        script.index('primary.append({\n            "category":"공시"'))

if __name__=="__main__":
    unittest.main()
