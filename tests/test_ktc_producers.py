import datetime as dt
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ktc_producers as kp  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 11, 7, 40, tzinfo=KST)


def report_zip(body):
    """사업보고서 원문 꼴: SECTION-1 'II. 사업의 내용'."""
    markup = ('<SECTION-1><TITLE>I. 회사의 개요</TITLE><P>개요</P></SECTION-1>'
              f'<SECTION-1><TITLE>II. 사업의 내용</TITLE><P>{body}</P></SECTION-1>'
              '<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE><P>아크릴산 재무</P></SECTION-1>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("report.xml", markup)
    return buf.getvalue()


class Producers(unittest.TestCase):
    def test_tokens_and_group(self):
        self.assertEqual(kp.tokens("아크릴산 2-에틸헥실"), ["2-에틸헥실", "아크릴산", "에틸헥실"])
        self.assertEqual(kp.tokens("중국, 미국, 말레이시아산 아크릴산 2-에틸헥실"), ["2-에틸헥실", "아크릴산", "에틸헥실"])   # 나라·'…산' 뺌
        self.assertEqual(kp.tokens("무계목강관"), ["무계목강관", "무계목"])
        self.assertEqual(kp.group_of("아크릴산 2-에틸헥실"), "화학")
        self.assertEqual(kp.group_of("무계목강관"), "철강")
        self.assertIsNone(kp.group_of("외장형 모뎀 연결장치"))
        self.assertEqual(kp.report_year(NOW), 2025)
        self.assertEqual(kp.report_year(dt.datetime(2026, 3, 1, tzinfo=KST)), 2024)

    def test_attach_finds_report_words_once(self):
        lists, docs = [], []

        def list_fetch(url):
            lists.append(url)
            code = url.split("corp_code=")[1].split("&")[0]
            return {"status": "000", "total_page": 1, "list": [{"corp_code": code, "rcept_no": f"2026031{code[-4:]}0001"[:14].ljust(14, "0"),
                                                               "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260310"}]}

        def doc_fetch(url):
            docs.append(url)
            if "00356361" in url or url.endswith(lg_receipt):
                return report_zip("석유화학 부문 주요 제품은 에틸렌, 프로필렌, 아크릴산 및 고흡수성수지이며 아크릴산은 여수에서 생산한다.")
            if "boom" in url:
                raise RuntimeError("x")
            return report_zip("주요 제품은 폴리에틸렌, 폴리프로필렌이다.")

        lg_receipt = None
        codes = {"LG화학": "00356361", "롯데케미칼": "00165413"}
        orig = kp.corp_codes
        kp.corp_codes = lambda: codes
        try:
            ev = {"id": "ktc:case:00000873", "pageId": "ktc", "ktcKind": "case", "beat": True, "product": "아크릴산 2-에틸헥실",
                  "detectedAt": "2026-11-05T16:49:00+09:00"}
            old = {"id": "ktc:case:1", "pageId": "ktc", "ktcKind": "case", "beat": True, "product": "아크릴산 2-에틸헥실", "detectedAt": "2026-08-01T00:00:00+09:00"}
            meet = {"id": "ktc:meeting:1", "pageId": "ktc", "ktcKind": "meeting", "beat": True, "product": "석도강판", "detectedAt": "2026-11-05T16:49:00+09:00"}
            doc = {"ktc": {"cases": []}, "events": [ev, old, meet]}
            # 문서 받을 때 접수번호가 주소에 실리므로 LG화학 접수번호를 미리 계산
            lg_receipt = list_fetch("x?corp_code=00356361&")["list"][0]["rcept_no"]
            lists.clear()
            n, m = kp.attach(doc, None, "KEY", NOW, list_fetch=list_fetch, doc_fetch=doc_fetch)
            self.assertEqual((n, m), (1, 2))                      # 새 조사 1건(45일 넘은 것·회의는 뺌), 보고서는 고유번호 있는 2곳만 받음
            got = doc["ktc"]["producers"]["ktc:case:00000873"]
            lg = next(c for c in got["companies"] if c["company"] == "LG화학")
            self.assertEqual((lg["status"], lg["hits"]), ("found", {"아크릴산": 2}))   # 'III. 재무'의 아크릴산은 안 셈
            self.assertIn("아크릴산 및 고흡수성수지", lg["snippets"][0])
            lotte = next(c for c in got["companies"] if c["company"] == "롯데케미칼")
            self.assertEqual(lotte["status"], "none")
            self.assertEqual(sum(1 for c in got["companies"] if c["status"] == "no_code"), 6)
            line = kp.line(got)
            self.assertEqual(got["line"], line)
            self.assertTrue(line.startswith("출입처 2025 사업보고서(II. 사업의 내용) 품목 낱말 대조[2-에틸헥실, 아크릴산, 에틸헥실]: LG화학 '아크릴산' 2곳 「"))
            self.assertIn("낱말 없음 1곳(롯데케미칼) — 안 만든다는 뜻 아님", line)
            self.assertIn("미확인 6곳(", line)
            self.assertTrue(line.endswith("— 신청인 확정 아님(회사 확인)"))
            # 다음 실행은 다시 받지 않는다
            lists.clear()
            doc2 = {"ktc": {"cases": []}, "events": [ev]}
            self.assertEqual(kp.attach(doc2, doc, "KEY", NOW + dt.timedelta(days=1), list_fetch=list_fetch, doc_fetch=doc_fetch), (0, 0))
            self.assertEqual(lists, [])
            self.assertIn("ktc:case:00000873", doc2["ktc"]["producers"])
            # 키가 없으면 대조하지 않고 저장된 것만 넘긴다
            doc3 = {"ktc": {}, "events": [dict(ev, id="ktc:case:2")]}
            self.assertEqual(kp.attach(doc3, doc, "", NOW), (0, 0))
            self.assertNotIn("ktc:case:2", doc3["ktc"]["producers"])
        finally:
            kp.corp_codes = orig

    def test_line_empty(self):
        self.assertEqual(kp.line(None), "")
        self.assertEqual(kp.line({"companies": []}), "")


if __name__ == "__main__":
    unittest.main()
