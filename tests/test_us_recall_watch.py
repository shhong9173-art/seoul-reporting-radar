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


# Supplier box text as pypdf extracts it from RCLRPT-26V698-3069.pdf (probe 10-28).
P573 = ("A technical defect may not be immediately detectable. Component Manufacturer Tier of Supplier: Supplier Type: Name: SK Battery "
        "Manufacturing Kft. Address: Irinyi János utca 9 Komárom Foreign States, 2903 Country: Hungary Involved Components Component Name 1: "
        "High Voltage Battery Module")
P573_KR = ("Component Manufacturer Tier of Supplier: Tier 1 Supplier Type: OEM Name: NIDEC MOBILITY KOREA CORPORATION Address: 790-12, "
           "Bogaewonsam-ro Gyeonggi-do Foreign States, 17507 Country: Korea, Republic Of Involved Components Component Name 1: SWITCH ASSY")


def inv(action, make, model, year, comp, opened, closed="", subject="Fire", summary="Summary.", maker="Maker", camp=""):
    return "\t".join([action, make, model, year, comp, maker, opened, closed, camp, subject, summary])


INV_LINES = [
    inv("PE26010", "HYUNDAI", "TUCSON", "2025", "ELECTRICAL", "20261020", subject="ICCU failure"),
    inv("DP26009", "BMW", "540I", "2022", "DRIVESHAFT", "20260914", "20261026"),
    inv("PE26012", "FORD", "F-150", "2025", "STEERING", "20261001", summary="Steering racks supplied by Hyundai Mobis may crack."),
    inv("EA26006", "BUICK", "ENCLAVE", "2025", "SERVICE BRAKES", "20260821"),           # not a GM Korea model
    inv("EA26007", "CHEVROLET", "TRAX", "2025", "AIR BAGS", "20260901"),               # GM Korea builds it
]


def inv_zip(lines):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("FLAT_INV.txt", "\n".join(lines).encode("utf-8"))
    return b.getvalue()


def fake(calls=None, flat=None, issues=SAFETY, pdf_text=P573, inv_lines=None):
    import pypdf  # noqa: F401  (patched below)

    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, params))
        if url == w.FLAT:
            return R(200, content=flat if flat is not None else flat_zip(LINES), headers={"Last-Modified": "Wed, 28 Oct 2026 07:05:14 GMT"})
        if url == w.ISSUES:
            return R(200, text=issues)
        if url == w.INV_FLAT:
            return R(200, content=inv_zip(INV_LINES if inv_lines is None else inv_lines))
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
        self.assertEqual(audi["supplierBox"], "SK Battery Manufacturing Kft. (Hungary)")
        self.assertEqual(audi["suppliers"], [{"name": "SK Battery Manufacturing Kft.", "country": "Hungary"}])
        self.assertEqual(audi["supplierKorean"], ["SK온"])
        self.assertIn({"role": "부품 공급사(원보고서, 출입처 아님)", "beat": None, "name": "SK온"}, audi["why"])
        self.assertIn(("https://api.nhtsa.gov/safetyIssues/byNhtsaId", {"filter": "recalls", "nhtsaId": "26V698000"}), calls)
        self.assertLessEqual(sum(1 for u, _ in calls if u.startswith(w.PDF_ROOT)), w.PDF_BUDGET)

    def test_supplier_located_in_korea_is_named_even_if_not_listed(self):
        doc = self.go(pdf_text=P573_KR)
        kia = next(x for x in doc["recalls"] if x["campaign"] == "26V700000")
        self.assertEqual(kia["supplierBox"], "NIDEC MOBILITY KOREA CORPORATION (Korea, Republic Of)")
        self.assertIn({"role": "부품 공급사(원보고서, 한국 소재)", "beat": None, "name": "NIDEC MOBILITY KOREA CORPORATION"}, kia["why"])

    def test_page_break_header_is_not_part_of_the_supplier(self):
        # 26V663 (Honda) as extracted on 10-28: the next page's form header sits between Name and Address.
        text = ("Component Manufacturer Tier of Supplier: Tier 1 Supplier Type: OEM Name: TEK CORPORATION Part 573 Safety Recall Report 26V663 "
                "The information contained in this report was submitted pursuant to 49 CFR Address: 1-2-3 Osaka Country: Japan Involved Components")
        doc = self.go(pdf_text=text)
        honda_like = next(x for x in doc["recalls"] if x["campaign"] == "26V698000")
        self.assertEqual(honda_like["suppliers"], [{"name": "TEK CORPORATION", "country": "Japan"}])

    def test_reports_are_read_once_and_new_items_marked(self):
        first = self.go()
        first["recalls"] = [x for x in first["recalls"] if x["campaign"] != "26V700000"]
        calls = []
        doc = self.go(calls=calls, previous=first)
        self.assertTrue(next(x for x in doc["recalls"] if x["campaign"] == "26V700000")["isNew"])
        self.assertFalse(next(x for x in doc["recalls"] if x["campaign"] == "26V698000")["isNew"])
        self.assertNotIn(("https://api.nhtsa.gov/safetyIssues/byNhtsaId", {"filter": "recalls", "nhtsaId": "26V698000"}), calls)
        # 원보고서는 다시 읽지 않아도 공급사 관계는 남는다(10-31 운영: 26V698000 SK온이 두 번째 실행부터 빠졌다)
        audi = next(x for x in doc["recalls"] if x["campaign"] == "26V698000")
        self.assertIn({"role": "부품 공급사(원보고서, 출입처 아님)", "beat": None, "name": "SK온"}, audi["why"])
        self.assertEqual(sum(1 for w in audi["why"] if w["name"] == "SK온"), 1)
        again = self.go(previous=doc)
        audi = next(x for x in again["recalls"] if x["campaign"] == "26V698000")
        self.assertEqual(sum(1 for w in audi["why"] if w["name"] == "SK온"), 1)

    def test_missing_report_and_failures(self):
        doc = self.go(issues='{"results":[]}')
        self.assertTrue(all(x.get("reportError") == "Part 573 보고서 없음" for x in doc["recalls"] if "report" not in x))
        bad = w.run(now=NOW, get=lambda *a, **k: R(503), sleep=lambda s: None, previous={"recalls": [{"id": "nhtsa:X", "received": "2026-10-01"}]})
        self.assertEqual((bad["status"], bad["checks"][0]["error"]), ("failed", "HTTP 503"))
        self.assertEqual([x["id"] for x in bad["recalls"]], ["nhtsa:X"])  # previous result kept, not zero


class Investigations(unittest.TestCase):
    def setUp(self):
        import pypdf
        self._r = pypdf.PdfReader
        pypdf.PdfReader = FakeReader

    def tearDown(self):
        import pypdf
        pypdf.PdfReader = self._r

    def test_beat_probes_tiers_and_baseline(self):
        first = w.run(now=NOW, previous=None, get=fake(), sleep=lambda s: None)
        got = {x["action"]: x for x in first["investigations"]}
        self.assertEqual(set(got), {"PE26010", "DP26009", "PE26012", "EA26007"})  # Enclave is not built by GM Korea
        self.assertEqual({a: x["tier"] for a, x in got.items()}, {"PE26010": "A", "DP26009": "C", "PE26012": "A", "EA26007": "A"})
        self.assertEqual(got["PE26012"]["beat"], ["현대모비스"])
        self.assertEqual((got["PE26010"]["type"], got["PE26010"]["kind"], got["PE26010"]["opened"]), ("예비조사(PE)", "조사 개시", "2026-10-20"))
        self.assertEqual(got["DP26009"]["kind"], "조사 종결")
        self.assertFalse(any(x["isNew"] for x in first["investigations"]))  # first read: baseline
        self.assertTrue(any(c["source"] == "NHTSA 결함조사(ODI)" for c in first["checks"]))
        # next day: a new probe and the Hyundai probe closed
        lines = INV_LINES + [inv("EA26008", "KIA", "EV9", "2025", "SEATS", "20261028")]
        lines[0] = inv("PE26010", "HYUNDAI", "TUCSON", "2025", "ELECTRICAL", "20261020", "20261028", subject="ICCU failure", camp="26V701000")
        second = w.run(now=NOW + dt.timedelta(days=1), previous=first, get=fake(inv_lines=lines), sleep=lambda s: None)
        new = {x["action"]: x for x in second["investigations"] if x["isNew"]}
        self.assertEqual(set(new), {"EA26008", "PE26010"})
        self.assertEqual((new["PE26010"]["kind"], new["PE26010"]["tier"], new["PE26010"]["recallCampaigns"]), ("조사 종결", "B", ["26V701000"]))
        self.assertEqual(new["EA26008"]["type"], "공학분석(EA, 격상 단계)")

    def test_investigation_file_failure_keeps_previous(self):
        first = w.run(now=NOW, previous=None, get=fake(), sleep=lambda s: None)

        def broken(url, **kw):
            return R(503) if url == w.INV_FLAT else fake()(url, **kw)
        doc = w.run(now=NOW + dt.timedelta(days=1), previous=first, get=broken, sleep=lambda s: None)
        self.assertEqual(doc["status"], "partial")
        self.assertEqual(len(doc["investigations"]), len(first["investigations"]))
        self.assertEqual(next(c for c in doc["checks"] if c["source"] == "NHTSA 결함조사(ODI)")["status"], "failed")


import nhtsa_complaints as cm  # noqa: E402


def cmpl(odino, make, model, year, comp, datea, fire="N", crash="N", injured="0", text="The car lost power while driving."):
    cells = [""] * 51
    cells[0], cells[1], cells[2], cells[3], cells[4], cells[5] = "1", odino, "Maker", make, model, year
    cells[6], cells[8], cells[9], cells[10], cells[11], cells[15], cells[19] = crash, fire, injured, "0", comp, datea, text
    return "\t".join(cells)


def cmpl_zip(lines):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("COMPLAINTS_RECEIVED_2025-2026.txt", "\n".join(lines).encode("latin-1"))
    return b.getvalue()


def day(n):
    return (dt.date(2026, 10, 28) - dt.timedelta(days=n)).strftime("%Y%m%d")


# 10-31 탐침 모양: 싼타페 하이브리드는 최근 28일 신고가 부품 세 칸에 걸쳐 튀고(한 신고가 두 칸), 투싼 엔진은 평소 수준, 쏘렌토 조향은 같은 부품 리콜 뒤
CMPL = (
    [cmpl(f"SF{i}", "HYUNDAI", "SANTA FE HYBRID", "2025", "FUEL/PROPULSION SYSTEM", day(i)) for i in range(1, 11)]
    + [cmpl(f"SF{i}", "HYUNDAI", "SANTA FE HYBRID", "2025", "POWER TRAIN", day(i)) for i in range(1, 9)]
    + [cmpl(f"SFB{i}", "HYUNDAI", "SANTA FE HYBRID", "2025", "FUEL/PROPULSION SYSTEM", day(40 + 12 * i)) for i in range(12)]
    + [cmpl(f"TU{i}", "HYUNDAI", "TUCSON", "2022", "ENGINE", day(i * 2 + 1)) for i in range(10)]
    + [cmpl(f"TUB{i}", "HYUNDAI", "TUCSON", "2022", "ENGINE", day(30 + 3 * i)) for i in range(55)]
    + [cmpl(f"SO{i}", "KIA", "SORENTO", "2026", "STEERING", day(i), crash="Y" if i < 2 else "N") for i in range(1, 10)]
    + [cmpl(f"FD{i}", "FORD", "ESCAPE", "2025", "ENGINE", day(i)) for i in range(1, 30)]             # 출입처 아님
    + [cmpl(f"TV{i}", "CHEVROLET", "TRAX", "2025", "ELECTRICAL SYSTEM", day(i), fire="Y") for i in range(1, 5)]  # 한국GM 화재 몰림
    + ["short\tline"])
RECALL_ROWS = [dict(CAMPNO="26V700000", MAKETXT="KIA", MODELTXT="SORENTO", RCDATE="20261022", COMPNAME="STEERING:GEAR BOX")]


def cget(blob=None, status=200):
    def get(url, headers=None, timeout=None):
        if "2025-2026" in url:
            return R(status, content=blob if blob is not None else cmpl_zip(CMPL), headers={"Last-Modified": "Fri, 30 Oct 2026 09:24:41 GMT"})
        return R(404)
    return get


class Complaints(unittest.TestCase):
    def test_spikes_by_model_with_recall_overlap_and_fire(self):
        doc, check = cm.collect(NOW, None, RECALL_ROWS, get=cget())
        self.assertEqual((check["status"], doc["files"], doc["window"]), ("ok", ["2025-2026"], ["2026-09-29", "2026-10-27"]))
        by = {x["model"]: x for x in doc["spikes"]}
        self.assertEqual(set(by), {"SANTA FE HYBRID", "SORENTO", "TRAX"})  # 투싼(평소 수준)·포드(출입처 아님) 없음
        sf = by["SANTA FE HYBRID"]
        self.assertEqual((sf["brand"], sf["complaints"], sf["tier"], sf["years"]), ("현대차", 10, "B", "2025(10)"))
        self.assertEqual([(p["component"], p["recent"], p["baselinePer28"]) for p in sf["parts"]],
                         [("FUEL/PROPULSION SYSTEM", 10, 2.0), ("POWER TRAIN", 8, 0.0)])
        self.assertEqual(sf["url"], "https://api.nhtsa.gov/complaints/complaintsByVehicle?make=HYUNDAI&model=SANTA%20FE%20HYBRID&modelYear=2025")
        self.assertEqual(len(sf["samples"]), 3)
        so = by["SORENTO"]
        self.assertEqual((so["tier"], so["sameComponentRecall"], so["crash"]), ("C", ["26V700000"], 1))  # 같은 부품 리콜 뒤
        tv = by["TRAX"]
        self.assertEqual((tv["beat"], tv["fire"], tv["parts"][0]["component"]), ("한국GM", 4, "화재 신고(FIRE=Y)"))
        self.assertFalse(any(x["isNew"] for x in doc["spikes"]))  # 첫 실행은 신규 표시 안 함

    def test_continuing_spike_keeps_first_seen_and_failure_keeps_previous(self):
        first, _ = cm.collect(NOW, None, RECALL_ROWS, get=cget())
        second, _ = cm.collect(NOW + dt.timedelta(days=1), first, RECALL_ROWS, get=cget())
        sf = next(x for x in second["spikes"] if x["model"] == "SANTA FE HYBRID")
        self.assertEqual((sf["firstSeen"], sf["isNew"]), (first["spikes"][0]["firstSeen"], False))
        down, check = cm.collect(NOW + dt.timedelta(days=2), second, RECALL_ROWS, get=cget(status=503))
        self.assertEqual(check["status"], "failed")
        self.assertEqual(len(down["spikes"]), len(second["spikes"]))
        self.assertTrue(down["stale"])

    def test_text_excerpt_is_short_and_utf8_repaired(self):
        self.assertEqual(cm.short("doesn\u00e2\u0080\u0099t   work"), "doesn\u2019t work")
        self.assertLessEqual(len(cm.short("word " * 200)), 222)

    def test_file_spans_cover_the_baseline(self):
        self.assertEqual(cm.spans(NOW), ["2025-2026", "2026-2027"])
        self.assertEqual(cm.spans(dt.datetime(2027, 2, 1, tzinfo=KST)), ["2025-2026", "2026-2027", "2027-2028"])


if __name__ == "__main__":
    unittest.main()
