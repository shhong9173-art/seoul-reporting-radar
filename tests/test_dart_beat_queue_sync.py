import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from dart_beat_queue_sync import inspect, verify_official_queue_source


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


class QueueSnapshotIdentityTests(unittest.TestCase):
    def pair(self):
        stamp='2026-10-18T09:24:53+09:00'
        beat={'status':'industry_beat_official_receipt_review',
              'generatedAt':stamp}
        item={'id':'DART_FILING:20261016800823',
              'sourceSnapshotAt':stamp,
              'evidenceClass':'beat_wide_official_receipt',
              'exclusiveConfirmed':False}
        queue={'status':'official_date_triage',
               'generatedAt':'2026-10-18T16:47:00+09:00',
               'beatWideDartSourceAt':stamp,
               'feedHealth':[{'name':'dart_beat_monitor',
                              'status':'partial_issuer_coverage',
                              'sourceAt':stamp}],
               'beatAttachedReceiptIds':['DART_FILING:20261016800823'],
               'freshOfficialReview':[item],
               'backgroundReference':[],
               'confirmedScoops':0,'approvedArticles':0}
        return beat,queue

    def test_exact_original_timestamp_and_partial_source_coverage(self):
        beat,queue=self.pair()
        result=verify_official_queue_source(beat,queue)
        self.assertTrue(result['verified'])
        self.assertEqual(result['sourceAt'],beat['generatedAt'])
        self.assertEqual(result['healthStatus'],'partial_issuer_coverage')

    def test_newer_beat_without_rebuild_cannot_publish_old_queue(self):
        beat,queue=self.pair()
        beat['generatedAt']='2026-10-18T16:55:00+09:00'
        out=verify_official_queue_source(beat,queue)
        self.assertFalse(out['verified'])
        self.assertEqual(out['reason'],'source_snapshot_timestamp_mismatch')

    def test_item_level_mixed_snapshot_blocked(self):
        beat,queue=self.pair()
        queue['freshOfficialReview'][0]['sourceSnapshotAt']='2026-10-17T09:00:00+09:00'
        self.assertEqual(verify_official_queue_source(beat,queue)['reason'],
                         'mixed_source_snapshot')

    def test_failed_health_or_scoop_promotion_rejected(self):
        beat,queue=self.pair()
        queue['feedHealth'][0]['sourceAt']='2026-10-17T09:00:00+09:00'
        self.assertEqual(verify_official_queue_source(beat,queue)['reason'],
                         'feed_health_timestamp_mismatch')
        beat,queue=self.pair()
        queue['approvedArticles']=1
        self.assertEqual(verify_official_queue_source(beat,queue)['reason'],
                         'unsupported_scoop_certification')

    def test_missing_receipt_history_not_normal_zero(self):
        beat,queue=self.pair()
        queue.pop('beatAttachedReceiptIds')
        self.assertEqual(verify_official_queue_source(beat,queue)['reason'],
                         'missing_or_duplicate_receipt_history')


if __name__ == '__main__': unittest.main()
