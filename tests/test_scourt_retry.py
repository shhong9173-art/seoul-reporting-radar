"""Supreme Court releases: a dropped connection is retried once before the page counts as failed."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pre_scoop_radar as psr  # noqa: E402

PAGE = """<table><tr><td><a href="/supreme/news/NewsViewAction.work?seqnum=1">현대제철 하도급 손해배상 사건 판결 선고</a></td>
<td>{day}</td></tr></table>"""


DETAIL_PAGE = """<table><tr><td><a href="/portal/news/NewsViewAction.work?seqnum=2">경매 임차인 통지서 전면 개선 안내</a></td>
<td>{day}</td></tr></table>"""


class Retry(unittest.TestCase):
    def run_with(self, outcomes, page=PAGE, prior=None):
        calls = []
        day = psr.datetime.now(psr.KST).strftime("%Y-%m-%d")

        def fake_get(url, timeout=8):
            calls.append((url, timeout))
            o = outcomes.pop(0) if outcomes else "ok"
            if o == "fail":
                raise TimeoutError("timed out")
            return page.format(day=day).encode()
        with patch.object(psr, "get", fake_get), patch.object(psr.time, "sleep", lambda s: None):
            psr.fetch_direct_court(max_items=1, prior_items=prior)
        return psr.DIRECT_DIAGNOSTICS["scourt-case-releases"], calls

    def test_one_failure_is_retried_with_a_longer_timeout(self):
        diag, calls = self.run_with(["fail", "ok"])
        self.assertEqual(diag["pagesFetched"], 1)
        self.assertEqual(diag["retriedOk"], 1)
        self.assertEqual(diag["errors"], [])
        self.assertEqual([t for _, t in calls[:2]], [10, 20])

    def test_two_failures_are_reported(self):
        diag, _ = self.run_with(["fail", "fail", "fail", "fail"])
        self.assertEqual(diag["pagesFetched"], 0)
        self.assertEqual(len(diag["errors"]), 2)
        self.assertIn("TimeoutError", diag["errors"][0])

    def test_detail_page_reset_is_retried(self):
        # 목록(성공) → 본문 1차 끊김 → 본문 2차 성공. 목록 두 번째 쪽은 그다음.
        diag, calls = self.run_with(["ok", "fail", "ok"], page=DETAIL_PAGE)
        self.assertEqual(diag["detailPagesAttempted"], 1)
        self.assertEqual(diag["detailPagesFetched"], 1)
        self.assertEqual(diag["retriedOk"], 1)
        self.assertEqual(diag["errors"], [])
        self.assertEqual([t for _, t in calls[1:3]], [8, 15])

    def test_detail_page_two_failures_are_reported(self):
        diag, _ = self.run_with(["ok", "fail", "fail"], page=DETAIL_PAGE)
        self.assertEqual(diag["detailPagesFetched"], 0)
        self.assertEqual(len(diag["errors"]), 1)
        self.assertTrue(diag["errors"][0].startswith("detail "))


    def test_detail_read_in_an_earlier_run_is_reused_not_reopened(self):
        day = psr.datetime.now(psr.KST).strftime("%Y-%m-%d")
        prior = [{"signalType": "supreme_court_case_release", "title": "경매 임차인 통지서 전면 개선 안내",
                  "url": "https://www.scourt.go.kr/portal/news/NewsViewAction.work?seqnum=2",
                  "published": day + "T00:00:00+09:00", "companies": [], "summary": "본문", "bodyFrom": psr.COURT_BODY}]
        diag, calls = self.run_with(["ok", "fail", "fail"], page=DETAIL_PAGE, prior=prior)
        self.assertEqual(diag["detailReused"], 1)
        self.assertEqual(diag["detailPagesAttempted"], 0)
        self.assertEqual(diag["errors"], [])
        self.assertEqual(len(calls), 1)  # 목록 한 쪽만 열고 본문은 열지 않음
        self.assertEqual(psr.DIRECT_DIAGNOSTICS["scourt-case-releases"]["retained"], 1)

    def test_changed_title_is_reopened(self):
        day = psr.datetime.now(psr.KST).strftime("%Y-%m-%d")
        prior = [{"signalType": "supreme_court_case_release", "title": "다른 제목",
                  "url": "https://www.scourt.go.kr/portal/news/NewsViewAction.work?seqnum=2", "published": day + "T00:00:00+09:00"}]
        diag, _ = self.run_with(["ok", "ok"], page=DETAIL_PAGE, prior=prior)
        self.assertEqual(diag.get("detailReused", 0), 0)
        self.assertEqual(diag["detailPagesAttempted"], 1)


# 10-31 실제 쪽 모양(메뉴 → 등록일·조회수·첨부 → 본문 → 다음글·목록 → 바닥글 법원 목록)
MENU = ("대국민서비스 대법원 각급법원 공고 주요사업 발주계획 입찰공고·계약공개 공시송달 회생·파산 공고 게시판 회생회사 M&A안내 "
        "서울고등법원 특허법원 서울회생법원 법원도서관 법원전시관 ")
def view(title, body, nxt="대법원 선고 2026도13782 특정범죄가중처벌등에관한법률위반(알선수재) 사건에 관한 보도자료"):
    return (f"<html><title>{title} - 보도자료</title><body><div>{MENU}</div><h3>{title}</h3><table><tr><th>등록일</th><td>2026-10-30</td>"
            f"<th>조회수</th><td>186</td></tr><tr><th>첨부파일</th><td>[보도자료] {title}.pdf</td></tr></table><div>{body}</div>"
            f"<table><tr><th>다음글</th><td>{nxt}</td></tr></table><a>목록</a><div>대법원 페이스북 {MENU} 개인정보처리방침</div></body></html>")


class ArticleOnly(unittest.TestCase):
    def run_list(self, title, body, prior=None):
        day = psr.datetime.now(psr.KST).strftime("%Y-%m-%d")
        lst = f'<table><tr><td><a href="/portal/news/NewsViewAction.work?seqnum=3069&gubun=6">{title}</a></td><td>{day}</td></tr></table>'
        calls = []

        def fake_get(url, timeout=8):
            calls.append(url)
            return (view(title, body) if "NewsViewAction" in url else lst).encode()
        with patch.object(psr, "get", fake_get), patch.object(psr.time, "sleep", lambda s: None):
            out = psr.fetch_direct_court(max_items=3, prior_items=prior)
        return out, calls

    def test_menu_words_do_not_keep_an_unrelated_release(self):
        out, _ = self.run_list("파키스탄 대법원장 방문",
                               "▣ 야히야 아프리디 파키스탄 대법원장을 비롯한 방문단 4인이 대한민국 대법원을 공식 방문함 ● 전자소송, AI, 스마트법원 협력 양해각서 체결")
        self.assertEqual(out, [])

    def test_industry_release_keeps_only_the_article_as_summary(self):
        out, _ = self.run_list("대법원 선고 2026도7102 중대재해처벌등에관한법률위반(산업재해치사) 사건",
                               "□ 사안의 개요 ○ 피고인 회사의 공장에서 하청 근로자가 사망한 산업재해 사건에 대하여 대법원은 원심 판결을 확정함")
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["summary"].startswith("□ 사안의 개요"))
        self.assertNotIn("회생·파산", out[0]["summary"])
        self.assertNotIn("알선수재", out[0]["summary"])  # 다음글 제목은 빠짐
        self.assertEqual(out[0]["bodyFrom"], psr.COURT_BODY)

    def test_old_cache_without_article_marker_is_read_again(self):
        title = "법원경매 기일입찰표 양식 전면 개선"
        day = psr.datetime.now(psr.KST).strftime("%Y-%m-%d")
        prior = [{"signalType": "supreme_court_case_release", "title": title, "published": day + "T00:00:00+09:00",
                  "url": "https://www.scourt.go.kr/portal/news/NewsViewAction.work?seqnum=3069&gubun=6", "summary": MENU}]
        out, calls = self.run_list(title, "○ 경매 기일입찰표를 알기 쉽게 고쳐 입찰자의 실수를 줄임", prior=prior)
        self.assertEqual(out, [])
        self.assertTrue(any("NewsViewAction" in u for u in calls))

    def test_court_article_without_view_count_is_empty(self):
        self.assertEqual(psr.court_article("메뉴 회생·파산 공고 특허법원"), "")


if __name__ == "__main__":
    unittest.main()
