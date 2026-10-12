import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import customs_watch as cw


def trade_row(month,amount,weight):
    return {"year":month,"expDlr":str(amount),"expWgt":str(weight),
            "impDlr":"0","impWgt":"0"}


class CustomsWatchTests(unittest.TestCase):
    def test_same_month_hs_unit_value_is_not_issuer_price(self):
        def fetch(k,hs,start,end,country):
            self.assertEqual(country,"")
            self.assertEqual(hs,"8504")
            return ([trade_row("202501",100,10)] if start=="202501" else
                    [trade_row("202601",180,12)])
        result=cw.build("key","202501","202609",2026,codes=("8504",),fetch=fetch)
        v=result["items"][0]["comparison"]
        self.assertEqual(v["comparableMonths"],["01"])
        self.assertEqual(v["totals"]["exportValueYoYPercent"],80.0)
        self.assertEqual(v["totals"]["exportWeightYoYPercent"],20.0)
        self.assertEqual(v["totals"]["unitValueYoYPercent"],50.0)
        self.assertIn("특정 기업",result["items"][0]["scopeWarning"])

    def test_missing_months_reported_not_filled_with_zero(self):
        with self.assertRaises(ValueError):
            cw.build("key","202501","202609",2026,codes=("8504",),
                     fetch=lambda *args:[trade_row("202601",80,10)])

    def test_missing_fields_fail_closed(self):
        with self.assertRaises(ValueError):
            cw.aggregate([{"year":"202601","expDlr":"80"}],"202501","202609")

    def test_invalid_month_and_outside_window_fail(self):
        for month in ("202699","bad","202401"):
            with self.subTest(month=month),self.assertRaises(ValueError):
                cw.aggregate([trade_row(month,10,3)],"202501","202609")

    def test_no_key_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"out.json"
            with patch.dict(os.environ,{"CUSTOMS_API_KEY":""}), \
                 patch.object(sys,"argv",["customs_watch.py","--output",str(p)]):
                cw.main()
            self.assertFalse(p.exists())

    def test_previous_full_calendar_month(self):
        self.assertEqual(cw.last_complete_month(datetime(2026,10,13)),"202609")
        self.assertEqual(cw.last_complete_month(datetime(2026,1,13)),"202512")

    def test_out_of_scope_code_excluded(self):
        with self.assertRaises(ValueError):
            cw.build("key","202501","202609",2026,codes=("0101",))

if __name__=="__main__":
    unittest.main()
