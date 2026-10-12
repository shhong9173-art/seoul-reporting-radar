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
