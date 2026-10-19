import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import customs_hs6 as hs

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,19,14,0,tzinfo=KST)

class CustomsHealthTests(unittest.TestCase):
    def test_outage_does_not_mean_zero_trade(self):
        state=hs.source_health(at=NOW,attempted=True,success=False,
                               error=RuntimeError("private-token-and-provider-url"))
        self.assertEqual(state["status"],"official_hs6_request_failed")
        self.assertEqual(state["upstreamErrorType"],"RuntimeError")
        self.assertFalse(state["newSnapshotVerified"])
        self.assertFalse(state["zeroRowsProvesNoTrade"])
        self.assertNotIn("private-token",str(state))
        self.assertEqual(state["confirmedScoops"],0)

    def test_missing_key_does_not_claim_success(self):
        state=hs.source_health(at=NOW,attempted=False,success=False)
        self.assertEqual(state["status"],"official_hs6_key_missing")
        self.assertFalse(state["sourceComplete"])

    def test_failing_producer_writes_health_and_leaves_previous_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            old=root/"hs.json"
            health=root/"health.json"
            old.write_text('{"status":"verified_hs6_country_trade_only","generatedAt":"2026-10-17T17:33:05+09:00"}',encoding="utf-8")
            before=old.read_bytes()
            with patch.dict(os.environ,{"CUSTOMS_API_KEY":"secret-value"}),patch.object(
                hs,"verify_dataset",side_effect=RuntimeError("secret-value network down")
            ),patch.object(sys,"argv",["customs_hs6.py","--out",str(old),
                                      "--health",str(health)]):
                with self.assertRaises(SystemExit) as exception:
                    hs.main()
            self.assertEqual(exception.exception.code,1)
            self.assertEqual(old.read_bytes(),before)
            result=json.loads(health.read_text(encoding="utf-8"))
            self.assertEqual(result["status"],"official_hs6_request_failed")
            self.assertFalse(result["newSnapshotVerified"])
            self.assertNotIn("secret-value",health.read_text(encoding="utf-8"))

    def test_good_producer_writes_current_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"hs.json"
            health=Path(tmp)/"health.json"
            sample={"status":"verified_hs6_country_trade_only","items":[{"hs6":"850423"}]}
            with patch.dict(os.environ,{"CUSTOMS_API_KEY":"secret"}),patch.object(
                hs,"verify_dataset",return_value=sample
            ),patch.object(sys,"argv",["customs_hs6.py","--out",str(target),
                                      "--health",str(health)]):
                hs.main()
            self.assertEqual(json.loads(target.read_text())["items"][0]["hs6"],"850423")
            self.assertTrue(json.loads(health.read_text())["newSnapshotVerified"])

if __name__=="__main__":
    unittest.main()
