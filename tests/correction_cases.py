import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
import dart_numeric_extractor as dart
from dart_corrections import compare_correction, public_correction_details

FIXTURES = Path(__file__).parent / 'fixtures' / 'corrections'
URL = 'https://dart.fss.or.kr/report/viewer.do?rcpNo=20261008800790&dcmNo=1'


class CorrectionTests(unittest.TestCase):
    def fixture(self, receipt):
        return (FIXTURES / (receipt+'.html')).read_text(encoding='utf-8')

    def table(self, before, after, label='계약금액(원)'):
        return f'<table><tr><td>정정항목</td><td>정정전</td><td>정정후</td></tr><tr><td>{label}</td><td>{before}</td><td>{after}</td></tr></table>'

    def test_actual_restart_schedule_is_not_zero_amount(self):
        result = compare_correction(self.fixture('20261008800790'), URL)
        change = result['changes'][0]
        self.assertEqual((change['before'], change['after']), ('-', '2026-10-12'))
        self.assertTrue(change['beforeUnspecified'])
        self.assertEqual(change['category'], 'production_schedule')
        self.assertEqual(result['correctionDate'], '2026-10-08')
        self.assertEqual(result['referencedFilingDate'], '2026-03-23')
        self.assertFalse(result['originalDocumentVerified'])
        self.assertNotIn('2,488,517,000,000', str(result['changes']))

    def test_actual_legal_text_requires_review(self):
        result = compare_correction(self.fixture('20261002800300'), URL)
        self.assertEqual(len(result['changes']), 2)
        self.assertEqual(result['referencedFilingDate'], '2025-11-28')
        self.assertEqual(result['changes'][1]['category'], 'text_review')
        self.assertIn('취소', result['changes'][1]['after'])
        self.assertNotIn('손실액', str(result['changes']))

    def test_four_column_attachment_remains_formal(self):
        result = compare_correction(self.fixture('20260929000219'), URL)
        self.assertEqual(len(result['changes']), 1)
        self.assertEqual(result['changes'][0]['category'], 'formal_review')
        self.assertIsNone(result['correctionDate'])
        self.assertEqual(result['referencedFilingDate'], '2026-09-15')

    def test_equal_values_and_whitespace_are_not_changes(self):
        result = compare_correction(self.table('A 회사', ' A   회사 '), URL)
        self.assertEqual(result['changes'], [])
        self.assertEqual(result['unchangedCount'], 1)

    def test_missing_cell_does_not_borrow_next_row(self):
        result = compare_correction(self.table('100원', ''), URL)
        self.assertEqual(result['changes'], [])
        self.assertEqual(result['skippedRows'], 1)

    def test_missing_header_and_unverified_url_rejected(self):
        self.assertEqual(compare_correction('<table><tr><td>100</td><td>200</td></tr></table>', URL)['changes'], [])
        for url in ('https://example.com/a', 'https://dart.fss.or.kr.example.com/report/viewer.do?rcpNo=20261008800790'):
            self.assertEqual(compare_correction(self.table('100','200'), url)['reason'], 'unverified_source_url')

    def test_span_and_nested_layout_are_not_guessed(self):
        markup = self.table('100','200').replace('<td>100', '<td rowspan="2">100')
        self.assertEqual(compare_correction(markup, URL)['changes'], [])
        self.assertEqual(compare_correction('<table><tr><td>'+self.table('100','200')+'</td></tr></table>', URL)['changes'], [])

    def test_amount_strings_are_preserved_without_invented_units(self):
        result = compare_correction(self.table('100','200'), URL)
        self.assertEqual(result['changes'][0]['before'], '100')
        self.assertEqual(result['changes'][0]['after'], '200')
        self.assertNotIn('delta', result['changes'][0])
        self.assertIsNone(result['correctionDate'])

    def test_viewer_integration_preserves_comparison(self):
        raw = self.fixture('20261008800790').encode()
        main = b'<script>viewDoc("20261008800790","11608769","0","0","0","HTML","");</script>'
        with patch.object(dart, 'fetch_bytes', side_effect=lambda url, timeout=10: main if 'main.do' in url else raw), patch.object(dart.time, 'sleep'):
            diag = {}
            text = dart.fetch_dart_viewer_text('20261008800790', diag)
        facts = dart.extract_viewer_facts({}, text, 'test fallback', diag)
        self.assertEqual(facts['correctionComparisons'][0]['changes'][0]['after'], '2026-10-12')

    def test_public_details_do_not_claim_exclusive_or_original_verification(self):
        comparison = compare_correction(self.table('100','200'), URL)
        details = public_correction_details({'correctionComparisons': [comparison]})
        self.assertIn('원공시 별도 대조 전·단독 아님', details[0])
        self.assertEqual(public_correction_details({}), [])

    def test_zip_path_keeps_correction_without_api_key_in_source(self):
        import io, zipfile
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('document.xml', self.table('100원','200원') + '<p>계약금액 200원</p>')
        with patch.object(dart, 'API_KEY', 'test-secret'), patch.object(dart, 'OPENDART_MAINTENANCE_SEEN', False), patch.object(dart, 'fetch_bytes', return_value=archive.getvalue()):
            result = dart.extract_document({'receiptNo':'20261008800790'})
        self.assertEqual(result['correctionComparisons'][0]['changes'][0]['after'], '200원')
        self.assertNotIn('test-secret', str(result))

    def test_public_lane_preserves_old_and_nonbeat_exclusion(self):
        from datetime import datetime
        import scoop_scout as scoop
        now = datetime(2026,10,12,tzinfo=scoop.KST)
        numeric = [{'receiptNo':'20261002800300', 'correctionComparisons': [compare_correction(self.fixture('20261002800300'),URL)]}]
        row = {'corpName':'영풍','receiptNo':'20261002800300','reportName':'[기재정정]생산중단','date':'20261002'}
        # The public lane still uses its own date window and direct-beat gate.
        current = {**row,'date':'20261011'}
        result = scoop.build_public_signals([], [current], now, numeric_rows=numeric)
        self.assertTrue(result[0]['details'])
        self.assertIn('단독 아님', result[0]['verification'])
        self.assertEqual(scoop.build_public_signals([], [{**row,'date':'20200101'}], now, numeric_rows=numeric), [])
        # LG화학은 11-01부터 출입처(석유화학) — 출입처 밖 화학사는 코오롱인더로 본다
        self.assertEqual(scoop.build_public_signals([], [{**current,'corpName':'코오롱인더'}], now, numeric_rows=numeric), [])
