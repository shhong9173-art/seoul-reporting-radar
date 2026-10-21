"""Atomic publisher may only publish an evidence-safe full research report."""
import json
import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path

from scripts.primary_document_dossiers import dossier,ROOT
from scripts.publish_newsroom_outputs import selected,OUTPUTS

class PrimaryResearchPublisher(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.root=Path(self.t.name)
        (self.root/"digests").mkdir()
        registry=json.loads((ROOT/"data/primary_research_targets.json").read_text())
        report=dossier(registry,now=datetime(2026,10,21,4,tzinfo=timezone.utc),
                       fetcher=lambda url: (_ for _ in ()).throw(TimeoutError("offline")))
        self.path=self.root/"digests/primary_research_dossiers_latest.json"
        self.write(report)
    def tearDown(self):
        self.t.cleanup()
    def write(self,doc):
        self.path.write_text(json.dumps(doc,ensure_ascii=False),encoding="utf-8")
    def test_does_not_publish_unowned_sources_or_fake_story_labels(self):
        self.assertEqual(OUTPUTS["primary_dossiers"],(
            "digests/primary_research_dossiers_latest.json",))
        self.assertEqual(selected(self.root,"primary_dossiers"),
                         ["digests/primary_research_dossiers_latest.json"])
        data=json.loads(self.path.read_text())
        self.assertEqual(data["documentPagesMatched"],0)
        self.assertEqual(data["documentPagesFailedOrUnmatched"],7)
        self.assertFalse(data["allDomesticPressChecked"])
    def test_impossible_source_counts_or_unsupported_exclusive_fail_publish(self):
        for key,val in [("confirmedScoops",1),("allDomesticPressChecked",True),
                        ("documentPagesMatched",2),("caseCount",18)]:
            data=json.loads(self.path.read_text())
            data[key]=val
            self.write(data)
            with self.assertRaises(ValueError,msg=key):
                selected(self.root,"primary_dossiers")
            data[key]=0 if key in ("confirmedScoops","documentPagesMatched") else (
                False if key=="allDomesticPressChecked" else 5)
            self.write(data)
    def test_partial_evidence_cannot_be_mislabeled_as_source_verified(self):
        data=json.loads(self.path.read_text())
        data["cases"][0]["originalDocumentsVerified"]=1
        self.write(data)
        with self.assertRaises(ValueError):
            selected(self.root,"primary_dossiers")

if __name__=="__main__":unittest.main()
