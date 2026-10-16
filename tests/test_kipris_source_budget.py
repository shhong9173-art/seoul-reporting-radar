"""Request attempts are counted before failures; no invented provider quota."""
import sys,unittest,json,tempfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from kipris_source_budget import SourceRequestMeter,SourceRequestBudgetExhausted
import patent_hunt as hunt

NOW=datetime(2026,10,16,tzinfo=timezone(timedelta(hours=9)))

class Budget(unittest.TestCase):
    def test_reserve_before_22_and_stop_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"budget.json"
            count=[]
            def unavailable(url):
                count.append(url)
                raise RuntimeError("KIPRISPlus 응답 오류 코드 22")
            m=SourceRequestMeter(path,now=NOW,run_limit=1,monthly_limit=3,fetch=unavailable)
            with self.assertRaises(RuntimeError):
                m.get("secret-not-saved")
            self.assertEqual(len(count),1)
            self.assertEqual(m.public()["sourceRequestsCounted"],1)
            with self.assertRaises(SourceRequestBudgetExhausted):
                m.get("another-secret")
            self.assertEqual(len(count),1)
            self.assertNotIn("secret-not-saved",path.read_text())
    def test_monthly_persistence_and_month_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"budget.json"
            for i in range(2):
                m=SourceRequestMeter(path,now=NOW,run_limit=2,monthly_limit=2,fetch=lambda u:b"ok")
                m.get("https://example.test")
            m=SourceRequestMeter(path,now=NOW,monthly_limit=2,fetch=lambda u:b"ok")
            with self.assertRaises(SourceRequestBudgetExhausted):m.get("url")
            tomorrow=datetime(2026,11,1,tzinfo=NOW.tzinfo)
            later=SourceRequestMeter(path,now=tomorrow,monthly_limit=2,fetch=lambda u:b"ok")
            self.assertEqual(later.public()["sourceRequestsCounted"],0)
    def test_corrupted_ledger_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"budget.json";path.write_text('{"month":"2026-10"}')
            with self.assertRaises(SourceRequestBudgetExhausted):
                SourceRequestMeter(path,now=NOW,fetch=lambda u:b"ok")
    def test_failed_fetch_integration_does_not_replace_verified_dataset(self):
        with tempfile.TemporaryDirectory() as folder:
            meter=SourceRequestMeter(Path(folder)/"budget.json",now=NOW,
                                    run_limit=1,monthly_limit=1,fetch=lambda u:
                                    b"<response><header><resultCode>22</resultCode></header></response>")
            report=hunt.build("fake",now=NOW,news_limit=0,
                names=["현대자동차","기아"],
                search=lambda k,t,start,end:hunt.search_applicant(
                    k,t,start,end,fetch=meter.get))
            self.assertFalse(report["sourceWindowComplete"])
            self.assertEqual(report["companyChecks"][0]["providerResultCode"],"22")
            self.assertEqual(report["companyChecks"][1]["status"],"not_attempted_after_provider_error")
if __name__=="__main__":unittest.main()
