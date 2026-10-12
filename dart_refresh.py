"""DART 장애만 격리한다. 유효한 이전 파일이 없으면 게시를 중단한다."""
import json
from datetime import datetime, timezone
from pathlib import Path
import dart_collector
import dart_numeric_extractor
from dart_health import read_payload


def run(root=Path('.'), collect=None, extract=None):
    root = Path(root)
    collect = collect or dart_collector.main
    extract = extract or dart_numeric_extractor.main
    paths = [root / 'dart.json', root / 'dart_numeric.json']
    backup = {p: p.read_bytes() if p.exists() else None for p in paths}
    stage = 'list'
    status = {'attemptedAt': datetime.now(timezone.utc).isoformat()}
    try:
        collect()
        stage = 'numeric'
        extract()
        for path in paths:
            read_payload(path)
        status.update(status='ok', stage='complete', usingPreviousData=False)
    except (SystemExit, Exception) as exc:
        # Never publish half of a new list/numeric pair or manufacture empty data.
        for path, raw in backup.items():
            if raw is None:
                path.unlink(missing_ok=True)
            else:
                temp = path.with_suffix('.json.restore')
                temp.write_bytes(raw)
                temp.replace(path)
        for path in paths:
            read_payload(path)  # missing/corrupt backup is a hard failure
        status.update(status='error', stage=stage, usingPreviousData=True,
                      error=f'{stage} refresh failed ({type(exc).__name__}); previous snapshot retained')
        print('::warning::DART 갱신 실패. 이전 자료와 장애 표시를 유지하고 정상 뉴스 갱신을 계속합니다.')
    target = root / 'dart_refresh_status.json'
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(target)
    return status


if __name__ == '__main__':
    run()
