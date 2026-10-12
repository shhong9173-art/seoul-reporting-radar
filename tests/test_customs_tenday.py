import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import customs_tenday as td


def xml_row(month="202610", period="01~10", overrides=None):
    values = {f"itemUsdAmt{i:02d}": str(100 if i else 2000) for i in range(11)}
    values.update(overrides or {})
    fields = {"priodMon": month, "priodDt": period, **values}
    body = "".join(f"<{k}>{v}</{k}>" for k, v in fields.items())
    return f"<response><header><resultCode>00</resultCode></header><body><items><item>{body}</item></items></body></response>"


class TenDayTests(unittest.TestCase):
    def test_months_include_previous_year_same_month(self):
        today = datetime(2026, 10, 13, tzinfo=timezone(timedelta(hours=9)))
        self.assertEqual(td.months_to_check(today),
                         ["202509", "202510", "202609", "202610"])

    def test_cumulative_cutoff(self):
        self.assertEqual(td.cutoff_for("01~10"), 10)
        self.assertEqual(td.cutoff_for("01~20"), 20)
        self.assertEqual(td.cutoff_for("01~31"), 99)
        self.assertEqual(td.cutoff_for("01~말일"), 99)
        with self.assertRaises(ValueError):
            td.cutoff_for("21~31")  # 누적 구간이 아니므로 거부

    def test_parse_preserves_thousand_usd(self):
        rows = td.parse(xml_row(overrides={"itemUsdAmt03": "1,234", "itemUsdAmt00": "3000"}),
                        "exp_item", "202610")
        self.assertEqual(rows[0]["cutoff"], 10)
        self.assertEqual(rows[0]["items"][3]["amountKUsd"], "1234")
        self.assertEqual(rows[0]["items"][3]["name"], "승용차")

    def test_partial_and_bad_response_fail_closed(self):
        for data in (
            xml_row(month="202609"),
            xml_row(overrides={"itemUsdAmt01": ""}),
            xml_row(overrides={"itemUsdAmt00": "20"}),
            xml_row(overrides={"itemUsdAmt01": "-8"}),
            '<response><header><resultCode>30</resultCode></header></response>',
        ):
            with self.subTest(data=data[:40]), self.assertRaises(ValueError):
                td.parse(data, "exp_item", "202610")

    def test_fetch_uses_verified_single_gateway_prefix(self):
        class Response:
            status_code = 200
            content = xml_row()
            def raise_for_status(self):
                return None
        with patch.object(td.requests, "get", return_value=Response()) as getter:
            rows = td.fetch("placeholder", "exp_item", "202610")
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                getter.call_args.args[0],
                "https://apis.data.go.kr/1220000/prlstMmUtPrviExpAcrs/getPrlstMmUtPrviExpAcrs")
            self.assertEqual(getter.call_args.kwargs["params"]["strtYymm"], "202610")

    def test_same_cutoff_yoy_and_no_mixing_years(self):
        today = datetime(2026, 10, 13, tzinfo=timezone(timedelta(hours=9)))
        def fake(_key, series, month):
            cutoff = 10 if month.endswith("10") else 99
            label = "01~10" if cutoff == 10 else "01~30"
            raw = xml_row(month, label)
            return td.parse(raw, series, month)
        result = td.build("placeholder", today=today, fetch_fn=fake)
        self.assertEqual(result["status"],
                         "official_provisional_10day_context_not_exclusive")
        self.assertEqual({x["month"] for x in result["focus"]}, {"202610"})
        self.assertTrue(all(x["priorYearMonth"] == "202510" for x in result["focus"]))
        self.assertTrue(all(x["comparisonStatus"] == "전년 동일 누적구간" for x in result["focus"]))

    def test_missing_latest_or_prior_data_not_zero(self):
        today = datetime(2026, 10, 13, tzinfo=timezone(timedelta(hours=9)))
        def fake(_key, series, month):
            return td.parse(xml_row(month), series, month) if month == "202610" else []
        result = td.build("placeholder", today=today, fetch_fn=fake)
        self.assertTrue(all(x["priorYearAmountKUsd"] is None for x in result["focus"]))
        self.assertTrue(all(x["yoyPercent"] is None for x in result["focus"]))

    def test_no_recent_rows_fail(self):
        today = datetime(2026, 10, 13, tzinfo=timezone(timedelta(hours=9)))
        with self.assertRaises(ValueError):
            td.build("placeholder", today=today, fetch_fn=lambda *args: [])


if __name__ == "__main__":
    unittest.main()
