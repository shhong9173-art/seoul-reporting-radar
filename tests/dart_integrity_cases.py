import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import dart_collector as collector
import dart_numeric_extractor as numeric
from dart_health import fingerprint, refresh_health


class DartIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'dart.json'
        self.output = self.root / 'dart_numeric.json'
        self.write(self.source, {'generatedAt': '2026-10-01', 'items': [{'receiptNo': 'old'}]})
        self.write(self.output, {'items': [{'receiptNo': 'old', 'numbers': ['123원']}]})

    def write(self, path, payload):
        path.write_text(json.dumps(payload), encoding='utf-8')

    def collect(self, results=None, key='offline', corps=None):
        if corps is None:
            corps = {'A': {'corp_code': '1'}, 'B': {'corp_code': '2'}}
        results = results or {'A': {'name': 'A', 'items': []}, 'B': {'name': 'B', 'items': []}}
        with patch.object(collector, 'OUT', str(self.source)), patch.object(collector, 'API_KEY', key), patch.object(collector, 'fetch_corp_codes', return_value=corps), patch.object(collector, 'fetch_company', side_effect=lambda name, corp: results[name]), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            collector.main()

    def test_missing_key_and_corp_failure_preserve_bytes(self):
        before = self.source.read_bytes()
        for kwargs in ({'key': ''}, {'corps': {}}):
            with self.assertRaises(SystemExit):
                self.collect(**kwargs)
            self.assertEqual(self.source.read_bytes(), before)

    def test_partial_or_total_failure_preserves_previous_snapshot(self):
        before = self.source.read_bytes()
        for success in ([], [{'receiptNo': 'new'}]):
            with self.assertRaises(SystemExit):
                self.collect({'A': {'name': 'A', 'items': success}, 'B': {'name': 'B', 'items': [], 'error': 'TimeoutError'}})
            self.assertEqual(self.source.read_bytes(), before)

    def test_successful_zero_is_saved_without_old_records(self):
        self.collect()
        payload = json.loads(self.source.read_text())
        self.assertEqual(payload['items'], [])
        self.assertEqual(payload['errors'], [])
        self.assertEqual(payload['targetCorpCount'], 2)

    def test_api_013_is_valid_empty_but_malformed_000_is_error(self):
        for response, failure in (({'status': '013'}, False), ({'status': '000'}, True), ({'status': '000', 'list': [], 'total_page': 2}, True), ({'status': '800'}, True)):
            with patch.object(collector, 'get_json', return_value=response):
                result = collector.fetch_company('A', {'corp_code': '1'})
            self.assertEqual(bool(result.get('error')), failure)

    def test_request_exception_cannot_expose_key(self):
        with patch.object(collector, 'get_json', side_effect=TimeoutError('https://example?crtfc_key=secret')):
            result = collector.fetch_company('A', {'corp_code': '1'})
        self.assertEqual(result['error'], 'TimeoutError')

    def extract(self):
        with patch.object(numeric, 'IN', self.source), patch.object(numeric, 'OUT', self.output), redirect_stdout(io.StringIO()):
            numeric.main()

    def test_failed_input_preserves_numeric_bytes(self):
        before = self.output.read_bytes()
        for rows in ([], [{'receiptNo': 'partial'}]):
            self.write(self.source, {'items': rows, 'errors': [{'error': 'timeout'}]})
            with self.assertRaises(SystemExit):
                self.extract()
            self.assertEqual(self.output.read_bytes(), before)
        self.source.unlink()
        with self.assertRaises(SystemExit):
            self.extract()
        self.assertEqual(self.output.read_bytes(), before)

    def test_valid_empty_input_records_provenance(self):
        source = {'items': [], 'errors': [], 'generatedAt': '2026-10-01'}
        self.write(self.source, source)
        self.extract()
        result = json.loads(self.output.read_text())
        self.assertEqual(result['items'], [])
        self.assertEqual(result['sourceDartHash'], fingerprint(source))
        self.assertTrue(result['generatedAt'])

    def test_health_refresh_keeps_candidates_and_generation_time(self):
        scoop = {'items': [{'title': 'original'}], 'generatedAt': 'original time', 'sourceHealth': {'preScoop': {'count': 9}, 'dart': {'count': 999}}}
        refresh_health(scoop, self.root)
        self.assertEqual(scoop['items'], [{'title': 'original'}])
        self.assertEqual(scoop['generatedAt'], 'original time')
        self.assertEqual(scoop['sourceHealth']['dart']['count'], 1)
        self.assertEqual(scoop['sourceHealth']['preScoop'], {'count': 9})
        self.assertEqual(scoop['sourceHealth']['dartCandidateAlignment'], 'unverified')

    def test_snapshot_changes_detect_same_count_different_receipt(self):
        scoop = {'items': []}
        refresh_health(scoop, self.root, capture=True)
        self.assertEqual(scoop['sourceHealth']['dartCandidateAlignment'], 'current')
        self.write(self.source, {'items': [{'receiptNo': 'different'}]})
        refresh_health(scoop, self.root)
        self.assertEqual(scoop['sourceHealth']['dartCandidateAlignment'], 'changed')

    def test_numeric_provenance_detects_mismatched_input(self):
        self.write(self.output, {'items': [], 'sourceDartHash': fingerprint(json.loads(self.source.read_text()))})
        scoop = refresh_health({'items': []}, self.root)
        self.assertEqual(scoop['sourceHealth']['dartNumeric']['sourceAlignment'], 'current')
        self.write(self.source, {'items': []})
        refresh_health(scoop, self.root)
        self.assertEqual(scoop['sourceHealth']['dartNumeric']['sourceAlignment'], 'changed')

    def test_zero_and_partial_health_are_not_confused(self):
        for rows, errors, status in (([], [], 'empty'), ([], [{'error': 'timeout'}], 'error'), ([{}], [{'error': 'timeout'}], 'partial')):
            self.write(self.source, {'items': rows, 'errors': errors})
            self.assertEqual(refresh_health({'items': []}, self.root)['sourceHealth']['dart']['status'], status)

    def test_two_pages_preserve_second_page_disclosure(self):
        rows = [{'report_nm': '생산중단', 'rcept_no': str(n), 'rcept_dt': '20261012'} for n in (1, 2)]
        responses = [{'status': '000', 'page_no': n, 'total_page': 2, 'list': [rows[n-1]]} for n in (1, 2)]
        with patch.object(collector, 'get_json', side_effect=responses) as fetch:
            result = collector.fetch_company('A', {'corp_code': '1'})
        self.assertEqual([r['receiptNo'] for r in result['items']], ['1', '2'])
        self.assertIn('page_no=2', fetch.call_args_list[1].args[0])

    def test_later_page_failure_discards_partial_list(self):
        first = {'status': '000', 'total_page': 2, 'list': [{'report_nm': '생산중단'}]}
        with patch.object(collector, 'get_json', side_effect=[first, {'status': '013'}]):
            result = collector.fetch_company('A', {'corp_code': '1'})
        self.assertEqual(result['items'], [])
        self.assertIn('page 2', result['error'])

    def test_retry_recovers_timeout_and_is_bounded(self):
        with patch.object(collector, 'get_json', side_effect=[TimeoutError(), {'status': '013'}]) as fetch, patch.object(collector.time, 'sleep'):
            self.assertFalse(collector.fetch_company('A', {'corp_code': '1'}).get('error'))
            self.assertEqual(fetch.call_count, 2)
        with patch.object(collector, 'get_json', side_effect=TimeoutError()) as fetch, patch.object(collector.time, 'sleep'):
            self.assertEqual(collector.fetch_company('A', {'corp_code': '1'})['error'], 'TimeoutError')
            self.assertEqual(fetch.call_count, 2)

    def test_auth_failure_is_not_retried(self):
        with patch.object(collector, 'get_json', return_value={'status': '010'}) as fetch:
            self.assertTrue(collector.fetch_company('A', {'corp_code': '1'}).get('error'))
            self.assertEqual(fetch.call_count, 1)

    def test_page_limit_and_wrong_page_are_not_success(self):
        for pages, page in ((6, 1), (2, 5)):
            with patch.object(collector, 'get_json', return_value={'status': '000', 'list': [{}], 'total_page': pages, 'page_no': page}):
                self.assertTrue(collector.fetch_company('A', {'corp_code': '1'}).get('error'))

    def test_isolated_failure_keeps_pair_and_exposes_stale_status(self):
        from dart_refresh import run
        original = (self.source.read_bytes(), self.output.read_bytes())
        def fail():
            raise SystemExit('failed')
        with redirect_stdout(io.StringIO()):
            status = run(self.root, collect=fail, extract=lambda: self.fail('must not extract'))
        self.assertEqual(status['status'], 'error')
        self.assertEqual(original, (self.source.read_bytes(), self.output.read_bytes()))
        health = refresh_health({'items': []}, self.root)['sourceHealth']
        self.assertEqual(health['dart']['status'], 'stale')
        self.assertTrue(health['dartRefresh']['usingPreviousData'])

    def test_numeric_crash_rolls_back_new_list(self):
        from dart_refresh import run
        original = self.source.read_bytes()
        def collect():
            self.write(self.source, {'items': [{'receiptNo': 'new'}]})
        def fail():
            raise RuntimeError('secret request URL')
        with redirect_stdout(io.StringIO()):
            status = run(self.root, collect=collect, extract=fail)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(status['stage'], 'numeric')
        self.assertNotIn('secret', json.dumps(status))

    def test_missing_backup_cannot_continue_as_success(self):
        from dart_refresh import run
        self.source.unlink()
        def fail():
            raise SystemExit('failed')
        with self.assertRaises(FileNotFoundError):
            run(self.root, collect=fail, extract=lambda: None)
        self.assertFalse(self.source.exists())

    def test_success_clears_previous_failure_status(self):
        from dart_refresh import run
        self.write(self.root/'dart_refresh_status.json', {'status': 'error'})
        status = run(self.root, collect=lambda: None, extract=lambda: None)
        self.assertEqual(status['status'], 'ok')
        self.assertFalse(status['usingPreviousData'])
        self.assertEqual(refresh_health({'items': []}, self.root)['sourceHealth']['dart']['status'], 'ok')
