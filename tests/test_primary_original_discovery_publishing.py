import json
import tempfile
import subprocess
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
from scripts.primary_original_discovery import discover,ROOT
from scripts.publish_newsroom_outputs import selected,OUTPUTS

class PrimaryOriginalDiscoveryPublisher(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        (self.root/"digests").mkdir()
        cfg=json.loads((ROOT/"data/primary_site_listing_watches.json").read_text("utf-8"))
        self.report=discover(cfg,now=datetime(2026,10,21,4,tzinfo=timezone.utc),
          listing_fetcher=lambda url:('<html><a href="/blog/hyundai-lawsuit">Hyundai vehicle litigation</a>'
              '<p>This is a public site</p></html>' if url.endswith("/blog")
              else '<html><h1>Official company auction listing</h1>No tracked entities</html>'),
          detail_fetcher=lambda url:("IPGATE primary page reports patent litigation "
                    "against Hyundai Motor Europe and Hyundai Motor Deutschland"))
        self.path=self.root/"digests/primary_original_discovery_latest.json"
        self.write(self.report)
    def tearDown(self):
        self.tmp.cleanup()
    def write(self,report):
        self.path.write_text(json.dumps(report),encoding="utf-8")
    def test_checked_list_original_is_not_an_exclusive(self):
        self.assertEqual(OUTPUTS["primary_discovery"],(
            "digests/primary_original_discovery_latest.json",))
        self.assertEqual(selected(self.root,"primary_discovery"),[
            "digests/primary_original_discovery_latest.json"])
        self.assertEqual(self.report["candidateCount"],1)
        self.assertEqual(self.report["newlyObservedAfterBaseline"],0)
        self.assertEqual(self.report["confirmedScoops"],0)
    def test_false_scoop_and_false_absence_cannot_publish(self):
        for key,bad in (("confirmedScoops",1),("sourceCoverageExhaustive",True),
                        ("domesticNoPriorCoverageProved",True),("candidateCount",200)):
            data=json.loads(json.dumps(self.report));data[key]=bad;self.write(data)
            with self.assertRaises(ValueError):
                selected(self.root,"primary_discovery")
        data=json.loads(json.dumps(self.report))
        data["candidates"][0]["confirmedExclusive"]=True
        self.write(data)
        with self.assertRaises(ValueError):
            selected(self.root,"primary_discovery")
    def test_real_script_cli_does_read_only_source_validation(self):
        cmd=[sys.executable,str(ROOT/"scripts/publish_newsroom_outputs.py"),
             "--mode","primary_discovery","--check-only",
             "--root",str(self.root)]
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=8)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertIn("read-only; no git push",run.stdout)
        data=json.loads(json.dumps(self.report))
        data["candidates"][0]["confirmedExclusive"]=True
        self.write(data)
        bad=subprocess.run(cmd,capture_output=True,text=True,timeout=8)
        self.assertNotEqual(bad.returncode,0)
        self.assertIn("unsafe_or_unverified_first_party_discovery",bad.stderr)

    def test_arbitrary_external_link_is_rejected(self):
        data=json.loads(json.dumps(self.report))
        data["candidates"][0]["url"]="https://untrusted.example.com/personal"
        self.write(data)
        with self.assertRaises(ValueError):
            selected(self.root,"primary_discovery")

if __name__=="__main__":unittest.main()
