import json
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

from scripts.primary_sec_filing_watch import (
    registry,collect,decode_filing_rows,ROOT,STATUS
)

NOW=datetime(2026,10,21,13,30,tzinfo=timezone.utc)
CFG=json.loads((ROOT/"data/primary_sec_filer_watches.json").read_text("utf-8"))

def response(cik,new=False):
    rows=[
      ("0001104659-26-091234","8-K","2026-10-17","report-20261017.htm"),
      ("0001104659-26-088789","10-Q","2026-08-05","quarterly.htm"),
      ("0001104659-26-012345","4","2026-10-16","wkform4.htm"),
      ("0001104659-26-011111","8-K","2024-10-15","ancient.htm"),
      ("0001104659-26-022222","8-K","2026-10-16","../bad.htm"),
    ]
    if new:
        rows.insert(0,("0001104659-26-098765","8-K","2026-10-21",
                       "new_current_event.htm"))
    return {
      "cik":int(cik),"name":"Sample company",
      "filings":{"recent":{
          "accessionNumber":[x[0].replace("0001104659",cik) for x in rows],
          "form":[x[1] for x in rows],
          "filingDate":[x[2] for x in rows],
          "primaryDocument":[x[3] for x in rows],
      }}
    }

class SECOriginalIndexWatch(unittest.TestCase):
    def test_first_live_like_index_is_baseline_not_scoop(self):
        s=collect(CFG,now=NOW,fetcher=lambda cik:response(cik))
        self.assertEqual(s["status"],STATUS)
        self.assertEqual(s["sourcesChecked"],4)
        self.assertEqual(s["filingsObserved"],8)
        self.assertEqual(s["newlyObservedAfterBaseline"],0)
        self.assertTrue(all(x["baselineOnly"] for x in s["sources"]))
        self.assertTrue(all(not x["originalDocumentBodyRead"] for x in s["filings"]))
        self.assertTrue(all(not x["exclusiveConfirmed"] for x in s["filings"]))
        self.assertEqual(s["confirmedScoops"],0)
        self.assertFalse(s["sourceCoverageExhaustive"])
        self.assertFalse(s["allOriginalDocumentBodiesRead"])
        self.assertTrue(all(x["filingOriginalUrl"].startswith(
            "https://www.sec.gov/Archives/edgar/data/") for x in s["filings"]))

    def test_followup_records_only_new_accession_not_newly_public_scoop(self):
        old=collect(CFG,now=NOW,fetcher=lambda cik:response(cik))
        def next_response(cik):
            return response(cik,new=cik=="0001819142")
        nxt=collect(CFG,old,now=NOW+timedelta(hours=4),fetcher=next_response)
        self.assertEqual(nxt["newlyObservedAfterBaseline"],1)
        first=nxt["filings"][0]
        self.assertTrue(first["newSinceCleanBaseline"])
        self.assertEqual(first["company"],"SES AI")
        self.assertEqual(first["filingDate"],"2026-10-21")
        self.assertFalse(first["contractOrPartnerMentionVerified"])
        self.assertFalse(first["fullTextAndPriorPressCompared"])
        self.assertFalse(first["actualTransactionDateVerified"])
        self.assertEqual(nxt["confirmedScoops"],0)

    def test_failed_api_not_recast_as_legitimate_zero_and_cache_kept(self):
        old=collect(CFG,now=NOW,fetcher=lambda cik:response(cik))
        def failing(cik):
            if cik=="0001819142":
                raise TimeoutError("SEC source down")
            return response(cik)
        nxt=collect(CFG,old,now=NOW+timedelta(hours=1),fetcher=failing)
        self.assertEqual(nxt["sourcesUnavailable"],1)
        self.assertEqual(nxt["newlyObservedAfterBaseline"],0)
        stale=[r for r in nxt["filings"] if r["company"]=="SES AI"]
        self.assertEqual(len(stale),2)
        self.assertTrue(all(r["notRecheckedThisRun"] for r in stale))
        failed=next(s for s in nxt["sources"] if s["cik"]=="0001819142")
        self.assertEqual(failed["status"],"source_unavailable")
        self.assertEqual(failed["failStreak"],1)
        self.assertEqual(nxt["confirmedScoops"],0)

    def test_malformed_source_cik_or_column_alignment_is_not_empty(self):
        x=response("0001819142")
        x["cik"]=1
        with self.assertRaises(ValueError):
            decode_filing_rows(x,"0001819142",now=NOW)
        x=response("0001819142")
        x["filings"]["recent"]["form"].pop()
        with self.assertRaises(ValueError):
            decode_filing_rows(x,"0001819142",now=NOW)
        data=collect(CFG,now=NOW,fetcher=lambda cik: x if cik=="0001819142" else response(cik))
        self.assertEqual(data["sourcesUnavailable"],1)
        self.assertEqual(data["sourcesChecked"],3)
        self.assertFalse(data["sourceCoverageExhaustive"])

    def test_invalid_cik_and_corrupt_previous_fail_closed(self):
        bad=json.loads(json.dumps(CFG))
        bad["companies"][0]["cik"]="9999/../etc"
        with self.assertRaises(ValueError):registry(bad)
        with self.assertRaises(ValueError):
            collect(CFG,{"status":"missing"},now=NOW,
                    fetcher=lambda cik:response(cik))

    def test_bad_future_date_and_path_not_published(self):
        x=response("0001819142")
        x["filings"]["recent"]["filingDate"][0]="2027-04-01"
        rows=decode_filing_rows(x,"0001819142",now=NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["form"],"10-Q")

if __name__=="__main__":
    unittest.main()
