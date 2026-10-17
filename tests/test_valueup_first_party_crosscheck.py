"""2025 first-party value-up targets vs a 2026 title-only DART new plan.

No automatic percentage-point or exclusivity claim without issuer attachment.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from valueup_first_party_crosscheck import match_official_prior

def load():
    prior=json.loads((ROOT/"data/valueup_first_party_prior_evidence.json").read_text(encoding="utf-8"))
    beat=json.loads((ROOT/"digests/dart_beat_monitor_latest.json").read_text(encoding="utf-8"))
    record=next(x for x in beat["records"] if
        x.get("receiptNo")=="20261016800823" and x.get("company")=="KG스틸")
    return record,prior

class ValueUpCrosscheck(unittest.TestCase):
    def test_actual_official_receipt_plus_first_party_history(self):
        filing,prior=load()
        r=match_official_prior(filing,prior)
        self.assertIsNotNone(r)
        self.assertEqual(r["priorShareholderReturnTargetPercent"],30)
        self.assertEqual(r["priorRoeTargetAtLeastPercent"],13)
        self.assertEqual(r["newPressReportedShareholderReturnTargetPercent"],50)
        self.assertEqual(r["newPressReportedWindow"],"5개년")
        self.assertEqual(r["newDartUrl"],
          "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261016800823")
        self.assertTrue(r["newOfficialDartTitleVerified"])
        self.assertFalse(r["newOfficialAttachmentContentVerified"])
        self.assertFalse(r["canClaimTwentyPercentagePointIncrease"])
        self.assertFalse(r["periodDefinitionMatched"])
        self.assertFalse(r["denominatorMatched"])
        self.assertFalse(r["exclusiveConfirmed"])
        self.assertTrue(r["alreadyReportedNewPlanHeadline"])

    def test_forged_official_issuer_identity_rejected(self):
        receipt,prior=load()
        mutations={
          "company":"다른 회사","corpCode":"00999999",
          "receiptNo":"20261016800824",
          "published":"20261015",
          "sourceUrl":"https://dart.fss.or.kr.evil.test/dsaf001/main.do?rcpNo=20261016800823",
          "sourceType":"google_news_aggregation",
          "isCorrection":True,
          "report":"[기재정정]기업가치제고계획(자율공시)",
        }
        for key,value in mutations.items():
            bad=copy.deepcopy(receipt);bad[key]=value
            self.assertIsNone(match_official_prior(bad,prior),key)

    def test_false_percent_semantics_or_unofficial_links_do_not_qualify(self):
        row,p=load()
        modifications=[
            {"priorOriginalIssuerReleaseUrl":"https://www.kg-steel.co.kr.evil.test/html/PR_view.html?no=822"},
            {"currentHeadlineMediaUrl":"https://www.digitaltoday.co.kr.attacker.test/disclosure/articleView.html?idxno=707878"},
            {"currentOfficialUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261016800825"},
            {"company":"KG모빌리티"},
            {"priorAndCurrentDenominatorDefinitionVerified":True},
            {"priorAndCurrentPeriodComparableVerified":True},
            {"currentOfficialFilingBodyRetrieved":True},
            {"sameAngleDomesticCoverageFulltextChecked":True},
            {"exclusiveConfirmed":True},
            {"currentHeadlineMediaPublishedDate":"2025-02-11"},
        ]
        for modifications in modifications:
            altered=copy.deepcopy(p)
            altered["records"][0].update(modifications)
            self.assertIsNone(match_official_prior(row,altered),modifications)
        altered=copy.deepcopy(p)
        altered["records"][0]["priorIssuerStatedTargets"]["shareholderReturnTargetPercent"]=31
        self.assertIsNone(match_official_prior(row,altered))

    def test_recent_queue_has_exactly_one_original_2026_disclosure_and_no_scoop(self):
        import reporting_evidence_queue as queue
        row,prior=load()
        now=__import__("datetime").datetime(2026,10,17,21,0,tzinfo=queue.KST)
        src={"dartBeat":{
           "generatedAt":"2026-10-17T20:54:10+09:00",
           "status":"industry_beat_official_receipt_review",
           "sourceComplete":False,
           "records":[row]},
           "valueupPriors":prior}
        out=queue.build(src,now=now)
        self.assertEqual(out["recentOfficialTitleOnlyCount"],1)
        self.assertEqual(out["checkedOfficialRecentCandidates"],1)
        item=out["items"][0]
        self.assertEqual(item["officialDocumentDate"],"2026-10-16")
        r=item["crossYearPlanReview"]
        self.assertFalse(r["canClaimTwentyPercentagePointIncrease"])
        self.assertFalse(item["exclusiveConfirmed"])
        self.assertFalse(item["approvedForPitch"])
        self.assertFalse(item["officialDocumentBodyReviewed"])
        self.assertIn("기존 언론",item["evidenceSummary"])
        src["valueupPriors"]={"status":"unavailable","records":[]}
        other=queue.build(src,now=now)
        self.assertNotIn("crossYearPlanReview",other["items"][0])
        self.assertEqual(other["recentOfficialTitleOnlyCount"],1)

if __name__=="__main__":
    unittest.main()
