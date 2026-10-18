"""Validate a DART beat snapshot without treating missing coverage as zero filings."""
import json
from datetime import datetime, timedelta
from pathlib import Path


def inspect(beat, queue):
    if not isinstance(beat, dict):
        return {'status': 'source_missing_or_malformed'}
    checks = beat.get('sourceChecks')
    if not isinstance(checks, list) or not isinstance(queue, dict):
        return {'status': 'source_missing_or_malformed'}
    scope = beat.get('scopeCompanyCount')
    if not isinstance(scope, int) or len(checks) != scope:
        return {'status': 'source_missing_or_malformed'}
    checked = sum(isinstance(x, dict) and x.get('status') == 'checked' for x in checks)
    unresolved = sum(isinstance(x, dict) and x.get('status') == 'corp_code_unavailable' for x in checks)
    failures = scope - checked - unresolved
    if checked != beat.get('companiesCodeVerified') or unresolved != beat.get('companiesUnresolved') or failures != beat.get('companiesWithSourceErrors'):
        return {'status': 'source_missing_or_malformed'}
    stamp = beat.get('generatedAt')
    try:
        generated = datetime.fromisoformat(stamp)
        queue_at = datetime.fromisoformat(queue['generatedAt'])
        if generated.utcoffset() is None or queue_at.utcoffset() is None:
            raise ValueError('naive timestamp')
    except (ValueError, TypeError, KeyError):
        return {'status': 'source_missing_or_malformed'}
    return {'status': 'partial_collection' if failures else 'partial_issuer_coverage' if unresolved else 'checked_source', 'sourceAt': stamp, 'queueAt': queue['generatedAt'], 'queueOlderThanSource': queue_at < generated, 'scope': scope, 'checked': checked, 'unresolved': unresolved, 'failures': failures, 'warning': 'First observed public filing is not an exclusive scoop.'}


def verify_official_queue_source(beat, queue):
    """Fail closed when queue publication lags the exact official DART source."""
    if (not isinstance(beat, dict) or not isinstance(queue, dict)
        or beat.get('status') != 'industry_beat_official_receipt_review'
        or queue.get('status') != 'official_date_triage'):
        return {'verified': False, 'reason': 'schema_or_source_missing'}
    src = beat.get('generatedAt')
    output = queue.get('generatedAt')
    if (not isinstance(src, str) or queue.get('beatWideDartSourceAt') != src):
        return {'verified': False, 'reason': 'source_snapshot_timestamp_mismatch'}
    try:
        beat_time = datetime.fromisoformat(src)
        queue_time = datetime.fromisoformat(output)
        if beat_time.utcoffset() is None or queue_time.utcoffset() is None:
            raise ValueError('naive timestamp')
        if queue_time < beat_time or queue_time > datetime.now(beat_time.tzinfo) + timedelta(minutes=10):
            return {'verified': False, 'reason': 'queue_generation_time_invalid'}
    except (TypeError, ValueError):
        return {'verified': False, 'reason': 'invalid_timestamp'}
    feeds = queue.get('feedHealth')
    if not isinstance(feeds, list):
        return {'verified': False, 'reason': 'missing_feed_health'}
    matching = [x for x in feeds if isinstance(x, dict) and x.get('name') == 'dart_beat_monitor']
    if len(matching) != 1 or matching[0].get('sourceAt') != src:
        return {'verified': False, 'reason': 'feed_health_timestamp_mismatch'}
    receipts = queue.get('beatAttachedReceiptIds')
    if (not isinstance(receipts, list) or
        any(not isinstance(x, str) or not x.startswith('DART_FILING:') for x in receipts)
        or len(receipts) != len(set(receipts))):
        return {'verified': False, 'reason': 'missing_or_duplicate_receipt_history'}
    if queue.get('confirmedScoops') != 0 or queue.get('approvedArticles') != 0:
        return {'verified': False, 'reason': 'unsupported_scoop_certification'}
    for x in queue.get('freshOfficialReview', []) + queue.get('backgroundReference', []):
        if not isinstance(x, dict) or x.get('exclusiveConfirmed') is not False:
            return {'verified': False, 'reason': 'unverified_editorial_item'}
        if (x.get('evidenceClass') == 'beat_wide_official_receipt'
            and x.get('sourceSnapshotAt') != src):
            return {'verified': False, 'reason': 'mixed_source_snapshot'}
    return {'verified': True, 'sourceAt': src,
            'queueAt': output, 'attachedReceipts': len(receipts),
            'healthStatus': matching[0].get('status'),
            'warning': 'Public filings only; no exclusives verified.'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-official-queue-sync', action='store_true')
    args = parser.parse_args()
    beat = json.loads(Path('digests/dart_beat_monitor_latest.json').read_text())
    queue = json.loads(Path('digests/official_event_triage_latest.json').read_text())
    result = (verify_official_queue_source(beat, queue)
              if args.require_official_queue_sync else inspect(beat, queue))
    print(json.dumps(result, ensure_ascii=False))
    if args.require_official_queue_sync and not result['verified']:
        raise SystemExit(1)
