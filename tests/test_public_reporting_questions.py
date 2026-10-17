"""Prevent press-office question generation about undisclosed internal plans."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from public_reporting_questions import (
    QUESTIONS,LEAD_QUESTIONS,DEFAULT,public_questions,public_lead_questions,
    validate_public_policy,
)
ROOT=Path(__file__).resolve().parents[1]

class PressOfficePublicQuestions(unittest.TestCase):
    def test_question_policy_exclusively_public_records_and_confirmable_facts(self):
        self.assertTrue(validate_public_policy())
        for kind in QUESTIONS:
            arr=public_questions(kind)
            self.assertEqual(len(arr),3)
            self.assertTrue(all(q.endswith("?") for q in arr))
        for kind in LEAD_QUESTIONS:
            arr=public_lead_questions(kind)
            self.assertGreaterEqual(len(arr),2)
            self.assertTrue(all(q.endswith("?") for q in arr))

    def test_specific_contract_patent_recall_questions_avoid_private_strategy(self):
        contract=" ".join(public_questions("계약·수주"))
        patent=" ".join(public_questions("특허·기술"))
        recall=" ".join(public_questions("결함·리콜"))
        self.assertIn("계열사 관계",contract)
        self.assertIn("독립청구항",patent)
        self.assertIn("시정조치",recall)
        forbidden=("생산 계획","조달 계획","공급망 변경","수출 물량 재배치",
                   "양산·상용화 계획","어떤 대응을 준비",
                   "물량·기간·단가와 실제 생산능력 투입")
        for question in list(QUESTIONS.values())+list(LEAD_QUESTIONS.values())+[DEFAULT]:
            content=" ".join(question)
            for word in forbidden:self.assertNotIn(word,content)

    def test_public_dart_receipt_only_if_exactly_verified_format(self):
        first=public_questions("계약·수주",{"receiptNo":"20261015800054"})[0]
        self.assertTrue(first.startswith("DART 20261015800054 · "))
        for raw in ("not_a_receipt","20261015800054<script>","2026101580005",
                    "202610158000540","https://example.test/private"):
            self.assertNotIn("DART ",public_questions("계약·수주",{"receiptNo":raw})[0])

    def test_scout_uses_same_public_policy_for_leads_and_candidates(self):
        src=(ROOT/"scoop_scout.py").read_text(encoding="utf-8")
        self.assertIn("questions=public_questions(kind,x)",src)
        self.assertIn('questions=public_lead_questions(row["kind"])',src)
        self.assertIn('"publicAnswerableQuestionsOnly":True',src)
        self.assertIn('"internalFutureStrategyRequested":False',src)
        self.assertIn("validate_public_policy()",src)

if __name__=="__main__":
    unittest.main()
