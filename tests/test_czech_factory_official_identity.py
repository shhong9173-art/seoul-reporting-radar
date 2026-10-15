"""Czech factory ARES legal identity cannot be confused with importer or dividends."""
import sys,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import czech_factory_official_identity as m
NOW=datetime(2026,10,16,5,0,tzinfo=timezone(timedelta(hours=9)))
class CzechAres(unittest.TestCase):
    def test_official_factory_registered_name_identity(self):
        x=m.verify(lambda:{"ico":"27773035",
            "obchodniJmeno":"Hyundai Motor Manufacturing Czech s.r.o.",
            "datumVzniku":"2006-07-07"},now=NOW)
        self.assertTrue(x["identityVerified"])
        self.assertEqual(x["identityStatus"],"exact_company_ico_and_registered_name")
        self.assertFalse(x["czechAuditedAccountsDocumentChecked"])
        self.assertFalse(x["czechDividendDistributionVerified"])
        self.assertFalse(x["koreanParentCashReceiptVerified"])
        self.assertFalse(x["exclusiveConfirmed"])
    def test_importer_and_wrong_ico_must_not_match_factory(self):
        for code,name in (
            ("28399757","Hyundai Motor Czech s.r.o."),
            ("27773035","Hyundai Motor Czech s.r.o."),
            ("28399757","Hyundai Motor Manufacturing Czech s.r.o.")):
            r=m.verify(lambda:{"ico":code,"obchodniJmeno":name},now=NOW)
            self.assertFalse(r["identityVerified"])
    def test_api_failure_stays_unverified_not_no_accounts(self):
        def fail():raise TimeoutError("cannot reach official service")
        r=m.verify(fail,now=NOW)
        self.assertEqual(r["identityStatus"],"official_api_unavailable_or_wrong_legal_entity")
        self.assertFalse(r["czechAuditedAccountsDocumentChecked"])
if __name__=="__main__":unittest.main()
