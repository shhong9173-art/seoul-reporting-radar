"""DART official table + dated news index cannot establish exclusivity by itself."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import dart_specific_media as d
ROOT=Path(__file__).resolve().parents[1]


def official(company="대한전선",receipt="20261015800054"):
    return {"corpName":company,"receiptNo":receipt,
        "url":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt}

def monitor(filing):
    return {"status":"industry_beat_official_receipt_review","records":[{
        "company":filing["corpName"],"receiptNo":filing["receiptNo"],
        "sourceUrl":filing["url"],"isCorrection":False,
        "status":"official_document_read",
        "documentFieldExtractionStatus":"official_table_terms_not_business_effect",
        "observedFields":{"contract_subject":"북미 초고압 케이블 납품의 건",
                          "contract_amount":"116,810,902,865"},
        "observedFieldEvidence":{
            "contract_subject":{"basis":"same_official_table_row"},
            "contract_amount":{"basis":"same_official_table_row"}}
    }]}

class PrecisionMediaTests(unittest.TestCase):
    def test_actual_dart_monitor_contract_is_precise_evidence(self):
        f=official()
        snapshot=json.loads((ROOT/"digests/dart_beat_monitor_latest.json").read_text(encoding="utf-8"))
        if any(r.get("receiptNo")==f["receiptNo"] for r in snapshot.get("records",[])):
            e=d.exact_contract_evidence(f,snapshot)
            self.assertEqual(e["amountWon"],116_810_902_865)
            self.assertEqual(e["contractSubject"],"북미 초고압 케이블 납품의 건")
            self.assertFalse(e["sameContractMediaFulltextVerified"])

    def test_specific_queries_resolve_the_already_reported_2026_contract(self):
        e=d.exact_contract_evidence(official(),monitor(official()))
        self.assertEqual(d.precise_press_queries(e)[0],
            '"대한전선" "북미 초고압 케이블"')
        article="대한전선 수주공시 - 북미 초고압 케이블 납품의 건 1,168.1억원 (매출액대비 3.21 %)"
        self.assertTrue(d.likely_same_contract_indexed(e,article))
        self.assertTrue(d.likely_same_contract_indexed(e,
            "대한전선, 북미 초고압 케이블 공급계약 1168억1090만원"))
        self.assertFalse(e["sameContractMediaFulltextVerified"])

    def test_two_similar_but_unrelated_contracts_do_not_match(self):
        e=d.exact_contract_evidence(official(),monitor(official()))
        for article in (
            "대한전선, 신규 초고압 케이블 계약 2000억원",
            "대한전선, 동남아 케이블 공급계약 1168억원",
            "포스코, 북미 초고압 케이블 납품의 건 1,168억원",
            "대한전선, 북미 케이블 납품 1168억원",
            "대한전선, 북미 초고압 케이블 시장 진출 논의",
        ):
            self.assertFalse(d.likely_same_contract_indexed(e,article),article)

    def test_no_inference_from_wrong_company_or_unverified_table(self):
        f=official()
        other=monitor(f);other["records"][0]["company"]="대한전선 외 회사"
        self.assertIsNone(d.exact_contract_evidence(f,other))
        other=monitor(f)
        other["records"][0]["observedFieldEvidence"]["contract_amount"]["basis"]="inferred"
        self.assertIsNone(d.exact_contract_evidence(f,other))
        other=monitor(f);other["records"][0]["sourceUrl"]="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261015800055"
        self.assertIsNone(d.exact_contract_evidence(f,other))
        other=monitor(f);other["records"][0]["isCorrection"]=True
        self.assertIsNone(d.exact_contract_evidence(f,other))
        self.assertIsNone(d.exact_contract_evidence(f,{"status":"partial","records":[]}))

    def test_no_media_proof_fabricated_by_scoop_scout(self):
        src=(ROOT/"scoop_scout.py").read_text(encoding="utf-8")
        self.assertIn("contractIndexEvidence",src)
        self.assertIn("precise_press_queries(evidence)",src)
        self.assertIn("likely_same_contract_indexed",src)
        self.assertIn("기사 전문은 아직 별도 대조",src)

if __name__=="__main__":
    unittest.main()
