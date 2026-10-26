"""Offline regression checks for the standalone reporter digest toolkit."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dart_watch
import customs
import news_check

class ReporterKitTests(unittest.TestCase):
    def test_watchlist_scoped_to_reporting_beats(self):
        names = {s.strip() for s in (ROOT / "watchlist.txt").read_text(encoding="utf-8").splitlines()
                 if s.strip() and not s.startswith(("#", "["))}
        for unrelated in ("풍산", "가온전선", "제룡전기", "삼성전기", "포스코퓨처엠"):
            self.assertNotIn(unrelated, names)
        for tracked in ("현대자동차", "기아", "현대제철", "고려아연", "두산에너빌리티"):
            self.assertIn(tracked, names)

    def test_flag_not_claiming_exclusive(self):
        self.assertEqual(dart_watch.flag_of("단일판매ㆍ공급계약체결")[0], "★수주")
        self.assertEqual(dart_watch.flag_of("신규시설투자등")[0], "★증설")
        self.assertEqual(dart_watch.flag_of("분기보고서")[1], 9)
        content=(ROOT/"scripts/dart_watch.py").read_text(encoding="utf-8")
        self.assertIn("공개자료·단독 아님", content)
        self.assertIn("latest.json", content)

    def test_ambiguous_same_name_not_guessed(self):
        self.assertIsNone(dart_watch.pick_code({"LS": [["00000001",""],["00000002",""]]}, "LS"))
        self.assertEqual(dart_watch.pick_code({"LS": [["00000001",""],["00000002","006260"]]}, "LS"),"00000002")
        self.assertIsNone(dart_watch.pick_code({}, "NOT_FOUND"))

    def test_customs_month_chunks(self):
        self.assertEqual(list(customs.chunks("202501","202602")), [("202501","202512"),("202601","202602")])
        self.assertEqual(customs.month_add("202512",1), "202601")

    def test_customs_invalid_numbers_must_not_be_zero(self):
        self.assertEqual(customs.num("0"), 0.0)
        for invalid in ("", "not-a-number", None):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    customs.num(invalid)

    def test_news_check_requires_explicit_credentials(self):
        with patch.dict("os.environ", {"NAVER_CLIENT_ID":"","NAVER_CLIENT_SECRET":""}):
            with patch.object(sys,"argv",["news_check.py","현대차"]):
                with self.assertRaises(SystemExit):
                    news_check.main()

    def test_original_receipt_url(self):
        row={"group":"자동차","corp_name":"기아","report_nm":"단일판매ㆍ공급계약체결","rcept_dt":"20261012","rcept_no":"20261012000123","tag":"★수주","new":True}
        self.assertIn("rcpNo=20261012000123",dart_watch._line(row))

class DartWatchRetry(unittest.TestCase):
    def test_transient_status_is_retried_then_succeeds(self):
        calls = []
        class R:
            def __init__(self, body, code=200): self.body, self.status_code = body, code
            def raise_for_status(self): pass
            def json(self): return self.body
        answers = [R({"status": "800", "message": "점검"}), R({}, 503),
                   R({"status": "000", "total_page": 1, "list": [{"rcept_no": "1"}]})]
        def get(url, params, timeout):
            calls.append(params["page_no"]); return answers.pop(0)
        self.assertEqual(dart_watch.filings("k", "00000001", "20261020", "20261026", get=get, sleep=lambda s: None),
                         [{"rcept_no": "1"}])
        self.assertEqual(len(calls), 3)

    def test_persistent_failure_raises_without_key(self):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"status": "020", "message": "요청 제한 초과"}
        with self.assertRaises(dart_watch.TransientDartError) as ctx:
            dart_watch.filings("SECRETKEY", "00000001", "20261020", "20261026", get=lambda *a, **k: R(), sleep=lambda s: None)
        self.assertNotIn("SECRETKEY", str(ctx.exception))
        self.assertIn("020", str(ctx.exception))

    def test_no_result_is_zero_not_failure(self):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"status": "013", "message": "조회된 데이타가 없습니다."}
        self.assertEqual(dart_watch.filings("k", "00000001", "20261020", "20261026", get=lambda *a, **k: R(), sleep=lambda s: None), [])


if __name__=="__main__":
    unittest.main()
