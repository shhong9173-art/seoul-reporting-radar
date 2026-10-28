"""EPA certification watch: new IDs only after the baseline, new model / EV range change / carryover."""
import csv
import datetime as dt
import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import us_epa_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 29, 6, 20, tzinfo=KST)
COLS = ["id", "make", "model", "baseModel", "year", "atvType", "range", "comb08", "createdOn", "VClass", "drive", "trany", "evMotor"]


def row(i, make, model, year, atv="", rng="0", created="Wed Sep 16 00:00:00 EDT 2026", base=None):
    return {"id": str(i), "make": make, "model": model, "baseModel": base or model, "year": str(year), "atvType": atv, "range": rng, "comb08": "30",
            "createdOn": created, "VClass": "Small SUV", "drive": "All-Wheel Drive", "trany": "Automatic", "evMotor": ""}


BASE = [row(1, "Kia", "Sorento AWD", 2026, base="Sorento"), row(2, "Hyundai", "Ioniq 5", 2025, "EV", "303", base="Ioniq 5"),
        row(3, "Toyota", "Camry", 2026)]


def zipped(rows):
    s = io.StringIO()
    wr = csv.DictWriter(s, fieldnames=COLS)
    wr.writeheader()
    wr.writerows(rows)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("vehicles.csv", s.getvalue().encode("latin-1"))
    return b.getvalue()


class R:
    def __init__(self, code=200, content=b""):
        self.status_code, self.content, self.headers = code, content, {"Last-Modified": "Tue, 29 Sep 2026 19:47:00 GMT"}


def go(rows, previous=None, code=200):
    return w.run(now=NOW, previous=previous, get=lambda *a, **k: R(code, zipped(rows)))


class Epa(unittest.TestCase):
    def test_baseline_then_new_entries_classified(self):
        first = go(BASE)
        self.assertEqual((first["vehicles"], first["checks"][0]["rows"]), ([], 2))  # baseline; Toyota ignored
        rows = BASE + [row(4, "Kia", "Sorento Hybrid AWD", 2027, base="Sorento"),
                       row(5, "Hyundai", "Ioniq 5", 2026, "EV", "318", "Mon Oct 26 00:00:00 EDT 2026", base="Ioniq 5"),
                       row(6, "Genesis", "GV90 AWD", 2027, "EV", "300", "Tue Oct 27 00:00:00 EDT 2026", base="GV90")]
        doc = go(rows, previous=first)
        by = {v["id"]: v for v in doc["vehicles"]}
        self.assertEqual(by["epa:6"]["kind"], "새 모델")
        self.assertEqual((by["epa:6"]["company"], by["epa:6"]["created"], by["epa:6"]["range"]), ("제네시스", "2026-10-27", 300))
        self.assertEqual(by["epa:5"]["kind"], "주행거리 변화")
        self.assertEqual(by["epa:5"]["compare"], {"previousYear": 2025, "previousRanges": [303]})
        self.assertEqual(by["epa:4"]["kind"], "연식 변경")
        self.assertTrue(all(v["isNew"] for v in doc["vehicles"]))
        again = go(rows, previous=doc)
        self.assertFalse(any(v["isNew"] for v in again["vehicles"]))
        self.assertEqual(len(again["vehicles"]), 3)

    def test_failure_keeps_previous(self):
        prev = {"vehicles": [{"id": "epa:9", "created": "2026-10-01", "firstSeen": "2026-10-01T06:20:00+09:00"}], "seenIds": ["9"]}
        doc = go(BASE, previous=prev, code=503)
        self.assertEqual((doc["status"], doc["checks"][0]["error"]), ("failed", "HTTP 503"))
        self.assertEqual([v["id"] for v in doc["vehicles"]], ["epa:9"])

    def test_created_dates(self):
        self.assertEqual(w.created("Wed Sep 16 00:00:00 EDT 2026"), "2026-09-16")
        self.assertIsNone(w.created("bad"))


if __name__ == "__main__":
    unittest.main()
