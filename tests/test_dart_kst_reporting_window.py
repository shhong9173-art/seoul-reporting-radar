"""Prevent OpenDART Korean publication dates falling behind UTC midnight."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import dart_collector as d


class DartKstDateWindow(unittest.TestCase):
    def test_korean_midnight_in_previous_utc_day(self):
        when=datetime(2026,10,17,15,30,tzinfo=timezone.utc)
        begin,end=d.official_dart_date_window(now=when,lookback_days=30)
        self.assertEqual(end.isoformat(),"2026-10-18")
        self.assertEqual(begin.isoformat(),"2026-09-18")

    def test_two_calendar_days_separated_across_local_midnight(self):
        before=datetime(2026,10,17,14,59,tzinfo=timezone.utc)
        after=datetime(2026,10,17,15,1,tzinfo=timezone.utc)
        self.assertEqual(d.official_dart_date_window(now=before)[1].isoformat(),
                         "2026-10-17")
        self.assertEqual(d.official_dart_date_window(now=after)[1].isoformat(),
                         "2026-10-18")

    def test_local_evening_and_utc_day_match(self):
        when=datetime(2026,10,18,12,1,tzinfo=timezone.utc)
        self.assertEqual(d.official_dart_date_window(now=when)[1].isoformat(),
                         "2026-10-18")

    def test_naive_datetime_or_invalid_days_rejected(self):
        with self.assertRaises(ValueError):
            d.official_dart_date_window(now=datetime(2026,10,18,1))
        for days in (0,-1,366):
            with self.assertRaises(ValueError):
                d.official_dart_date_window(
                    now=datetime(2026,10,18,1,tzinfo=timezone.utc),
                    lookback_days=days)

    def test_fetch_company_queries_dart_kst_date_not_utc(self):
        calls=[]
        def getter(url):
            calls.append(url)
            return {"status":"013"}
        class FixedUTC(datetime):
            @classmethod
            def now(cls,tz=None):
                instant=datetime(2026,10,17,15,30,tzinfo=timezone.utc)
                return instant.astimezone(tz) if tz else instant
        with patch.object(d,"datetime",FixedUTC),patch.object(d,"get_json",getter):
            result=d.fetch_company("KG스틸",{"corp_code":"00115676"})
        self.assertEqual(result["items"],[])
        self.assertTrue(calls)
        from urllib.parse import parse_qs,urlsplit
        params=parse_qs(urlsplit(calls[0]).query)
        self.assertEqual(params["end_de"],["20261018"])
        self.assertEqual(params["bgn_de"],["20260918"])
        self.assertEqual(params["corp_code"],["00115676"])


if __name__=="__main__":
    unittest.main()
