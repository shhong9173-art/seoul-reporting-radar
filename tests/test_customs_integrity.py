"""Regression coverage for the customs API client and newsroom data precision."""
import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import customs
import business_coverage as coverage


class CustomsIntegrityTests(unittest.TestCase):
    def rows(self):
        return [{"year":"202601","expDlr":"10.50","expWgt":"12.25",
                 "impDlr":"0","impWgt":"2"},
                {"year":"202601","expDlr":"1.50","expWgt":"2.75",
                 "impDlr":"3","impWgt":"4"}]

    def run_csv(self,rows):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(customs,"fetch",return_value=rows), \
                 patch.object(customs,"ROOT",Path(folder)), \
                 patch.dict(os.environ,{"CUSTOMS_API_KEY":"fake"}), \
                 patch.object(sys,"argv",["customs.py","--hs","8504",
                                         "--start","202601","--end","202601"]):
                customs.main()
            out=Path(folder)/"data"/"customs_8504_ALL_202601_202601.csv"
            if out.exists():
                with out.open(encoding="utf-8-sig",newline="") as stream:
                    return list(csv.DictReader(stream))
            return None

    def test_valid_month_and_decimal_amount_sums(self):
        rows=self.run_csv(self.rows())
        self.assertEqual(rows[0]["월"],"202601")
        self.assertEqual(rows[0]["수출금액(달러)"],"12.00")
        self.assertEqual(rows[0]["수출중량(kg)"],"15.00")
        self.assertEqual(rows[0]["수입금액(달러)"],"3")

    def test_official_yyyy_dot_mm_label_normalized(self):
        rows=self.rows()
        rows[0]["year"]="2026.01"
        rows[1]["year"]="2026.01"
        out=self.run_csv(rows)
        self.assertEqual(len(out),1)
        self.assertEqual(out[0]["월"],"202601")
        self.assertEqual(out[0]["수출금액(달러)"],"12.00")

    def test_total_row_not_double_counted(self):
        rows=self.rows()+[{"year":"총계","expDlr":"999999"}]
        out=self.run_csv(rows)
        self.assertEqual(out[0]["수출금액(달러)"],"12.00")

    def test_month_format_bad_fails(self):
        rows=self.rows();rows[0]["year"]="202699"
        with self.assertRaises(ValueError):
            self.run_csv(rows)

    def test_missing_api_field_must_not_turn_to_zero(self):
        rows=self.rows();rows[0].pop("expWgt")
        with self.assertRaises(ValueError):
            self.run_csv(rows)

    def test_bad_decimal_is_not_zero(self):
        for v in ("", "bad", "NaN", "-4", None, "Infinity"):
            with self.subTest(v=v),self.assertRaises(ValueError):
                customs.num(v)

    def test_bad_hs_and_month_rejected_before_api(self):
        with patch.dict(os.environ,{"CUSTOMS_API_KEY":"fake"}), \
             patch.object(sys,"argv",["customs.py","--hs","bad",
                                      "--start","202613","--end","202601"]):
            with self.assertRaises(SystemExit):
                customs.main()

    def test_press_query_never_contains_long_group_entity_string(self):
        f={"company":"효성중공업","topic":"productionCapacity","toYear":2025,
           "rowIdentity":["중공업","효성중공업주nantonghyosungtransformercoltdhyosungtanddindiapvtltd"]}
        text=coverage.query_for(f)
        self.assertNotIn("nantong",text)
        self.assertLess(len(text),100)

    def test_news_scan_prioritizes_distinct_issuers(self):
        base=lambda company,topic,change: {
            "company":company,"topic":topic,"toYear":2025,
            "rowIdentity":["전력기기"],"carryForwardMatched":True,
            "changePercent":change}
        items=[base("HD현대일렉트릭","segmentSales",p) for p in (39,20,10,5)]
        items.extend([base("효성중공업","productionCapacity",23),
                      base("엘에스일렉트릭","productionCapacity",-7)])
        seen=[]
        def fake(f):
            seen.append(f["company"])
            return {"status":"검색상 미발견: 단독 판단 불가","articles":[]}
        coverage.build({"generatedAt":"x","findings":items},search=fake,limit=3)
        self.assertEqual(len(seen),3)
        self.assertEqual(set(seen),{"HD현대일렉트릭","효성중공업","엘에스일렉트릭"})


if __name__=="__main__":
    unittest.main()
