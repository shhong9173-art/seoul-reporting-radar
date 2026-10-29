"""전기위원회·원안위 감시: 개최결과 PDF의 허가 사업명·구역, 출입처 그룹·해상풍력 등급, 허가대장 최근 줄, 원안위 안건·결과."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_energy_watch as k  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 29, 17, 50, tzinfo=KST)

RESULT_TEXT = """제 차 전기위원회 개최결과329 - 화 전기위원회 사무국26. 10. 13.( ) - 회의 개요 : ` 26. 10. 8.( ), 14 : 00 회의 결과 총 건 ( 25 )
ㅇ 승인 건 : 11 ㅇ 인가 건 : 4 ㅇ 허가 건 : 1 ㅇ 조건부 허가 건 : 5 ㅇ 허가 취소 건 : 1
심의 내용 승인 건 (11 ) 가시리 태양광 발전사업 등 건 준비기간 공사계획인가기간 연장 안11. 10 · ( ) 인가 건 (4 ) 1. 발전소 시운전을 고려한 안
허가 건 (1 )
1. 욕지 좌사리 해상풍력 발전사업 변경허가 안( )
조건부 허가 건 (5 )
1. 비를라카본코리아 부생가스 발전사업 허가 안 ( )
반영하여 이에 대한 사업자의 동의 여부 확인 후 조건부 허가,
포항 동백이풍력 발전사업 허가 안2. ( )
후 조건부 허가 삼척 건마람재풍력 발전사업 허가 안3. ( )
GS 당진 바이오 발전사업 허가 안4. ( )
신안 우이 해상풍력 발전사업 허가 안5. ( )
허가 취소 건 (1 ) 1. 영덕 동대산풍력 발전사업 허가 취소 안 ( )"""

LIST_HTML = ('<table><tr><td>공지</td><td><a href="#moveNoticeDetail" title="제329차 전기위원회 개최 결과"><i>제329차 전기위원회 개최 결과</i></a></td>'
             '<td>2026-10-13</td><td><a href="javascript:cf_downloadFile(\'/notice\',\'[공지]제329차 전기위원회 개최 결과_w20261013173527.pdf\');">pdf</a></td></tr>'
             '<tr><td>1</td><td><a href="#moveNoticeDetail" title="제328차 전기위원회 개최 결과">제328차</a></td><td>2026-09-09</td>'
             '<td><a href="javascript:cf_downloadFile(\'/notice\',\'[공지]제328차 전기위원회 개최 결과_w20260909134807.pdf\');">pdf</a></td></tr></table>')
NOTICE_HTML = '<a href="javascript:cf_downloadFile(\'/notice\',\'★3MW초과 발전사업허가대장(홈페이지)_3분기_w20261028094614.pdf\');">x</a>'
LEDGER_TEXT = """NO 상호(사업자) 발전소 위치 원동력 용량(MW) 허가 및변경일 공사계획인가기간 사업준비기간 기타(변경사항)
2025 1 한국동서발전 울산 남구 용잠동 300-11
BESS(배터
리) 5 2026-10-13 해당없음 2027-10-31 준비기간연장
2026 1 GS EPS(주) 충남 당진시 송악읍 부곡리 564
바이오 100 2026-09-01 2028-12-31 2027-09-01 신규
2027 1 포스코에너지(주) 인천 서구 원창동 1,000 2015-08-01 해당없음 해당없음 사업개시
(동 자료는 알림용입니다)- 860 -"""


class Resp:
    def __init__(self, text="", status=200, content=None):
        self.text, self.status_code = text, status
        self.content = content if content is not None else text.encode()


class Energy(unittest.TestCase):
    def test_meeting_sections_and_names(self):
        held, counts, items = k.meeting_items(RESULT_TEXT)
        self.assertEqual(held, "2026-10-08")
        self.assertEqual(counts["조건부 허가"], 5)
        got = {x["project"]: x["kind"] for x in items}
        self.assertEqual(got["욕지 좌사리 해상풍력 발전사업"], "변경허가")
        self.assertEqual(got["삼척 건마람재풍력 발전사업"], "조건부 허가")  # 앞 문장 '확인 후 조건부 허가' 떼어냄
        self.assertEqual(got["GS 당진 바이오 발전사업"], "조건부 허가")
        self.assertEqual(got["영덕 동대산풍력 발전사업"], "허가 취소")
        self.assertNotIn("가시리 태양광 발전사업", got)  # 승인(기간 연장) 구역은 버림
        self.assertEqual(k.group_of("GS 당진 바이오 발전사업"), "GS")
        self.assertIsNone(k.group_of("무안큐파워솔라팜 태양광 발전사업"))

    def test_ledger_recent_rows_joined_across_lines(self):
        rows = k.ledger_rows(LEDGER_TEXT, "2026-07-01")
        self.assertEqual([r["day"] for r in rows], ["2026-10-13", "2026-09-01"])
        self.assertIn("GS EPS(주) 충남 당진시", rows[1]["text"])

    def test_nssc_agenda_and_results(self):
        html = ('<p>○ 안건 : 심의∙의결 2건 - (심의∙의결 제1호) 고리 원자력발전소 3·4호기 계속운전 허가(안) - (심의∙의결 제2호) i-SMR 표준설계인가(안) '
                '○ 결과 및 안건담당자 구 분 안건 제목 결과 심의‧의결 제1호 고리 원자력발전소 3‧4호기 계속운전 허가(안) 원안의결 제2호 i-SMR 표준설계인가 ( 안 ) 보류</p>')
        md, items = k.nssc_post_items("제2026-17회(10.27) 원자력안전위원회", html)
        self.assertEqual([(x["no"], x["result"]) for x in items], [(1, "원안의결"), (2, "보류")])
        agenda_only = '<p>○ 안건 : (심의∙의결 제1호) 새울 3·4호기 운영허가(안) ○ 결과 및 안건담당자 구 분 안건 제목 결과</p>'
        _, items2 = k.nssc_post_items("제2026-18회(11.10) 원자력안전위원회", agenda_only)
        self.assertEqual(items2[0]["result"], None)
        resub = ('<p>○ 안건 : (심의∙의결 제3호) 고리 원자력발전소 3·4호기 계속운전 허가(안) ○ 결과 및 안건 담당자 구 분 안건 제목 결과 '
                 '제3호 고리 원자력발전소 3·4호기 계속운전 허가(안) 재상정 원자력안전위원회</p>')
        self.assertEqual(k.nssc_post_items("제2026-16회(10.15) 원자력안전위원회", resub)[1][0]["result"], "재상정")

    def test_run_baseline_then_new_meeting_and_result(self):
        calls = {"pdf": []}

        def get(url, headers=None, timeout=None, **kw):
            if url == k.KOREC_RESULTS:
                return Resp(LIST_HTML)
            if url == k.KOREC_NOTICES:
                return Resp(NOTICE_HTML)
            raise AssertionError(url)

        def post(url, headers=None, timeout=None, **kw):
            calls["pdf"].append(url)
            return Resp(content=b"%PDF-1.7 fake")

        texts = {"329": RESULT_TEXT, "328": RESULT_TEXT.replace("329", "328").replace("신안 우이", "부안 위도")}
        k_pdf = k.pdf_text
        k.pdf_text = lambda raw: LEDGER_TEXT if calls["pdf"] and "허가대장" in calls["pdf"][-1] or "%ED%97%88%EA%B0%80%EB%8C%80%EC%9E%A5" in calls["pdf"][-1] \
            else texts["329" if "329" in calls["pdf"][-1] else "328"]

        class Sess:
            headers = {}

            def __init__(self, posts):
                self.posts = posts

            def get(self, url, timeout=None):
                return Resp("")

            def post(self, url, data=None, timeout=None, headers=None):
                import json
                return Resp(json.dumps({"data": {"list": self.posts}}, ensure_ascii=False))
        post17 = {"SUBJECT": "제2026-17회(10.27) 원자력안전위원회", "WRITE_DATE": "2026.10.21", "BBS_SEQ": 46138,
                  "CONTENTS": "<p>○ 안건 : (심의∙의결 제1호) 고리 원자력발전소 3·4호기 계속운전 허가(안) ○ 결과 및 안건담당자 구 분 안건 제목 결과</p>"}
        try:
            first = k.run(now=NOW, previous=None, get=get, post=post, sleep=lambda s: None, nssc_session=Sess([post17]))
            self.assertEqual(first["status"], "complete")
            self.assertTrue(all(x["baseline"] and not x["isNew"] for x in first["items"]))
            ids = {x["id"]: x for x in first["items"]}
            gs = next(x for x in first["items"] if x["title"] == "GS 당진 바이오 발전사업" and x["meeting"] == "제329차")
            self.assertEqual((gs["tier"], gs["company"], gs["held"], gs["url"]), ("A", "GS", "2026-10-08", k.KOREC_RESULTS))
            wind = next(x for x in first["items"] if x["title"] == "신안 우이 해상풍력 발전사업")
            self.assertEqual(wind["tier"], "B")
            ledger = [x for x in first["items"] if x["source"] == "전기위원회 허가대장"]
            self.assertEqual([x["company"] for x in ledger], ["GS"])
            nssc = next(x for x in first["items"] if x["source"] == "원자력안전위원회")
            self.assertEqual((nssc["tier"], nssc["result"]), ("B", None))
            self.assertEqual(len(first["korecSeen"]), 2)

            # second run: the result is filled in → the item becomes new
            post17b = dict(post17, CONTENTS=post17["CONTENTS"].replace("결과</p>", "결과 심의‧의결 제1호 고리 원자력발전소 3‧4호기 계속운전 허가(안) 원안의결</p>"))
            calls["pdf"].clear()
            second = k.run(now=NOW + dt.timedelta(days=1), previous=first, get=get, post=post, sleep=lambda s: None, nssc_session=Sess([post17b]))
            self.assertEqual(calls["pdf"], [])  # same meetings and ledger file: nothing downloaded again
            n = next(x for x in second["items"] if x["source"] == "원자력안전위원회")
            self.assertEqual((n["result"], n["isNew"]), ("원안의결", True))
            self.assertIn(gs["id"], {x["id"] for x in second["items"]})
        finally:
            k.pdf_text = k_pdf

    def test_failures_are_not_zero(self):
        def bad(*a, **kw):
            return Resp("", status=503)

        class Bad:
            headers = {}

            def get(self, *a, **kw):
                raise ConnectionError("x")
        doc = k.run(now=NOW, previous={"items": [{"id": "korec:x", "firstSeen": "2026-10-01T00:00:00+09:00", "held": "2026-10-01"}]},
                    get=bad, post=bad, sleep=lambda s: None, nssc_session=Bad())
        self.assertEqual(doc["status"], "failed")
        self.assertEqual([x["id"] for x in doc["items"]], ["korec:x"])


if __name__ == "__main__":
    unittest.main()
