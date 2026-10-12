"""공식 DART 실패 원문 재현 및 단위/행 경계 회귀 테스트."""
import io
import json
import tempfile
import unittest
import warnings
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import dart_numeric_extractor as dart

FIXTURES = Path(__file__).parent / "fixtures" / "dart"


class DartTableTests(unittest.TestCase):
    def raw(self, receipt):
        return (FIXTURES / (receipt + ".html")).read_bytes()

    def test_actual_revenue_and_suspension_tables(self):
        expected = {
            "20261008800790": ["2,488,517,000,000원", "48,916,104,472,005원", "5.09%"],
            "20261002800300": ["1,009,604,903,616원", "2,787,414,358,375원", "36.22%"],
            "20260929800197": ["117,947,181,460원", "2,009,429,144,163원", "5.87%"],
        }
        for receipt, values in expected.items():
            facts = dart.extract_table_facts(self.raw(receipt))
            self.assertEqual([f["formatted"] for f in facts], values)
            self.assertTrue(all("손실액" in f["interpretation"] for f in facts))
            self.assertTrue(all(f["unitSource"] == "field_heading" for f in facts))

    def test_actual_table_level_unit_and_separate_labels(self):
        facts = dart.extract_table_facts(self.raw("20260921000219"))
        self.assertEqual([f["formatted"] for f in facts], ["297억원", "297억원"])
        self.assertEqual(len({f["label"] for f in facts}), 2)
        self.assertTrue(all(f["unitSource"] == "table_unit" for f in facts))

    def test_no_amount_attachment_is_not_a_parser_failure(self):
        raw = self.raw("20260929000219")
        result = dart.extract_viewer_facts({"reportName": "[첨부정정]주요사항보고서"},
                                          dart.html_to_text(raw), "OpenDART status 014", {})
        self.assertEqual(result["numbers"], [])
        self.assertEqual(result["numericFacts"], [])
        self.assertEqual(result["extractionStatus"], "attachment_correction_without_numeric_facts")
        self.assertEqual(result["error"], "")
        self.assertEqual(result["upstreamError"], "OpenDART status 014")

    def test_unknown_empty_document_not_claimed_as_attachment(self):
        result = dart.extract_viewer_facts({"reportName": "[첨부정정]주요사항보고서"},
                                          "문서가 없거나 조회가 불가능합니다", "fetch issue", {})
        self.assertTrue(result["error"])
        self.assertEqual(result["extractionStatus"], "no_target_values_in_readable_document")

    def table(self, label, value):
        return f"<TABLE><TR><TD>{label}</TD><TD>{value}</TD></TR></TABLE>"

    def test_dash_or_missing_cell_cannot_borrow_next_row(self):
        raw = ('<TABLE><TR><TD>출자금액(원)</TD><TD>-</TD></TR>'
               '<TR><TD>이사회결의일</TD><TD>2026-10-12</TD></TR></TABLE>').encode()
        self.assertEqual(dart.extract_table_facts(raw), [])

    def test_unknown_unit_unknown_label_and_date_are_rejected(self):
        for label, value in (("출자금액", "297"), ("연락처(원)", "297"),
                             ("출자금액(원)", "2026-10-12"), ("출자금액(%)", "297")):
            self.assertEqual(dart.extract_table_facts(self.table(label, value).encode()), [])

    def test_unit_cannot_leak_to_second_table_or_across_prose(self):
        unit = '<TABLE><TR><TD>(단위 : 억 원)</TD></TR></TABLE>'
        first = self.table("출자금액", "297")
        second = self.table("출자금액", "123")
        facts = dart.extract_table_facts((unit + first + second).encode())
        self.assertEqual([f["formatted"] for f in facts], ["297억원"])
        self.assertEqual(dart.extract_table_facts((unit + '<p>별도 설명</p>' + first).encode()), [])
        self.assertEqual(dart.extract_table_facts(first.encode()), [])

    def test_local_unit_overrides_table_unit(self):
        raw = ('<TABLE><TR><TD>(단위 : 억 원)</TD></TR></TABLE>' + self.table("출자금액(원)", "297")).encode()
        self.assertEqual([f["formatted"] for f in dart.extract_table_facts(raw)], ["297원"])

    def test_mixed_table_units_are_not_guessed(self):
        raw = ('<TABLE><TR><TD>(단위 : 억원, %)</TD></TR><TR><TD>출자금액</TD><TD>297</TD></TR></TABLE>').encode()
        self.assertEqual(dart.extract_table_facts(raw), [])

    def test_zip_path_uses_same_table_evidence(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("official.xml", self.raw("20260921000219"))
        with patch.object(dart, "API_KEY", "offline-test"), patch.object(dart, "OPENDART_MAINTENANCE_SEEN", False), patch.object(dart, "fetch_bytes", return_value=archive.getvalue()):
            result = dart.extract_document({"receiptNo": "20260921000219"})
        self.assertEqual(result["numbers"], ["297억원"])
        self.assertEqual(result["numericFacts"][0]["documentName"], "official.xml")
        self.assertEqual(result["extractionStatus"], "numeric_facts_extracted")

    def test_viewer_records_source_and_toc_diagnostics_without_warning(self):
        receipt = "20261008800790"
        main = (f'<script>node1["rcpNo"]="{receipt}";'
                f'viewDoc("{receipt}","11608769","0","0","0","HTML","");</script>').encode()
        def fetch(url, timeout=12):
            return main if "main.do" in url else self.raw(receipt)
        with patch.object(dart, "fetch_bytes", side_effect=fetch), patch.object(dart.time, "sleep"), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            diag = {}
            text = dart.fetch_dart_viewer_text(receipt, diag)
        self.assertFalse(any(issubclass(w.category, FutureWarning) for w in caught))
        self.assertEqual(diag["tocAssignmentCount"], 1)
        self.assertTrue(diag["numericTableFacts"][0]["sourceUrl"].startswith("https://dart.fss.or.kr/report/viewer.do?"))
        result = dart.extract_viewer_facts({}, text, "upstream unavailable", diag)
        self.assertIn("2,488,517,000,000원", result["numbers"])

    def test_attachment_without_numbers_does_not_reuse_old_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            inp, out = Path(directory)/"dart.json", Path(directory)/"dart_numeric.json"
            inp.write_text(json.dumps({"items": [{"receiptNo": "20260929000219"}]}))
            out.write_text(json.dumps({"items": [{"receiptNo": "20260929000219", "numbers": ["999억원"]}]}))
            row = {"receiptNo": "20260929000219", "numbers": [], "snippets": [], "error": "",
                   "viewerFallbackDiagnostics": {"attempted": True}, "extractionStatus": "attachment_correction_without_numeric_facts"}
            with patch.object(dart, "IN", inp), patch.object(dart, "OUT", out), patch.object(dart, "extract_document", return_value=row), redirect_stdout(io.StringIO()):
                dart.main()
            result = json.loads(out.read_text())['items'][0]
            self.assertEqual(result["numbers"], [])
            self.assertFalse(result.get("cacheFallback"))
