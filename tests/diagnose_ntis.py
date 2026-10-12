"""NTIS만 읽기 전용 실행. 예: python tests/diagnose_ntis.py 철강 변압기 전력망"""
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pre_scoop_radar as scout
import scoop_scout as scoops


if __name__ == "__main__":
    with redirect_stdout(io.StringIO()):
        rows = scout.fetch_direct_ntis_announcements(query_terms=sys.argv[1:] or None)
    print(json.dumps({"checkedAt": datetime.now(scout.KST).isoformat(),
                      "diagnostics": scout.DIRECT_DIAGNOSTICS["ntis-announcements"],
                      "scopeChecks": [{"title": row["title"], "url": row["url"],
                                       "published": row["published"],
                                       "directBeatCompanies": scoops.direct_beat_company_hits(row, row["title"])} for row in rows]},
                     ensure_ascii=False, indent=2))
