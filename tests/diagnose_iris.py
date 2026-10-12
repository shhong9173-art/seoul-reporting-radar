"""IRIS만 읽기 전용으로 검증. 운영 JSON을 쓰거나 전체 수집기를 실행하지 않는다."""
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
        rows = scout.fetch_direct_iris_announcements()
    scope = [{"announcementId": row["announcementId"], "title": row["title"],
              "url": row["url"], "published": row["published"],
              "directBeatCompanies": scoops.direct_beat_company_hits(row, row["title"])} for row in rows]
    print(json.dumps({"checkedAt": datetime.now(scout.KST).isoformat(),
                      "diagnostics": scout.DIRECT_DIAGNOSTICS["iris-rnd-announcements"],
                      "retainedDirectBeatRecords": sum(bool(row["directBeatCompanies"]) for row in scope),
                      "scopeChecks": scope}, ensure_ascii=False, indent=2))
