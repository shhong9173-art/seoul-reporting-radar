"""One ledger for every KIPRIS request: count first, cap per month and group, per-group 22 wait."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from kipris_account_ledger import (KiprisAccountLedger, KiprisBudgetStop, provider_code,
                                   GROUP_LIMITS, MONTHLY_LIMIT)
from kipris_source_budget import SourceRequestBudgetExhausted

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 2, 7, 0, tzinfo=KST)
OK = b"<response><header><resultCode>00</resultCode></header><body/></response>"
LIMITED = b"<response><header><resultCode>22</resultCode><resultMsg>x</resultMsg></header></response>"


def ledger(folder, now=NOW, **kw):
    kw.setdefault("sleep", lambda _s: None)
    return KiprisAccountLedger(Path(folder) / "ledger.json", now=now,
                               legacy_path=Path(folder) / "legacy.json", **kw)


class Ledger(unittest.TestCase):
    def test_limits_fit_inside_free_tier(self):
        self.assertLessEqual(MONTHLY_LIMIT, 1000)
        self.assertLessEqual(sum(GROUP_LIMITS.values()), MONTHLY_LIMIT)
        self.assertIn("trademark", GROUP_LIMITS)

    def test_counts_before_network_and_never_stores_url(self):
        with tempfile.TemporaryDirectory() as folder:
            sent = []

            def boom(url):
                sent.append(url)
                raise TimeoutError()
            book = ledger(folder)
            with self.assertRaises(TimeoutError):
                book.fetcher("patent_claims", boom)("https://x.test/?ServiceKey=SECRET")
            self.assertEqual(len(sent), 1)
            again = ledger(folder)
            self.assertEqual(again.by_purpose["patent_claims"], 1)
            text = (Path(folder) / "ledger.json").read_text()
            self.assertNotIn("SECRET", text)
            self.assertNotIn("x.test", text)

    def test_all_patent_purposes_share_one_group_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            book = ledger(folder, monthly_limit=10, group_limits={"patent": 3, "trademark": 2, "diagnostic": 1})
            send = {p: book.fetcher(p, lambda u: OK) for p in ("patent_source", "patent_deep", "patent_claims")}
            send["patent_source"]("a"); send["patent_deep"]("b"); send["patent_claims"]("c")
            with self.assertRaises(KiprisBudgetStop) as stop:
                send["patent_source"]("d")
            self.assertEqual(stop.exception.reason, "patent_limit_reached")
            # Trademark keeps its own share even when patents ran out.
            book.fetcher("trademark", lambda u: OK)("e")
            self.assertEqual(book.remaining("trademark"), 1)
            self.assertIsInstance(stop.exception, SourceRequestBudgetExhausted)

    def test_monthly_total_and_month_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            book = ledger(folder, monthly_limit=2, group_limits={"patent": 1, "trademark": 1, "diagnostic": 0})
            book.fetcher("patent_source", lambda u: OK)("a")
            book.fetcher("trademark", lambda u: OK)("b")
            with self.assertRaises(KiprisBudgetStop):
                ledger(folder, monthly_limit=2, group_limits={"patent": 1, "trademark": 1, "diagnostic": 0}).reserve("trademark")
            december = ledger(folder, now=datetime(2026, 12, 1, 7, tzinfo=KST), monthly_limit=2,
                              group_limits={"patent": 1, "trademark": 1, "diagnostic": 0})
            self.assertEqual(december.total(), 0)
            december.reserve("trademark")

    def test_code_22_pauses_only_that_group_for_72_hours(self):
        with tempfile.TemporaryDirectory() as folder:
            book = ledger(folder)
            raw = book.fetcher("trademark", lambda u: LIMITED)("a")
            self.assertEqual(provider_code(raw), "22")
            later = ledger(folder, now=NOW + timedelta(hours=10))
            with self.assertRaises(KiprisBudgetStop) as stop:
                later.reserve("trademark")
            self.assertEqual(stop.exception.reason, "provider_22_cooldown")
            self.assertEqual(later.total(), 1)  # the refused attempt is not counted
            later.reserve("patent_source")      # a trademark problem must not stop patents
            after = ledger(folder, now=NOW + timedelta(hours=72))
            after.fetcher("trademark", lambda u: OK)("b")
            self.assertNotIn("trademark", after.public()["providerCooldown"])
            self.assertIn("trademark", after.public()["lastSuccessAt"])

    def test_patent_group_also_obeys_older_source_ledger_wait(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "legacy.json").write_text(json.dumps({
                "nextProviderProbeAt": (NOW + timedelta(hours=5)).isoformat()}))
            book = ledger(folder)
            self.assertFalse(book.should_probe("patent_deep"))
            self.assertTrue(book.should_probe("trademark"))
            self.assertTrue(book.should_probe("patent_deep", force=True))
            self.assertIn("patent", book.public()["effectiveNextProbeAt"])

    def test_damaged_ledger_stops_instead_of_resetting(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "ledger.json").write_text("{not json")
            with self.assertRaises(KiprisBudgetStop) as stop:
                ledger(folder)
            self.assertEqual(stop.exception.reason, "ledger_invalid_manual_review")
            (Path(folder) / "ledger.json").write_text(json.dumps({
                "month": "2026-11", "status": "repository_requests_counted_not_account_quota",
                "byPurpose": {"unknown": 3}}))
            with self.assertRaises(KiprisBudgetStop):
                ledger(folder)

    def test_paces_between_requests_in_one_run(self):
        with tempfile.TemporaryDirectory() as folder:
            waits = []
            book = ledger(folder, sleep=waits.append)
            send = book.fetcher("trademark", lambda u: OK)
            send("a"); send("b"); send("c")
            self.assertEqual(waits, [0.2, 0.2])

    def test_provider_code_reads_header_only(self):
        self.assertEqual(provider_code(OK), "00")
        self.assertIsNone(provider_code(b"<html>error</html>"))
        self.assertIsNone(provider_code(None))


class PatentWiring(unittest.TestCase):
    def test_patent_scripts_route_kipris_calls_through_ledger(self):
        root = Path(__file__).resolve().parents[1] / "scripts"
        for name, purpose in (("patent_hunt.py", "patent_source"),
                              ("patent_deep_hunt.py", "patent_deep"),
                              ("patent_claim_review.py", "patent_claims")):
            text = (root / name).read_text(encoding="utf-8")
            self.assertIn('fetcher("' + purpose + '"', text, name)

    def test_workflow_no_longer_calls_kipris_on_every_merge(self):
        flow = (Path(__file__).resolve().parents[1] / ".github/workflows/kipris-patent-hunt.yml").read_text(encoding="utf-8")
        head = flow.split("permissions:")[0]
        self.assertNotIn("push:", head)
        self.assertIn("group: kipris-account", flow)
        self.assertIn("kipris_account_ledger_latest.json", flow)



class ExtrasYieldToSource(unittest.TestCase):
    """11-16: 과거 제목·청구항 조회가 공보 조회 몫을 먹어 월말에 특허 감시가 통째로 멈출 뻔했다."""
    def book(self, folder, now, counts):
        Path(folder, "ledger.json").write_text(json.dumps({
            "month": now.strftime("%Y-%m"), "status": "repository_requests_counted_not_account_quota",
            "byPurpose": counts}), encoding="utf-8")
        return ledger(folder, now=now)

    def test_short_month_gives_extras_nothing_but_source_still_runs(self):
        # 실제 11-16 장부: 특허 505 · 상표 141 — 남은 10평일 공보 조회(266건)도 모자라다
        now = datetime(2026, 11, 16, 8, 33, tzinfo=KST)
        with tempfile.TemporaryDirectory() as d:
            book = self.book(d, now, {"patent_source": 305, "patent_deep": 80, "patent_claims": 120,
                                      "trademark": 141, "diagnostic": 0})
            self.assertEqual(book.extras_allowance("patent_deep"), 0)
            self.assertEqual(book.extras_allowance("patent_claims"), 0)
            self.assertEqual(book.remaining("patent_source"), 195)     # 공보 조회는 그대로 쓸 수 있다
            book.fetcher("patent_source", lambda u: OK)("a")

    def test_fresh_month_spreads_only_the_surplus(self):
        # 12-01(화) 공보 24건을 쓴 뒤: 남은 22평일·월요일 4번 몫을 떼면 96건 → 하루·용도별 2건
        now = datetime(2026, 12, 1, 8, 33, tzinfo=KST)
        with tempfile.TemporaryDirectory() as d:
            book = self.book(d, now, {"patent_source": 24, "patent_deep": 0, "patent_claims": 0,
                                      "trademark": 0, "diagnostic": 0})
            self.assertEqual(book.extras_allowance("patent_deep"), 2)
            self.assertEqual(book.extras_allowance("patent_claims"), 2)
            with self.assertRaises(ValueError):
                book.extras_allowance("patent_source")

    def test_source_is_short_in_november_but_not_in_a_fresh_month(self):
        with tempfile.TemporaryDirectory() as d:
            nov = self.book(d, datetime(2026, 11, 17, 8, 30, tzinfo=KST),
                            {"patent_source": 305, "patent_deep": 80, "patent_claims": 120,
                             "trademark": 141, "diagnostic": 0})
            self.assertTrue(nov.source_short())
            self.assertEqual(nov.source_headroom(), (195, 9, 2))
        with tempfile.TemporaryDirectory() as d:
            dec = self.book(d, datetime(2026, 12, 1, 8, 30, tzinfo=KST),
                            {"patent_source": 0, "patent_deep": 0, "patent_claims": 0,
                             "trademark": 0, "diagnostic": 0})
            self.assertFalse(dec.source_short())

    def test_run_cap_stops_before_sending(self):
        with tempfile.TemporaryDirectory() as d:
            book = ledger(d)
            sent = []
            send = book.fetcher("patent_claims", lambda u: sent.append(u) or OK, cap=2)
            send("a"); send("b")
            with self.assertRaises(KiprisBudgetStop):
                send("c")
            self.assertEqual(sent, ["a", "b"])
            self.assertEqual(book.public()["byPurpose"]["patent_claims"], 2)   # 막힌 요청은 세지 않는다
            zero = book.fetcher("patent_deep", lambda u: sent.append(u) or OK, cap=0)
            with self.assertRaises(KiprisBudgetStop):
                zero("d")
            self.assertEqual(len(sent), 2)

if __name__ == "__main__":
    unittest.main()
