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

    def test_core_words_and_windows(self):
        self.assertEqual(kp.core_words("아크릴산 2-에틸헥실"), [["아크릴산"], ["2-에틸헥실", "에틸헥실"]])
        self.assertEqual(kp.core_words("무계목강관"), [["무계목강관", "무계목"]])
        cores = kp.core_words("아크릴산 2-에틸헥실")
        # 11-11 첫 실제 실행: SK이노베이션 사업보고서의 '에틸렌 아크릴산'(EAA, 다른 품목) — 낱말 하나만 겹침은 안 센다
        sk = "The Dow Chemical Company가 보유한 미국 소재 에틸렌 아크릴산 사업을 인수하면서 설립한 법인입니다."
        self.assertEqual(kp.windows(sk, cores), [])
        self.assertEqual(len(kp.windows("주요 제품은 아크릴산 2-에틸헥실(2-EHA), 부틸아크릴레이트이다.", cores)), 1)
        self.assertEqual(len(kp.windows("2-에틸헥실 아크릴레이트는 아크릴산과 2-에틸헥산올로 만든다.", cores)), 1)   # 순서가 달라도 40자 안이면
        self.assertEqual(kp.windows("아크릴산을 만든다." + "가" * 60 + "에틸헥실", cores), [])                   # 멀리 떨어지면 안 셈

    def test_attach_strict_and_redo_old_version(self):
        lists = []

        def list_fetch(url):
            lists.append(url)
            code = url.split("corp_code=")[1].split("&")[0]
            return {"status": "000", "total_page": 1, "list": [{"corp_code": code, "rcept_no": f"20260310{code[-6:]}",
                                                               "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260310"}]}

        def doc_fetch(url):
            if "20260310356361" in url:   # LG화학
                return report_zip("석유화학 부문 제품은 아크릴산 2-에틸헥실 등이다.")
            if "20260310631518" in url:   # SK이노베이션
                return report_zip("미국 소재 에틸렌 아크릴산 사업을 인수하면서 설립한 법인입니다.")
            return report_zip("주요 제품은 폴리에틸렌, 폴리프로필렌이다.")

        codes = {"LG화학": "00356361", "SK이노베이션": "00631518", "롯데케미칼": "00165413"}
        orig = kp.corp_codes
        kp.corp_codes = lambda: codes
        try:
            ev = {"id": "ktc:case:00000873", "pageId": "ktc", "ktcKind": "case", "beat": True, "product": "아크릴산 2-에틸헥실",
                  "detectedAt": "2026-11-05T16:49:00+09:00"}
            old = {"id": "ktc:case:1", "pageId": "ktc", "ktcKind": "case", "beat": True, "product": "아크릴산 2-에틸헥실", "detectedAt": "2026-08-01T00:00:00+09:00"}
            meet = {"id": "ktc:meeting:1", "pageId": "ktc", "ktcKind": "meeting", "beat": True, "product": "석도강판", "detectedAt": "2026-11-05T16:49:00+09:00"}
            # 예전 규칙(v 없음)으로 저장된 결과는 다시 본다
            prev = {"ktc": {"producers": {"ktc:case:00000873": {"caseId": "ktc:case:00000873", "checkedAt": "2026-11-11T17:40:00+09:00",
                                                                 "companies": [{"company": "SK이노베이션", "status": "found"}]}}}}
            doc = {"ktc": {"cases": []}, "events": [ev, old, meet]}
            n, m = kp.attach(doc, prev, "KEY", NOW, list_fetch=list_fetch, doc_fetch=doc_fetch)
            self.assertEqual((n, m), (1, 3))
            got = doc["ktc"]["producers"]["ktc:case:00000873"]
            self.assertEqual(got["v"], kp.EV_VERSION)
            by = {c["company"]: c for c in got["companies"]}
            self.assertEqual((by["LG화학"]["status"], by["LG화학"]["hits"]), ("found", 1))
            self.assertEqual(by["SK이노베이션"]["status"], "none")             # 다른 품목(EAA)은 안 셈
            self.assertEqual(by["롯데케미칼"]["status"], "none")
            self.assertEqual(sum(1 for c in got["companies"] if c["status"] == "no_code"), 5)
            self.assertEqual(got["line"], "품목 이름이 나온 출입처 2025 사업보고서(II. 사업의 내용): LG화학 1곳 「II. 사업의 내용 석유화학 부문 제품은 아크릴산 2-에틸헥실 등이다.」"
                                          "(접수 20260310356361) · 미확인 5곳 — 신청인 확정 아님(회사 확인)")
            # 다음 실행은 다시 받지 않는다
            lists.clear()
            doc2 = {"ktc": {"cases": []}, "events": [ev]}
            self.assertEqual(kp.attach(doc2, doc, "KEY", NOW + dt.timedelta(days=1), list_fetch=list_fetch, doc_fetch=doc_fetch), (0, 0))
            self.assertEqual(lists, [])
            # 키가 없으면 대조하지 않고 저장된 것만 넘긴다
            doc3 = {"ktc": {}, "events": [dict(ev, id="ktc:case:2")]}
            self.assertEqual(kp.attach(doc3, doc, "", NOW), (0, 0))
            self.assertNotIn("ktc:case:2", doc3["ktc"]["producers"])
            # 아무 보고서에도 품목 이름이 없으면 줄을 안 붙인다
            self.assertEqual(kp.line({"companies": [{"company": "LG화학", "status": "none"}, {"company": "X", "status": "error"}]}), "")
        finally:
            kp.corp_codes = orig

    def test_line_empty(self):
        self.assertEqual(kp.line(None), "")
        self.assertEqual(kp.line({"companies": []}), "")


if __name__ == "__main__":
    unittest.main()
