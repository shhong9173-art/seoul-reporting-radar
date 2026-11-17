import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import dart_text_prewarm as p  # noqa: E402


class Resp:
    def __init__(self, status=200, content=b"", data=None):
        self.status_code, self.content, self._data = status, content, data

    def json(self):
        return self._data


def zip_of(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text, enc in files:
            z.writestr(name, text.encode(enc))
    return buf.getvalue()


class Prewarm(unittest.TestCase):
    def test_text_matches_worker_rules_plus_dart_cells(self):
        xml = ("<?xml version='1.0'?><DOCUMENT><TITLE>분기보고서</TITLE><P>4분기는 여수공장 정기보수&amp;비용</P>"
               "<TABLE><TR><TE>구분</TE><TU>금액</TU></TR><TR><TD>NPG</TD><TD>1,234</TD></TR></TABLE><!-- 주석 --></DOCUMENT>")
        self.assertEqual(p.html_to_text(xml), "분기보고서\n4분기는 여수공장 정기보수&비용\n구분 | 금액 |\nNPG | 1,234 |")

    def test_targets_only_this_period_ok_reports(self):
        doc = {"period": {"year": 2026, "report": "11014"}, "companies": {
            "LG화학": {"status": "ok", "period": "202611014", "rcept": "20261116000765"},
            "롯데케미칼": {"status": "pending", "period": "202611012", "rcept": None},
            "한화솔루션": {"status": "ok", "period": "202611012", "rcept": "20260814000111"},   # 앞 기간
            "같은 접수": {"status": "ok", "period": "202611014", "rcept": "20261116000765"}}}
        self.assertEqual(p.targets(doc), ["20261116000765"])

    def test_run_skips_stored_waits_on_014_and_keeps_budget(self):
        doc = {"period": {"year": 2026, "report": "11014"}, "companies": {
            f"c{i}": {"status": "ok", "period": "202611014", "rcept": f"2026111600000{i}"} for i in range(4)}}
        posted = []

        def get(url, params=None, **kw):
            if url.endswith("/ingest/dart-text"):
                return Resp(200, data={"have": params["rcp"] == "20261116000000"})
            rcp = params["rcept_no"]
            if rcp == "20261116000001":
                return Resp(200, zip_of([("a.xml", "<P>작은 첨부</P>", "utf-8"), ("b.xml", "<P>본문 " + "가" * 50 + "</P>", "cp949")]))
            return Resp(200, b"<result><status>014</status></result>")

        def post(url, data=None, **kw):
            posted.append(json.loads(data.decode("utf-8")))
            return Resp(200)

        c = p.run("k", "t" * 43, get=get, post=post, sleep=lambda s: None, budget=2, notes_doc=doc)
        self.assertEqual({k: c[k] for k in ("targets", "had", "put", "waiting", "failed", "left")},
                         {"targets": 4, "had": 1, "put": 1, "waiting": 1, "failed": 0, "left": 1})
        self.assertEqual(posted[0]["schema"], "dart_text/v1")
        self.assertEqual(posted[0]["rcp"], "20261116000001")
        self.assertEqual([f["name"] for f in posted[0]["files"]], ["b.xml", "a.xml"])   # 큰 파일 먼저, cp949도 읽는다
        self.assertTrue(posted[0]["files"][0]["text"].startswith("본문 가"))


if __name__ == "__main__":
    unittest.main()
