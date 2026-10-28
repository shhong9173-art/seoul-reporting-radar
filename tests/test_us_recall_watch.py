"""NHTSA full recall watch: flat-file parsing, beat brands / GM Korea / Korean tires / Korean suppliers, Part 573 supplier box, baseline."""
import datetime as dt
import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import us_recall_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 28, 17, 10, tzinfo=KST)


def row(camp, make, model, year, comp, maker, rc, pot, defect, typ="V", part="Part", **kw):
    d = dict.fromkeys(w.FIELDS, "")
    d.update(RECORD_ID="1", CAMPNO=camp, MAKETXT=make, MODELTXT=model, YEARTXT=year, COMPNAME=comp, MFGNAME=maker, RCLTYPECD=typ,
             POTAFF=str(pot), RCDATE=rc, DESC_DEFECT=defect, CONEQUENCE_DEFECT="Fire risk.", CORRECTIVE_ACTION="Dealers will replace.",
             MFR_COMP_NAME=part, DO_NOT_DRIVE="No", PARK_OUTSIDE="Y" if kw.get("park") else "No")
    return "\t".join(d[f] for f in w.FIELDS)


LINES = [
    row("26V698000", "AUDI", "Q4 E-TRON", "2024", "ELECTRICAL SYSTEM:PROPULSION", "Volkswagen Group of America, Inc.", "20261021", 9048,
        "Volkswagen Group of America, Inc. (Audi) is recalling certain 2024-2025 Q4 E-Tron vehicles. The high voltage battery may fail.",
        part="High Voltage Battery Module", park=True),
    row("26V698000", "AUDI", "Q4 E-TRON", "2025", "ELECTRICAL SYSTEM:PROPULSION", "Volkswagen Group of America, Inc.", "20261021", 9048, "same"),
    row("26V700000", "KIA", "SORENTO", "2026", "STEERING", "Kia America, Inc.", "20261022", 1200, "The steering gear may fail."),
    row("26V539000", "CHEVROLET", "TRAX", "2025", "AIR BAGS", "General Motors, LLC", "20261015", 50000, "The air bag may not deploy."),
    row("26T009000", "KUMHO", "SOLUS TA31", "9999", "TIRES", "Kumho Tire U.S.A., Inc.", "20261020", 3000, "Sidewall may crack.", typ="T"),
    row("26E056000", "FORD", "ACCESSORY", "9999", "ELECTRICAL", "Ford Motor Company", "20261019", 400,
        "Cells supplied by Samsung SDI may short circuit.", typ="E"),
    row("26V600000", "TOYOTA", "CAMRY", "2026", "BRAKES", "Toyota", "20261023", 90000, "Brake booster."),          # not ours
    row("26V100000", "HYUNDAI", "TUCSON", "2025", "AIR BAGS", "Hyundai Motor America", "20260301", 100, "Old."),  # outside window
    "short\tline",
]
PART573 = b"%PDF-fake"
SAFETY = '{"results":[{"associatedDocuments":[{"fileName":"RCLRPT-26V698-3069.pdf"}]}]}'


class R:
    def __init__(self, code=200, content=b"", text="", headers=None):
        self.status_code, self.content, self.text, self.headers = code, content, text, headers or {}


def flat_zip(lines):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("FLAT_RCL_POST_2010.txt", "\n".join(lines).encode("latin-1"))
    return b.getvalue()


def fake(calls=None, flat=None, issues=SAFETY, pdf_text="Supplier Identification: Component Manufacturer Name: SK On Co., Ltd. Address: Seoul Korea Chronology: ..."):
    import pypdf  # noqa: F401  (patched below)

    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, params))
        if url == w.FLAT:
            return R(200, content=flat if flat is not None else flat_zip(LINES), headers={"Last-Modified": "Wed, 28 Oct 2026 07:05:14 GMT"})
        if url == w.ISSUES:
            return R(200, text=issues)
        if url.startswith(w.PDF_ROOT):
            return R(200, content=PART573 + pdf_text.encode())
        return R(404)
    return get


class FakeReader:
    def __init__(self, stream):
        self.pages = [type("P", (), {"extract_text": lambda self, t=stream.getvalue()[len(PART573):].decode(): t})()]


class Watch(unittest.TestCase):
    def setUp(self):
        import pypdf
        self._orig, pypdf.PdfReader = pypdf.PdfReader, FakeReader

    def tearDown(self):
        import pypdf
        pypdf.PdfReader = self._orig

    def go(self, **k):
        return w.run(now=NOW, get=fake(**{x: k.pop(x) for x in list(k) if x in ("calls", "flat", "issues", "pdf_text")}), sleep=lambda s: None, **k)

    def test_selection_and_roles(self):
        doc = self.go(issues='{"results":[]}')  # roles from the flat file only
        by = {x["campaign"]: x for x in doc["recalls"]}
        self.assertEqual(sorted(by), ["26E056000", "26T009000", "26V539000", "26V698000", "26V700000"])
        self.assertEqual(by["26V698000"]["why"][0], {"role": "제조사(출입처 브랜드)", "beat": "아우디코리아", "name": "아우디"})
        self.assertEqual((by["26V698000"]["affected"], by["26V698000"]["models"], by["26V698000"]["parkOutside"]), (9048, "Q4 E-TRON 2024~2025", True))
        self.assertEqual(by["26V539000"]["why"][0]["beat"], "한국GM")
        self.assertEqual(by["26T009000"]["why"][0], {"role": "타이어 제조사", "beat": "금호타이어", "name": "금호타이어"})
        self.assertEqual(by["26E056000"]["why"], [{"role": "부품사 이름(결함 설명, 출입처 아님)", "beat": None, "name": "삼성SDI"}])
        self.assertEqual(by["26E056000"]["beat"], [])
        self.assertEqual(by["26V698000"]["url"], "https://www.nhtsa.gov/recalls?nhtsaId=26V698")
        self.assertEqual(doc["checks"][0]["badRows"], 1)
        self.assertFalse(any(x["isNew"] for x in doc["recalls"]))  # baseline

    def test_part573_supplier_box_names_a_korean_supplier(self):
        calls = []
        doc = self.go(calls=calls)
        audi = next(x for x in doc["recalls"] if x["campaign"] == "26V698000")
        self.assertEqual(audi["report"], "https://static.nhtsa.gov/odi/rcl/2026/RCLRPT-26V698-3069.pdf")
        self.assertIn("SK On Co., Ltd.", audi["supplierBox"])
        self.assertEqual(audi["supplierKorean"], ["SK온"])
        self.assertIn({"role": "부품 공급사(원보고서, 출입처 아님)", "beat": None, "name": "SK온"}, audi["why"])
        self.assertIn(("https://api.nhtsa.gov/safetyIssues/byNhtsaId", {"filter": "recalls", "nhtsaId": "26V698000"}), calls)
        self.assertLessEqual(sum(1 for u, _ in calls if u.startswith(w.PDF_ROOT)), w.PDF_BUDGET)

    def test_reports_are_read_once_and_new_items_marked(self):
        first = self.go()
        first["recalls"] = [x for x in first["recalls"] if x["campaign"] != "26V700000"]
        calls = []
        doc = self.go(calls=calls, previous=first)
        self.assertTrue(next(x for x in doc["recalls"] if x["campaign"] == "26V700000")["isNew"])
        self.assertFalse(next(x for x in doc["recalls"] if x["campaign"] == "26V698000")["isNew"])
        self.assertNotIn(("https://api.nhtsa.gov/safetyIssues/byNhtsaId", {"filter": "recalls", "nhtsaId": "26V698000"}), calls)

    def test_missing_report_and_failures(self):
        doc = self.go(issues='{"results":[]}')
        self.assertTrue(all(x.get("reportError") == "Part 573 보고서 없음" for x in doc["recalls"] if "report" not in x))
        bad = w.run(now=NOW, get=lambda *a, **k: R(503), sleep=lambda s: None, previous={"recalls": [{"id": "nhtsa:X", "received": "2026-10-01"}]})
        self.assertEqual((bad["status"], bad["checks"][0]["error"]), ("failed", "HTTP 503"))
        self.assertEqual([x["id"] for x in bad["recalls"]], ["nhtsa:X"])  # previous result kept, not zero


if __name__ == "__main__":
    unittest.main()
