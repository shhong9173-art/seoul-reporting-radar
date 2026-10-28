import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from scripts.primary_sec_filing_watch import collect,ROOT
from scripts.publish_newsroom_outputs import selected,OUTPUTS

SPEC=json.loads((ROOT/"data/primary_sec_filer_watches.json").read_text("utf-8"))
NOW=datetime(2026,10,21,14,tzinfo=timezone.utc)

def sample(cik):
    return {"cik":int(cik),"filings":{"recent":{
        "accessionNumber":[cik+"-26-099999"],
        "form":["8-K"],"filingDate":["2026-10-21"],
        "primaryDocument":["test-8k.htm"],
    }}}

class SECOriginalPublisherTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.root=Path(self.dir.name)
        (self.root/"digests").mkdir()
        self.file=self.root/"digests/primary_sec_filing_watch_latest.json"
        self.data=collect(SPEC,now=NOW,fetcher=sample)
        self.save(self.data)
    def tearDown(self):
        self.dir.cleanup()
    def save(self,x):
        self.file.write_text(json.dumps(x),encoding="utf-8")
    def test_publish_only_source_receipt_without_article_or_partner_claims(self):
        self.assertEqual(OUTPUTS["sec_filings"],("digests/primary_sec_filing_watch_latest.json",))
        self.assertEqual(selected(self.root,"sec_filings"),
                         ["digests/primary_sec_filing_watch_latest.json"])
        self.assertEqual(self.data["sourcesChecked"],4)
        self.assertEqual(self.data["newlyObservedAfterBaseline"],0)
        self.assertFalse(self.data["allOriginalDocumentBodiesRead"])
    def test_unsafe_facts_or_counts_are_rejected(self):
        for key,value in [("confirmedScoops",1),("allDomesticPressChecked",True),
                          ("allOriginalDocumentBodiesRead",True),
                          ("filingsObserved",0),
                          ("sourceCoverageExhaustive",True)]:
            r=json.loads(json.dumps(self.data))
            r[key]=value
            self.save(r)
            with self.assertRaises(ValueError,msg=key):
                selected(self.root,"sec_filings")
        r=json.loads(json.dumps(self.data))
        r["filings"][0]["contractOrPartnerMentionVerified"]=True
        self.save(r)
        with self.assertRaises(ValueError):selected(self.root,"sec_filings")
    def test_exact_standalone_production_cli_read_only(self):
        self.save(self.data)
        cmd=[sys.executable,str(ROOT/"scripts/publish_newsroom_outputs.py"),
             "--mode","sec_filings","--check-only","--root",str(self.root)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("read-only; no git push",p.stdout)
        x=json.loads(json.dumps(self.data))
        x["filings"][0]["exclusiveConfirmed"]=True
        self.save(x)
        denied=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(denied.returncode,0)
        self.assertIn("sec_filing_unverified_evidence_cannot_publish",denied.stderr)

if __name__=="__main__":
    unittest.main()
