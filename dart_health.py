"""현재 DART 파일의 진단만 갱신한다. 후보·기사·공개일은 변경하지 않는다."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def read_payload(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError(f"{Path(path).name}: items 목록이 없습니다")
    return payload


def refresh_health(scoop, root=Path("."), capture=False):
    root = Path(root)
    dart, numeric = read_payload(root / "dart.json"), read_payload(root / "dart_numeric.json")
    rows = numeric["items"]
    errors = dart.get("errors", [])
    health = scoop.setdefault("sourceHealth", {})
    health["dart"] = {"count": len(dart["items"]), "generatedAt": dart.get("generatedAt"),
                      "status": ("partial" if dart["items"] else "error") if errors else ("ok" if dart["items"] else "empty"),
                      "errors": errors[:3]}
    source_hash = numeric.get("sourceDartHash")
    alignment = "unverified" if not source_hash else ("current" if source_hash == fingerprint(dart) else "changed")
    health["dartNumeric"] = {
        "count": len(rows), "generatedAt": numeric.get("generatedAt"),
        "sourceAlignment": alignment,
        "withNumbers": sum(bool(row.get("numbers")) for row in rows),
        "errorCount": sum(bool(row.get("error")) for row in rows),
        "cacheFallbackCount": sum(bool(row.get("cacheFallback")) for row in rows),
        "maintenanceCount": sum("status 800" in str(row.get("error", "")).lower() or "시스템 점검" in str(row.get("error", "")) for row in rows),
        "errors": [{"company": row.get("corpName"), "report": row.get("reportName"), "error": row["error"]} for row in rows if row.get("error")][:3],
    }
    current = {"dart": fingerprint(dart), "dartNumeric": fingerprint(numeric)}
    if capture:
        scoop["dartCandidateInputs"] = current
    health["dartCandidateAlignment"] = (
        "unverified" if not scoop.get("dartCandidateInputs") else
        "current" if scoop["dartCandidateInputs"] == current else "changed")
    health["dartCheckedAt"] = datetime.now(timezone.utc).isoformat()
    return scoop


if __name__ == "__main__":
    path = Path("scoop.json")
    payload = read_payload(path)
    refresh_health(payload)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)
    print("DART 진단 갱신:", payload["sourceHealth"]["dart"]["status"],
          "/ 후보 입력 일치:", payload["sourceHealth"]["dartCandidateAlignment"])
