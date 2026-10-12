import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import trade_trends


class TradeTrendTests(unittest.TestCase):
    def row(self, money, weight):
        return {"수출금액(달러)": Decimal(money), "수출중량(kg)": Decimal(weight),
                "수입금액(달러)": Decimal(0), "수입중량(kg)": Decimal(0)}

    def test_same_month_period_not_mixed(self):
        data = {"202501": self.row(100, 10), "202502": self.row(100, 10),
                "202601": self.row(180, 12), "202603": self.row(1000, 200)}
        res = trade_trends.compare_years(data, target_year=2026)
        self.assertEqual(res["comparableMonths"], ["01"])
        self.assertEqual(res["totals"]["exportValueYoYPercent"], 80.0)
        self.assertEqual(res["totals"]["exportWeightYoYPercent"], 20.0)
        self.assertEqual(res["status"], "전월이 아닌 전년 동월 비교: 해당 월 교집합만 계산")

    def test_unit_value_not_contract_price(self):
        data = {"202501": self.row(100, 10), "202601": self.row(180, 12)}
        res = trade_trends.compare_years(data, target_year=2026)
        self.assertEqual(res["totals"]["currentUnitValueUsdPerKg"], "15")
        self.assertEqual(res["totals"]["previousUnitValueUsdPerKg"], "10")
        self.assertEqual(res["totals"]["unitValueYoYPercent"], 50.0)

    def test_zero_weight_cannot_be_used_as_unit_value(self):
        data = {"202501": self.row(100, 0), "202601": self.row(180, 0)}
        res = trade_trends.compare_years(data, target_year=2026)
        self.assertIsNone(res["totals"]["currentUnitValueUsdPerKg"])
        self.assertIsNone(res["totals"]["unitValueYoYPercent"])

    def test_no_comparable_month_is_explicit(self):
        data = {"202601": self.row(100, 10)}
        res = trade_trends.compare_years(data, target_year=2026)
        self.assertIsNone(res["totals"])

    def test_invalid_csv_values_fail_closed(self):
        self.assertRaises(ValueError, trade_trends.parse_amount, "NaN")
        self.assertRaises(ValueError, trade_trends.parse_amount, "-3")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"bad.csv"
            path.write_text("월,수출금액(달러),수출중량(kg),수입금액(달러),수입중량(kg)\n"
                            "202613,1,10,0,0\n", encoding="utf-8")
            self.assertRaises(ValueError, trade_trends.read_rows, path)

    def test_duplicate_month_not_double_counted(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"duplicated.csv"
            path.write_text("월,수출금액(달러),수출중량(kg),수입금액(달러),수입중량(kg)\n"
                            "202601,10,1,0,0\n202601,20,2,0,0\n", encoding="utf-8")
            self.assertRaises(ValueError,trade_trends.read_rows,path)


if __name__ == "__main__":
    unittest.main()
