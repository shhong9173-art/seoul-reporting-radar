"""Offline tests for the five independent Customs statistical API collectors."""
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import customs_five as cf

KST = timezone(timedelta(hours=9))


def fake_fetch(key, route, params):
    assert key == "placeholder"
    year = params["strtYymm"][:4]
    month = params["strtYymm"]
    amount = "18000000" if year == "2026" else "12000000"
    flow = "수출" if params.get("imexTpcd", "1") == "1" else "수입"
    if route.startswith("sidoitemtrade/"):
        return [{"priodTitle": year, "hsSgn": "87", "korePrlstNm": "자동차 등",
                 "expUsdAmt": amount, "impUsdAmt": "1000000"},
                {"priodTitle": "총계", "expUsdAmt": "999999999", "impUsdAmt": "999999999"}]
    if route.startswith("kindtrade/"):
        return [{"year": month, "statCd": "A" if flow == "수출" else "11",
                 "statCdCntnKor1": "일반수출" if flow == "수출" else "일반수입",
                 "impexp": flow, "dlr": amount, "wgt": "120",
                 "cnt": "1", "won": "360000000"},
                {"year": "총계", "statCd": "-", "statCdCntnKor1": "-",
                 "impexp": flow, "dlr": "999999999"}]
    if route.startswith(("nnewtempertrade/", "newtempertrade/", "ntempertrade/")):
        code = "4Z001" if route.startswith("ntempertrade/") else "23050102"
        country = params.get("cntyCd", "US")
        return [{"year": year + "." + month[4:], "impexp": flow,
                 "statCd": country, "statCdCntnKor1": "미국",
                 "godsCd": code, "godsKor": "자동차 관련 부품", "dlr": amount, "wgt": "100"}]
    raise AssertionError(route)


class CustomsFiveTests(unittest.TestCase):
    def test_release_cutoff_not_future_month(self):
        self.assertEqual(cf.month_for(datetime(2026, 10, 13, tzinfo=KST)), "202608")
        self.assertEqual(cf.month_for(datetime(2026, 10, 16, tzinfo=KST)), "202609")
        self.assertEqual(cf.month_for(datetime(2027, 1, 13, tzinfo=KST)), "202611")

    def test_no_key(self):
        with self.assertRaises(ValueError):
            cf.build("", fetcher=fake_fetch)

    def test_all_five_independent_and_month_yoy(self):
        d = cf.build("placeholder", now=datetime(2026, 10, 13, tzinfo=KST), fetcher=fake_fetch)
        self.assertEqual(d["period"], "202608")
        self.assertEqual(len(d["services"]), 5)
        self.assertEqual({s["id"] for s in d["services"]}, set(cf.SERVICES))
        for s in d["services"]:
            self.assertGreater(s["rawRecordsCurrent"], 0)
            self.assertGreater(len(s["rows"]), 0)
            self.assertTrue(all(r["previousMonth"] == "202508" for r in s["rows"]))
            self.assertTrue(all(r["comparisonStatus"] == "전년 동일 월·동일 분류" for r in s["rows"]))
            self.assertTrue(all("company" not in r for r in s["rows"]))
        region = next(x for x in d["services"] if x["id"] == "regional")
        self.assertEqual(region["unit"], "천 달러")
        self.assertEqual(len(region["rows"]), 6)
        new = next(x for x in d["services"] if x["id"] == "newtemper")
        self.assertEqual(new["unit"], "달러")
        self.assertEqual(new["rows"][0]["market"], "전 국가 집계")

    def test_regional_total_excluded_and_scope(self):
        source = fake_fetch("placeholder", "sidoitemtrade/getSidoitemtradeList",
                            {"strtYymm": "202608", "endYymm": "202608", "sidoCd": "31"})
        converted = cf.convert("regional", "202608", "", "31", source)
        self.assertEqual(len(converted), 2)
        self.assertEqual(converted[0][0], "87")
        bad = [dict(source[0], priodTitle="2025")]
        with self.assertRaises(ValueError):
            cf.convert("regional", "202608", "", "31", bad)

    def test_source_code_and_direction_guard(self):
        bad = [{"year": "2026.08", "impexp": "수입", "statCd": "US",
                "godsCd": "23050102", "godsKor": "자동차", "dlr": "20"}]
        with self.assertRaises(ValueError):
            cf.convert("newtemper_country", "202608", "1", "US", bad)
        bad[0]["impexp"] = "수출"
        bad[0]["statCd"] = "JP"
        with self.assertRaises(ValueError):
            cf.convert("newtemper_country", "202608", "1", "US", bad)

    def test_missing_previous_never_zero(self):
        current = {("23050102", "미국", "수출"): ("자동차 관련 부품", cf.Decimal("200"))}
        result = cf.compare("newtemper_country", current, {}, "202608")
        self.assertIsNone(result["rows"][0]["previous"])
        self.assertIsNone(result["rows"][0]["changePercent"])

    def test_duplicate_per_identity_raises(self):
        rows = [("A", "일반수출", "전국", "수출", cf.Decimal(12))] * 2
        with self.assertRaises(ValueError):
            cf.aggregate("kind", rows)

    def test_no_raw_key_exposed_when_http_error(self):
        import requests
        with patch.object(cf.requests, "get", side_effect=requests.ConnectTimeout("url=SECRET")):
            with self.assertRaisesRegex(RuntimeError, "인증키 및 URL 비공개") as e:
                cf.safe_fetch("SECRET", "kindtrade/getKindtradeList", {})
        self.assertNotIn("SECRET", str(e.exception))

    def test_missing_preceding_year_does_not_publish(self):
        def missing_prior(key, route, params):
            if params["strtYymm"].startswith("2025"):
                return []
            return fake_fetch(key, route, params)
        with self.assertRaises(ValueError):
            cf.build("placeholder", now=datetime(2026, 10, 13, tzinfo=KST),
                     fetcher=missing_prior)


if __name__ == "__main__":
    unittest.main()
