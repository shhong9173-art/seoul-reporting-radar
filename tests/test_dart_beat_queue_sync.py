import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dart_beat_queue_sync import inspect


class DARTBeatSyncTests(unittest.TestCase):
    def test_partial_coverage_and_stale_queue(self):
        b = {'sourceChecks': [{'status':'checked'}, {'status':'corp_code_unavailable'}], 'scopeCompanyCount':2, 'companiesCodeVerified':1, 'companiesUnresolved':1, 'companiesWithSourceErrors':0, 'generatedAt':'2026-10-18T09:24:53+09:00'}
        q = {'generatedAt':'2026-10-17T17:16:38+09:00'}
        x = inspect(b,q)
        self.assertEqual(x['status'], 'partial_issuer_coverage')
        self.assertTrue(x['queueOlderThanSource'])
        self.assertEqual(x['unresolved'],1)
    def test_fail_closed(self):
        self.assertEqual(inspect({},{}), {'status':'source_missing_or_malformed'})
        b = {'sourceChecks':[{'status':'checked'}], 'scopeCompanyCount':1, 'companiesCodeVerified':0, 'companiesUnresolved':0, 'companiesWithSourceErrors':0, 'generatedAt':'2026-10-18T09:24:53+09:00'}
        self.assertEqual(inspect(b,{'generatedAt':'2026-10-18T09:24:53+09:00'})['status'], 'source_missing_or_malformed')

if __name__ == '__main__': unittest.main()
