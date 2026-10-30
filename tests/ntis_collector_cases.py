"""NTIS 공식 응답 발췌를 사용한 오프라인 회귀 검사."""
import io
import re
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pre_scoop_radar as scout
import scoop_scout as scoops

FIXTURES = Path(__file__).parent / "fixtures" / "ntis"


class NtisCollectorTests(unittest.TestCase):
    def setUp(self):
        self.detail = (FIXTURES / "detail.html").read_text(encoding="utf-8")
        self.title = scout.parse_ntis_detail(self.detail)[0]
        self.now = datetime(2026, 4, 24, 10, tzinfo=scout.KST)

    def listing(self, ids=("1260364",), title=None):
        return ('<input type="hidden" id="totalCnt" value="' + str(len(ids)) + '" />' + ''.join(
            f'<a href="http://www.ntis.go.kr/rndgate/eg/un/ra/view.do?roRndUid={uid}">{title or self.title}</a>' for uid in ids))

    def run_collector(self, listing=None, detail=None, response=None, terms=("자동차",), **kwargs):
        requested = []
        def get(url, timeout=8):
            requested.append((url, timeout))
            if response:
                return response(url)
            if "ThSearch" in url:
                return (self.listing() if listing is None else listing).encode()
            return (self.detail if detail is None else detail).encode()
        with patch.object(scout, "get", side_effect=get), patch.object(scout, "datetime") as clock, \
                patch.object(scout, "NTIS_LATE_PAUSE", 0), redirect_stdout(io.StringIO()):
            clock.now.return_value = self.now
            clock.strptime = datetime.strptime
            clock.fromisoformat = datetime.fromisoformat
            clock.min = datetime.min
            rows = scout.fetch_direct_ntis_announcements(query_terms=terms, **kwargs)
        return rows, scout.DIRECT_DIAGNOSTICS["ntis-announcements"], requested

    def test_actual_detail_fields_and_body(self):
        rows, diag, _ = self.run_collector()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["published"][:10], "2026-04-23")
        self.assertEqual(rows[0]["announcementFields"]["접수일"], "2026.04.22")
        self.assertEqual(rows[0]["announcementFields"]["마감일"], "2026.05.07")
        self.assertEqual(rows[0]["announcementFields"]["공고금액"], "425 억원")
        self.assertIn("10Mbps~10Gbps", rows[0]["bodyText"])
        self.assertNotIn("공고기관명", rows[0]["summary"])
        self.assertTrue(diag["collectionComplete"])

    def test_round_robin_preserves_later_terms(self):
        terms = ("자동차", "전기차", "배터리")
        def response(url):
            if "ThSearch" in url:
                term = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["searchWord"][0]
                prefix = str(terms.index(term)+1)
                return self.listing([prefix + str(i) for i in range(10)]).encode()
            return self.detail.encode()
        rows, diag, requests = self.run_collector(response=response, terms=terms)
        self.assertEqual(len(rows), 8)
        self.assertEqual([q["detailPagesAttempted"] for q in diag["queryDiagnostics"]], [3, 3, 2])
        self.assertEqual(diag["announcementLinks"], 30)
        self.assertEqual(diag["detailsSkippedByLimit"], 22)
        self.assertFalse(diag["collectionComplete"])

    def test_retry_recovers_once_and_keeps_error_evidence(self):
        attempts = []
        def response(url):
            if "ThSearch" in url:
                return self.listing().encode()
            attempts.append(url)
            if len(attempts) == 1:
                raise urllib.error.URLError(TimeoutError("timeout"))
            return self.detail.encode()
        rows, diag, requests = self.run_collector(response=response)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(diag["retries"], 1)
        self.assertEqual(diag["httpAttempts"], 3)
        self.assertTrue(diag["errors"][0]["retry"])
        # 목록·첫 본문은 12초, 다시 받는 본문만 25초
        self.assertEqual([timeout for _, timeout in requests], [12, 12, 25])

    def test_persistent_timeout_is_bounded_and_not_empty_success(self):
        def response(url):
            if "ThSearch" in url:
                return self.listing().encode()
            raise TimeoutError("unavailable")
        rows, diag, requests = self.run_collector(response=response)
        self.assertEqual(rows, [])
        self.assertEqual(diag["httpAttempts"], 4)  # 목록 1 + 본문 2 + 끝에서 한 번 더 1
        self.assertEqual(diag["lateRetries"], 1)
        self.assertEqual(diag["detailPagesFetched"], 0)
        self.assertEqual(diag["status"], "detail_fetch_failed")
        self.assertEqual(diag["exclusions"]["detail_fetch_failed"], 1)

    def test_late_retry_recovers_and_is_not_partial(self):
        attempts = []
        def response(url):
            if "ThSearch" in url:
                return self.listing().encode()
            attempts.append(url)
            if len(attempts) <= 2:
                raise urllib.error.URLError(TimeoutError("timeout"))
            return self.detail.encode()
        rows, diag, requests = self.run_collector(response=response)
        self.assertEqual(len(rows), 1)
        self.assertEqual(diag["lateRetryOk"], 1)
        self.assertTrue(all(e["retry"] for e in diag["errors"]))
        self.assertNotIn("detail_fetch_failed", diag["exclusions"])
        self.assertEqual([t for _, t in requests], [12, 12, 25, 25])
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        import official_source_observation as obs
        self.assertNotEqual(obs._health_direct(diag), "partial")

    def test_earlier_verified_detail_is_reused_not_reread(self):
        rows, _, _ = self.run_collector()
        again, diag, requests = self.run_collector(prior_items=rows)
        self.assertEqual(again, rows)
        self.assertEqual([u for u, _ in requests if "ThSearch" not in u], [])
        self.assertEqual(diag["detailReused"], 1)

    def test_old_announcement_dates_are_remembered_not_reopened(self):
        old = self.detail.replace("2026.04.23", "2026.01.05")
        if old == self.detail:
            self.skipTest("fixture date format changed")
        rows, diag, requests = self.run_collector(detail=old)
        self.assertEqual(rows, [])
        self.assertEqual(diag["exclusions"]["outside_lookback"], 1)
        known = dict(scout.DETAIL_DATES["ntis"])
        self.assertEqual(list(known.values())[0]["d"], "2026-01-05")
        rows, diag, requests = self.run_collector(detail=old, known_dates=known)
        self.assertEqual([u for u, _ in requests if "ThSearch" not in u], [])
        self.assertEqual(diag["knownOldSkipped"], 1)
        # A changed listed title is a different document: read it again.
        changed = {u: {**v, "t": "다른제목"} for u, v in known.items()}
        _, diag, requests = self.run_collector(detail=old, known_dates=changed)
        self.assertEqual(len([u for u, _ in requests if "ThSearch" not in u]), 1)

    def test_consecutive_detail_failures_stop_and_defer(self):
        ids = tuple(str(1260364 + i) for i in range(6))
        def response(url):
            if "ThSearch" in url:
                return self.listing(ids).encode()
            raise TimeoutError("detail timeout")
        with patch.object(scout, "DETAIL_GAP_SECONDS", 0):
            rows, diag, requests = self.run_collector(response=response)
        self.assertEqual(rows, [])
        self.assertEqual(len([u for u, _ in requests if "ThSearch" not in u]), scout.DETAIL_BREAKER * 2)
        self.assertTrue(diag["detailCircuitOpen"])
        self.assertEqual(diag["detailDeferred"], 6 - scout.DETAIL_BREAKER)

    def test_403_not_retried(self):
        def response(url):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        rows, diag, requests = self.run_collector(response=response)
        self.assertEqual(len(requests), 1)
        self.assertEqual(diag["retries"], 0)
        self.assertEqual(diag["status"], "search_fetch_or_parse_failed")

    def test_official_https_id_dedup_and_host_validation(self):
        url = "http://www.ntis.go.kr/rndgate/eg/un/ra/view.do?roRndUid=1260364"
        self.assertEqual(scout._ntis_detail_url(url), url.replace("http:", "https:"))
        for bad in (url.replace("www.ntis.go.kr", "www.ntis.go.kr.evil.org"),
                    url.replace("www.ntis.go.kr", "evil.org"), url + "&roRndUid=2",
                    url.replace("1260364", "unknown")):
            self.assertEqual(scout._ntis_detail_url(bad), "")
        rows, diag, requests = self.run_collector(listing=self.listing() + self.listing().replace("http:", "https:"), terms=("자동차", "전기차"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(diag["duplicateLinks"], 3)
        self.assertTrue(all(url.startswith("https:") for url, _ in requests))

    def test_real_list_anchor_and_highlight_markup(self):
        listing = (FIXTURES / "list.html").read_text(encoding="utf-8")
        rows, diag, _ = self.run_collector(listing=listing)
        self.assertEqual(diag["announcementLinks"], 1)
        self.assertEqual(len(rows), 1)
        self.assertTrue(diag["coverageLimited"])

    def test_old_publication_not_new_because_of_deadline_or_update(self):
        self.now = datetime(2026, 10, 12, 10, tzinfo=scout.KST)
        rows, diag, _ = self.run_collector(detail=self.detail.replace("2026.05.07", "2026.10.12").replace("2026-05-17", "2026-10-12"))
        self.assertEqual(rows, [])
        self.assertEqual(diag["exclusions"]["outside_lookback"], 1)
        self.assertEqual(diag["status"], "no_recent_publications_in_checked_details")

    def test_missing_invalid_future_date_never_becomes_today(self):
        for date in ("", "2026.02.30", "2026.12.01"):
            rows, diag, _ = self.run_collector(detail=self.detail.replace("2026.04.23", date))
            self.assertEqual(rows, [])
            self.assertEqual(diag["recentRecords"], 0)

    def test_missing_body_and_login_page_are_not_documents(self):
        for markup, reason in ((self.detail.replace('class="notice_cont"', 'class="other"'), "body_missing"),
                               ("<html>로그인이 필요합니다</html>", "detail_structure_or_title_missing")):
            rows, diag, _ = self.run_collector(detail=markup)
            self.assertEqual(rows, [])
            self.assertEqual(diag["detailPagesFetched"], 1)
            self.assertEqual(diag["exclusions"][reason], 1)

    def test_missing_links_not_misreported_as_zero_results(self):
        for listing in ('<html>서비스 점검</html>', '<input id="totalCnt" value="10" />'):
            rows, diag, _ = self.run_collector(listing=listing)
            self.assertEqual(diag["searchPagesFetched"], 1)
            self.assertEqual(diag["searchPagesParsed"], 0)
            self.assertEqual(diag["status"], "search_fetch_or_parse_failed")

    def test_explicit_empty_search_is_distinct(self):
        rows, diag, requests = self.run_collector(listing='<input type="hidden" id="totalCnt" value="0" />')
        self.assertEqual(rows, [])
        self.assertEqual(diag["status"], "empty_official_search")
        self.assertEqual(diag["detailPagesAttempted"], 0)

    def test_wrong_detail_title_is_rejected(self):
        rows, diag, _ = self.run_collector(listing=self.listing(title="현대차 다른 공고 신규지원 대상과제"))
        self.assertEqual(rows, [])
        self.assertEqual(diag["exclusions"]["list_detail_title_mismatch"], 1)

    def test_observed_rd_search_index_normalization(self):
        title = self.title + "(R&D)"
        rows, diag, _ = self.run_collector(detail=self.detail.replace(self.title, title),
                                            listing=self.listing(title=self.title + "(RD)"))
        self.assertEqual(len(rows), 1)
        self.assertNotIn("list_detail_title_mismatch", diag["exclusions"])

    def test_observed_rd_before_hangul_and_quote_marks(self):
        # 10-30 탐침 실제 제목: 목록 'RD사업'·곧은 따옴표, 상세 'R&D사업'·굽은 따옴표
        pairs = [("2027년 산업기술 RD사업(디스플레이, 스마트전자, 배터리 분야) 추가 기술수요조사",
                  "2027년 산업기술 R&amp;D사업(디스플레이, 스마트전자, 배터리 분야) 추가 기술수요조사"),
                 ("국제개발협력센터[입찰재공고] 헝가리 정책자문사업: '한국-헝가리 배터리 협력연구센터 설립 지원' 용역입찰 재공고",
                  "국제개발협력센터[입찰재공고] 헝가리 정책자문사업: ‘한국-헝가리 배터리협력연구센터 설립 지원’ 용역입찰 재공고")]
        for listed, detailed in pairs:
            rows, diag, _ = self.run_collector(detail=self.detail.replace(self.title, detailed), listing=self.listing(title=listed))
            self.assertNotIn("list_detail_title_mismatch", diag["exclusions"], listed)
        self.assertNotEqual(scout._ntis_title_key("R&D사업"), scout._ntis_title_key("RFD사업"))
        self.assertEqual(scout._ntis_title_key("HR&DX 과제"), "HR&DX과제")  # 다른 낱말 속 R&D는 바꾸지 않음

    def test_unrelated_company_and_menu_do_not_become_leads(self):
        for company in ("삼성전기", "포스코퓨처엠", "포스코인터내셔널"):
            title = company + " 신규 기술개발 과제 공고"
            detail = "<nav>현대차 신규 투자</nav>" + self.detail.replace(self.title, title)
            rows, _, _ = self.run_collector(detail=detail, listing=self.listing(title=title))
            self.assertEqual(len(rows), 1)
            self.assertNotIn("현대차", rows[0]["companies"])
            leads, diag = scoops.build_lead_signals(rows, [], self.now)
            self.assertEqual(leads, [])
            self.assertEqual(diag["out_of_beat"], 1)

    def test_amount_not_invented_when_missing(self):
        detail = re.sub(r'<li>\s*<span>공고금액.*?</li>', '', self.detail, flags=re.S)
        rows, _, _ = self.run_collector(detail=detail)
        self.assertEqual(len(rows), 1)
        self.assertNotIn("공고금액", rows[0]["announcementFields"])
        self.assertNotIn("numbers", rows[0])
