"""Validate a DART beat snapshot without treating missing coverage as zero filings."""
import json
from datetime import datetime, timedelta
from pathlib import Path


def inspect(beat, queue):
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


if __name__ == '__main__':
    beat = json.loads(Path('digests/dart_beat_monitor_latest.json').read_text())
    queue = json.loads(Path('digests/official_event_triage_latest.json').read_text())
    print(json.dumps(inspect(beat, queue), ensure_ascii=False))
