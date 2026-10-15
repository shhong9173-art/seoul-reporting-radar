"""Real-user scoop archetypes: foreign recall/domestic comparison and recognized dividends."""
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import crossborder_source_gap_triage as t

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,16,11,0,tzinfo=KST)

def safety_record():
    return {
      "id":"26V664000","officialDate":"20261008",
      "sourceUrl":"https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber=26V664000",
      "makes":["GENESIS","HYUNDAI"],
      "models":[{"model":"G80","year":"2017"},{"model":"GENESIS","year":"2015"}],
      "defect":"The front power seat motors may overheat; fire while parked or driving.",
      "flags":["fire_or_thermal_word_in_us_summary","us_park_outside_advice"],
      "usRecallExists":True,"exclusiveConfirmed":False,
      "koreanRecallChecked":False,"koreanIncidentVerified":False
    }

def note():
    return {
      "receiptNo":"20260916000427","company":"기아",
      "filingUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260916000427",
      "evidenceTier":"low_confidence_proximity",
      "tableExcerpt":("당반기 중 투자손익. (단위: 백만원) 제83기 반기 "
         "배당금수익 1,747,732, 전반기 배당금수익 146,488. "
         "당반기 배당금수익은 Kia Slovakia s.r.o.(KaSK)로부터 인식한 "
         "1,610,458백만원, 현대모비스로부터 인식한 82,135백만원 등으로 구성됩니다."),
      "cashReceiptVerified":False,"scoopConfirmed":False
    }

def sources():
    return (
      {"status":"official_us_recalls_to_review","confirmedScoops":0,
       "generatedAt":"2026-10-16T03:28:49+09:00",
       "archiveLatestReceived":"2026-10-15","campaignCount":1,"leads":[safety_record()]},
      {"status":"evidence_excerpts_not_verified_dividend_receipts",
       "confirmedScoops":0,"generatedAt":"2026-10-16T03:28:52+09:00",
       "foreignRegistryStatus":"not_connected",
       "sourceChecks":[{"company":"기아","period":"current","status":"checked"}],
       "leads":[note()]}
    )

class CrossBorderDossiers(unittest.TestCase):
    def test_genesis_nhtsa_only_us_recall_no_korea_absence(self):
        n,d=sources()
        data=t.build(n,d,now=NOW)
        safety=next(x for x in data["items"] if x["type"]=="overseas_safety_domestic_comparison")
        self.assertEqual(safety["officialFact"]["usCampaign"],"26V664000")
        self.assertEqual(safety["reporterPriority"],"domestic_crosscheck_first")
        self.assertFalse(safety["pitchGate"]["domesticOfficialChecked"])
        self.assertFalse(safety["pitchGate"]["exactComponentMatch"])
        self.assertFalse(safety["pitchGate"]["exclusiveConfirmed"])
        self.assertEqual(safety["sourceAvailability"]["koreanOfficialRecall"],
                         "api_not_connected_requires_authorization")
        self.assertEqual(data["confirmedScoops"],0)
        self.assertFalse(data["domesticRecallAbsenceVerified"])

    def test_kia_recognized_issuer_dividend_not_cash_and_not_a_new_20261016_event(self):
        n,d=sources()
        result=t.build(n,d,now=NOW)
        row=next(x for x in result["items"] if x["type"]=="foreign_subsidiary_dividend_accounting")
        self.assertEqual(row["officialFact"]["recognizedFromEntity"],
                         "Kia Slovakia s.r.o.(KaSK)")
        self.assertEqual(row["officialFact"]["recognizedAmountInMillionKrw"],1610458)
        self.assertEqual(row["officialFact"]["recognizedDividendIncomeText"],"1,610,458백만원")
        self.assertEqual(row["officialPublicationDate"],"2026-09-16")
        self.assertEqual(row["reportingWindowStatus"],"historical_public_filing_to_investigate")
        self.assertFalse(row["pitchGate"]["cashReceivedByParentVerified"])
        self.assertFalse(row["pitchGate"]["foreignCompanyLegalAccountsVerified"])
        self.assertFalse(row["pitchGate"]["sameAnglePriorPressChecked"])
        self.assertFalse(result["foreignParentCashTransferVerified"])

    def test_wrong_entity_or_total_dividend_is_not_subsidiary_amount(self):
        x=note()
        x["tableExcerpt"]="당반기 배당금수익은 1,747,732백만원입니다. Kia Slovakia 현지공장 매출 32억원"
        self.assertEqual(t.recognized_dividend_dossiers(x),[])

    def test_unverified_source_failure_cannot_be_zero(self):
        n,d=sources()
        n["status"]="provider_error"
        with self.assertRaisesRegex(ValueError,"source_invalid"):
            t.build(n,d,now=NOW)
        n,d=sources()
        d["confirmedScoops"]=1
        with self.assertRaisesRegex(ValueError,"source_invalid"):
            t.build(n,d,now=NOW)

    def test_wrong_recall_url_and_korean_recall_claim_both_rejected(self):
        x=safety_record()
        x["sourceUrl"]="https://not-nhtsa.example/recall"
        self.assertIsNone(t.safety_dossier(x,NOW))
        x=safety_record()
        x["koreanRecallChecked"]=True
        self.assertIsNone(t.safety_dossier(x,NOW))

    def test_input_from_future_and_stale_note_state_visible(self):
        n,d=sources()
        n["generatedAt"]="2026-10-18T13:01:00+09:00"
        with self.assertRaisesRegex(ValueError,"unverified_source_creation_time"):
            t.build(n,d,now=NOW)
        n,d=sources()
        n["generatedAt"]="2026-10-13T03:00:00+09:00"
        result=t.build(n,d,now=NOW)
        self.assertTrue(result["sourceStale48h"])
        self.assertEqual(result["confirmedScoops"],0)

    def test_real_committed_official_datasets_if_both_still_available(self):
        import json
        a=ROOT/"digests/crossborder_safety_latest.json"
        b=ROOT/"digests/overseas_dividend_evidence_latest.json"
        if not (a.exists() and b.exists()):
            self.skipTest("Official snapshots not committed")
        n=json.loads(a.read_text(encoding="utf-8"))
        d=json.loads(b.read_text(encoding="utf-8"))
        # Use exact first run time rather than a frozen NOW to avoid future-data false failures.
        dynamic=max(NOW,datetime.fromisoformat(n["generatedAt"])+timedelta(minutes=1),
                    datetime.fromisoformat(d["generatedAt"])+timedelta(minutes=1))
        out=t.build(n,d,now=dynamic)
        self.assertFalse(out["domesticRecallAbsenceVerified"])
        self.assertFalse(out["foreignParentCashTransferVerified"])
        self.assertEqual(out["confirmedScoops"],0)
        self.assertEqual(out["approvedArticles"],0)
        for x in out["items"]:
            self.assertTrue(x["publicationAloneIsNotScoop"])
            self.assertFalse(x["pitchGate"]["exclusiveConfirmed"])

if __name__=="__main__":unittest.main()
