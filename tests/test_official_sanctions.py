import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import kr_exec_market as km  # noqa: E402
import official_sanctions as osn  # noqa: E402

NOW = dt.datetime(2026, 11, 5, 5, 50)


def fss_page(rows):
    trs = "".join(f'<tr><td>{n}</td><td>{org}</td><td>{d}</td><td><a href="/fss/job/openInfo/view.do?menuNo=200476&amp;pageIndex=1&amp;examMgmtNo={k}&amp;emOpenSeq=1">내용보기</a></td>'
                  f'<td>보험검사3국</td><td>10</td></tr>' for n, org, d, k in rows)
    return "<table><tr><th>번호</th><th>제재대상기관</th></tr>" + trs + "</table>"


class R:
    def __init__(self, text="", content=b"", status=200):
        self.text, self.content, self.status_code = text, content, status


# 탐침 180 공개안 PDF 글자(가상 회사로 바꿈)
PDF = ("제재내용 공개안\n1. 금융기관명 : 한빛카드㈜\n2. 제재조치일 : 2021. 10. 26.\n3. 제재조치내용\n대상 내용\n기 관 기관경고, 과태료 53억 1,110만원 부과\n"
       "임 원 주의적 경고 : 2명\n직 원 등\n감봉 : 2명\n4. 제재대상사실\n가. 문책사항\n(1) 신용정보 관리 소홀 한빛카드㈜ 前 대표이사 등은")
PDF_NONE = ("제재내용 공개안\n1. 금융기관명 : 오성보험대리점㈜\n2. 제재조치일 : 2026. 10. 26.\n3. 제재조치내용\n대상 내용\n기 관 해당사항 없음\n임 원 해당사항 없음\n"
            "직 원 등 (보험설계사) 업무정지 90일 : 1명\n4. 제재대상사실\n가. 문책사항")
# 탐침 181 결과의 공표 PDF 글자(가상 회사)
PIPC = ("개인정보보호법 위반 행정처분 결과 공표 … 순번 위반행위를 한 자 위반행위의 내용 행정처분의 내용 및 결과 명칭 위반조항 위반내용 처분일자 처분내용 "
        "1 ㈜한빛카드 舊 보호법*제29조 안전조치의무 2024. 3. 18. 과징금 7,088만원과태료 360만원 2 ㈜서울오성티브이 舊 보호법* 제29조 안전조치의무 2024. 3. 18. "
        "과징금 2,225만원과태료 420만원 舊 보호법* 제39조의4 제1항 개인정보 유출등의 통지·신고에 대한 특례 2024. 3. 18. 과태료 부과 360만원 "
        "* 舊 보호법 : 2020. 8. 5. 시행, 법률 제16930호 2024년 3월 18일 개 인 정 보 보 호 위 원 회")


class Parse(unittest.TestCase):
    def test_fss_rows_and_summary(self):
        rows = osn.fss_rows(fss_page([(310, "인카금융서비스㈜", "20261104", "202400672"), (309, "한빛카드주식회사", "20211026", "202100001")]))
        self.assertEqual(rows[0], {"id": "fss:202400672-1", "org": "인카금융서비스㈜", "date": "2026-11-04"})
        self.assertIn("examMgmtNo=202100001&emOpenSeq=1", osn.fss_url(rows[1]["id"]))
        s = osn.fss_summary(PDF)
        self.assertEqual(s["inst"], "기관경고, 과태료 53억 1,110만원 부과")
        self.assertEqual(s["exec"], "주의적 경고 : 2명")
        self.assertTrue(s["execSanctioned"] and s["ceoMentioned"])
        n = osn.fss_summary(PDF_NONE)
        self.assertFalse(n["execSanctioned"])

    def test_pipc_rows(self):
        rows = osn.pipc_rows(PIPC)
        self.assertEqual([(r["org"], r["date"], r["major"]) for r in rows], [("한빛카드", "2024-03-18", True), ("서울오성티브이", "2024-03-18", True)])
        self.assertEqual(rows[0]["inst"], "과징금 7,088만원, 과태료 360만원")
        self.assertEqual(rows[0]["what"], "안전조치의무")

    def test_org_keys_read_latin(self):
        self.assertTrue(osn.org_keys("KB증권") & osn.org_keys("케이비증권 주식회사"))
        self.assertTrue(osn.org_keys("DB손해보험") & osn.org_keys("DB손해보험주식회사"))
        self.assertFalse(osn.org_keys("한빛카드") & osn.org_keys("한빛카드캐피탈"))

    def test_top_roles(self):
        got = osn.top_roles("(2015~2018) 한빛증권 대표이사 사장 / 前) 현대자동차 사장 / KB자산 대표이사 사장 오성증권 대표이사 / 現) 디비손보 대표이사(2024~현재)",
                            km.segments, now=NOW)
        self.assertEqual([(r["org"], r["start"], r["end"]) for r in got],
                         [("한빛증권", 2015, 2018), ("현대자동차", None, None), ("KB자산", None, None), ("오성증권", None, None), ("디비손보", 2024, 2026)])
        self.assertEqual(osn.top_roles("現) 한국경영학회 회장 / 現) 법무법인 율촌 대표", km.segments, now=NOW), [])

    def test_match_timing(self):
        roles = [{"org": "한빛카드", "role": "대표이사", "start": 2019, "end": 2021, "current": False, "seg": ""},
                 {"org": "오성증권", "role": "사장", "start": None, "end": None, "current": False, "seg": ""}]
        recs = [{"id": "a", "agency": "금감원", "org": "한빛카드주식회사", "date": "2023-05-01"},     # 끝+2년 안
                {"id": "b", "agency": "금감원", "org": "한빛카드㈜", "date": "2024-05-01"},          # 끝+3년 — 뺀다
                {"id": "c", "agency": "금감원", "org": "한빛카드", "date": "2018-12-01"},            # 시작 전 — 뺀다
                {"id": "d", "agency": "금감원", "org": "오성증권㈜", "date": "2020-01-01"}]
        got = {(m["record"]["id"], m["timing"]) for m in osn.match(roles, recs)}
        self.assertEqual(got, {("a", "overlap"), ("d", "timing_unknown")})


class Refresh(unittest.TestCase):
    def test_fss_new_then_backfill_and_failure_keeps_state(self):
        pages = {1: [(3, "새회사", "20261104", "3")], 2: [(2, "중간", "20201010", "2")], 3: [(1, "옛회사", "20160105", "1")], 4: []}
        calls = []

        def get(url, **kw):
            n = int(url.rsplit("pageIndex=", 1)[1])
            calls.append(n)
            return R(fss_page(pages[n]))
        st, c = osn.refresh_fss(None, get=get, now=NOW, backfill_pages=10, new_pages=2)
        self.assertEqual((c["status"], c["rows"], st["done"]), ("ok", 3, True))
        pages[1] = [(4, "더새회사", "20261105", "4")] + pages[1]
        calls.clear()
        st2, c2 = osn.refresh_fss(st, get=get, now=NOW, new_pages=3)
        self.assertEqual((c2["new"], c2["rows"], calls), (1, 4, [1]))          # 아는 줄이 나오면 멈추고, 채우기 끝났으면 뒤쪽 안 봄

        def boom(url, **kw):
            raise TimeoutError()
        st3, c3 = osn.refresh_fss(st2, get=boom, now=NOW)
        self.assertEqual((c3["status"], c3["rows"]), ("partial", 4))           # 실패는 앞 상태 유지(0건 아님)

    def test_pipc_reads_only_new_posts(self):
        listing = '<a href="/np/cop/bbs/selectBoardArticle.do?bbsId=BS258&amp;mCode=C010040000&amp;nttId=12608">공표</a>'
        view = "<a href=\"javascript:fn_egov_downFileCnv('FILE_1','0','pdf')\">다운로드</a>"
        calls = []

        def get(url, **kw):
            calls.append(url)
            if "selectBoardList" in url:
                return R(listing if url.endswith("pageIndex=1") else "")
            if "selectBoardArticle" in url:
                return R(view)
            return R(content=b"%PDF-1.4 fake")
        st, c = osn.refresh_pipc(None, get=get, now=NOW, read_pdf=lambda raw, pages: PIPC)
        self.assertEqual((c["posts"], c["rows"]), (1, 2))
        self.assertEqual(osn.pipc_records(st)[0]["id"], "pipc:12608:1")
        calls.clear()
        osn.refresh_pipc(st, get=get, now=NOW, read_pdf=lambda raw, pages: PIPC)
        self.assertFalse(any("FileDown" in u for u in calls))                   # 이미 읽은 글은 다시 안 읽는다


if __name__ == "__main__":
    unittest.main()
