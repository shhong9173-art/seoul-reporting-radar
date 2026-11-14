"""호주 사건 공개기록 본문: 기자 컴퓨터가 올린 PDF를 레이더에서 받아 한국·출입처 대목을 남기고 칸을 비운다(레이더·pdftotext는 가짜)."""
import base64
import datetime as dt
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import au_epr_cases as a  # noqa: E402
import au_epr_docs as d  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 16, 9, 10, tzinfo=KST)
TEXT = ("BlueScope Steel Limited submission\n1. Introduction\nBlueScope submits that a particular market situation (PMS) exists in the Korean hot-rolled coil (HRC) market such that sales in that\n"
        "market are not suitable for determining normal values. The Commission should construct normal values\nfor KG Dongbu Steel Co., Ltd using a competitive benchmark for HRC costs.\n"
        "Table of contents ........................ 2\nThe Vietnamese exporter Hoa Sen Group cooperated. The weather was fine in Canberra on that day.\n"
        "KG Dongbu's dumping margin of 2.1% in the SEF understates the true level of dumping. POSCO supplies HRC to KG Dongbu at market prices.\n\fPage 2\n")


def section():
    doc = lambda no, typ, title, date, firms=None: {"no": no, "type": typ, "title": title, "date": date, "url": f"{a.HOST}/sites/default/files/atrc/{no}.pdf",
                                                    **({"companies": firms} if firms else {})}
    return {"status": "ok", "baselineAt": "2026-11-15T02:27:00+09:00", "cases": {"698": {
        "commodity": "Aluminium zinc coated steel (≥600mm)", "kind": "Continuation", "url": a.INDEX + "/698", "firstSeen": "2026-11-15T02:27:00+09:00", "companies": ["KG스틸"],
        "docs": [doc("18", "Submission", "Exporter - KG Dongbu Steel Co Ltd - Final submission", "2026-11-16", ["KG스틸"]),
                 doc("13", "Submission", "Australian Industry - BlueScope Steel Limited - Submission on PMS in the Korean HRC market and response to KG Dongbu submission", "2026-09-15", ["KG스틸"]),
                 doc("11", "Verification Report", "Exporter - KG Dongbu - Findings of Verification Report", "2026-09-01", ["KG스틸"])]}}, "pdf": {}, "want": []}


class Resp:
    def __init__(self, body=None, status=200):
        self._b, self.status_code = body, status

    def json(self):
        return self._b


class Radar:
    """레이더의 /ingest/browser-files 흉내."""
    def __init__(self, files, parts):
        self.files, self.parts, self.done, self.calls = files, parts, None, []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append(params)
        if not params:
            return Resp({"files": self.files})
        got = self.parts.get((params["slot"], params["part"]))
        return Resp({"b64": got}) if got is not None else Resp(status=404)

    def post(self, url, json=None, headers=None, timeout=None):
        self.done = json["done"]
        return Resp({"cleared": len(self.done)})


def b64parts(data, n):
    s = base64.b64encode(data).decode()
    size = -(-len(s) // n)
    return [s[i:i + size] for i in range(0, len(s), size)]


PDF_BYTES = b"%PDF-1.7 fake " + bytes(range(256)) * 20


class Docs(unittest.TestCase):
    def test_excerpts_pick_korea_and_beat_sentences_with_issue_words_first(self):
        got = d.excerpts(TEXT)
        self.assertEqual(got["hits"], 4)
        self.assertEqual(got["excerpts"][0], "Introduction BlueScope submits that a particular market situation (PMS) exists in the Korean hot-rolled coil (HRC) market such that sales in that "
                                             "market are not suitable for determining normal values.")
        self.assertIn("The Commission should construct normal values for KG Dongbu Steel Co., Ltd using a competitive benchmark for HRC costs.", got["excerpts"])
        self.assertFalse(any("Hoa Sen" in x or "weather" in x or "....." in x for x in got["excerpts"]))
        self.assertEqual(got["margins"], ["dumping margin of 2.1%"])
        long = "Korea " + "word " * 100 + "particular market situation."
        self.assertTrue(d.excerpts(long)["excerpts"][0].endswith(" …"))
        self.assertLessEqual(len(d.excerpts(long)["excerpts"][0]), d.EXCERPT_CHARS)
        self.assertEqual(d.excerpts("Nothing relevant here at all, only general remarks about procedure."), {"excerpts": [], "margins": [], "hits": 0})

    def test_read_files_stores_excerpts_clears_slots_and_alerts_only_for_documents_after_the_baseline(self):
        sec = section()
        p1, p2 = b64parts(PDF_BYTES, 2), b64parts(PDF_BYTES, 1)
        radar = Radar([{"slot": "a", "key": "698-13", "parts": 2, "complete": True}, {"slot": "b", "key": "698-18", "parts": 1, "complete": True},
                       {"slot": "c", "key": "698-11", "parts": 2, "complete": False}, {"slot": "d", "key": "123-9", "parts": 1, "complete": True}],
                      {("a", 0): p1[0], ("a", 1): p1[1], ("b", 0): p2[0]})
        seen, events = [], []
        extract = lambda data: (seen.append(data) or (9, TEXT))
        counts = d.read_files(sec, "x" * 40, NOW, events=events, get=radar.get, post=radar.post, extract=extract)
        self.assertEqual(counts, {"waiting": 1, "read": 2, "failed": 0, "scan": 0, "cleared": 3, "events": 1})
        self.assertEqual(seen, [PDF_BYTES, PDF_BYTES])                       # 조각을 이어 붙여 원래 파일로
        self.assertEqual(radar.done, ["a", "b", "d"])                        # 다 받은 칸만 비운다(문서 줄에 없는 파일도 비운다), 덜 올라온 칸은 둔다
        rec = sec["pdf"]["698-13"]
        self.assertEqual((rec["v"], rec["pages"], rec["hits"], rec["date"], rec["margins"]), (a.PDF_VERSION, 9, 4, "2026-09-15", ["dumping margin of 2.1%"]))
        self.assertIn("particular market situation (PMS)", rec["excerpts"][0])
        # 기준선(11-15) 전에 나온 문서의 본문은 화면에만, 기준선 뒤 문서(11-16)는 B로 한 번
        self.assertEqual([(e["id"], e["tier"], e["companies"]) for e in events], [("au-epr:698:text:18", "B", ["KG스틸"])])
        self.assertIn("본문 읽음 — EPR 18번 Submission 「Exporter - KG Dongbu Steel Co Ltd - Final submission」(2026-11-16, 9쪽): 한국·출입처 이름이 든 문장 4개. 첫 대목: \"Introduction BlueScope submits", events[0]["text"])
        # 읽은 문서는 다시 달라고 하지 않는다(덜 올라온 698-11만 남는다)
        self.assertEqual([w["key"] for w in sec["want"]], ["698-11"])

    def test_bad_files_are_counted_and_retried(self):
        sec = section()
        radar = Radar([{"slot": "a", "key": "698-13", "parts": 1, "complete": True}, {"slot": "b", "key": "698-11", "parts": 2, "complete": True}],
                      {("a", 0): base64.b64encode(b"<html>not a pdf</html>").decode(), ("b", 0): "AAAA"})   # b의 둘째 조각이 없다
        counts = d.read_files(sec, "x" * 40, NOW, get=radar.get, post=radar.post, extract=lambda data: (1, TEXT))
        self.assertEqual((counts["read"], counts["failed"], counts["cleared"]), (0, 2, 2))
        self.assertEqual((sec["pdf"]["698-13"]["error"], sec["pdf"]["698-13"]["tries"], sec["pdf"]["698-11"]["error"]), ("PDF 아님", 1, "조각 HTTP 404"))
        self.assertEqual(sorted(w["key"] for w in sec["want"]), ["698-11", "698-13", "698-18"])      # 다시 받아 달라고 한다
        # 글자가 거의 없는 PDF는 스캔본으로 적는다(대목 없음, 다시 달라고 하지 않는다)
        radar2 = Radar([{"slot": "a", "key": "698-13", "parts": 1, "complete": True}], {("a", 0): base64.b64encode(PDF_BYTES).decode()})
        counts = d.read_files(sec, "x" * 40, NOW, get=radar2.get, post=radar2.post, extract=lambda data: (3, " \f \f "))
        self.assertEqual((counts["read"], counts["scan"], sec["pdf"]["698-13"]["scan"], sec["pdf"]["698-13"]["excerpts"]), (1, 1, True, []))
        self.assertNotIn("698-13", [w["key"] for w in sec["want"]])
        # 레이더가 목록을 안 주면 예외(감시는 경고만 남긴다)
        with self.assertRaises(RuntimeError):
            d.read_files(sec, "x" * 40, NOW, get=lambda *a_, **k: Resp(status=503), post=radar.post)

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext 없음")
    def test_pdf_text_with_poppler(self):
        from tests.test_edis_watch import pdf
        pages, text = d.pdf_text(pdf([["Submission", "A particular market situation exists in the Korean HRC market."], ["Second page"]]))
        self.assertEqual(pages, 2)
        self.assertIn("particular market situation exists in the Korean HRC market", text)


if __name__ == "__main__":
    unittest.main()
