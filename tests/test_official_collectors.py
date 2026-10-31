"""Offline regression checks for public-source parsers; no network or secrets required."""
from beat_identity_cases import BeatIdentityTests
import sys
import json
import io
import unittest
import urllib.error
import urllib.parse
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from correction_cases import CorrectionTests
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dart_integrity_cases import DartIntegrityTests
import dart_numeric_extractor as dart
from dart_table_cases import DartTableTests
import pre_scoop_radar as scout
import scoop_scout as scoops
from ntis_collector_cases import NtisCollectorTests


class CollectorRegressionTests(unittest.TestCase):
    def test_employee_stock_grants_are_not_scoop_candidates(self):
        # 10-30 운영 원문(DART 주요사항보고서(자기주식처분결정)) 발췌
        mobis = ("자기주식 처분 결정 1. 처분예정주식(주) 보통주식 96,136 3. 처분예정금액(원) 보통주식 33,936,008,000 "
                 "5. 처분목적 2026년 단체교섭에 따른 회사주식 지급 6. 처분방법 기 타(주) 96,136 7. 처분상대방 회사 직원")
        kia = ("3. 처분예정금액(원) 보통주식 190,011,916,800 5. 처분목적 2026년 임금협상 결과에 따른 회사주식 지급 "
               "7. 처분상대방 당사 직원 30,916명")
        self.assertTrue(scoops.employee_equity_grant(mobis))
        self.assertTrue(scoops.employee_equity_grant(kia))
        self.assertTrue(scoops.employee_equity_grant("5. 처분목적 임원 성과급 지급 7. 처분상대방 임원 12명"))
        # 지배구조·자금 목적 처분은 그대로 본다
        self.assertFalse(scoops.employee_equity_grant("5. 처분목적 교환사채 교환대상 주식 확보 7. 처분상대방 기관투자자"))
        self.assertFalse(scoops.employee_equity_grant("5. 처분목적 전략적 제휴를 위한 주식 교환 7. 처분상대방 OOO홀딩스"))

    def test_exclusive_scope_rejects_unrelated_sources_and_suppliers(self):
        unrelated = [
            "대법원 선고 2026도11543 증거인멸교사 등 사건에 관한 보도자료",
            "경매 임차인 통지서 전면 개선",
            "삼성전기, 신규 계약 2,856억원…고객사·물량은",
            "포스코퓨처엠 해외 양극재 투자",
            "포스코인터내셔널 신규 LNG 도입 계약",
            "한국전력기술 전기설계 분야 채용",
        ]
        for title in unrelated:
            with self.subTest(title=title):
                self.assertEqual(scoops.direct_beat_company_hits({}, title), [])

    def test_exclusive_scope_allows_direct_companies(self):
        cases = {
            "현대차, 전기차 생산계획 조정": "현대차",
            "HL만도 공급사 변경": "HL만도",
            "BMW코리아 740d 제작결함 리콜": "BMW코리아",
            "포스코홀딩스 광물 사업 투자": "포스코홀딩스",
            "LS일렉트릭 HVDC 변압기 수주": "LS일렉트릭",
            "동국제강 철강제품 생산조정": "동국제강",
            "동성케미칼 공장 설비 증설": "동성케미칼",
        }
        for title, name in cases.items():
            with self.subTest(title=title):
                self.assertIn(name, scoops.direct_beat_company_hits({}, title))
        self.assertEqual(scoops.direct_beat_company_hits(
            {"corpName": "포스코퓨처엠"}, "포스코퓨처엠 주요사항보고서"), [])

    def test_public_radar_excludes_nonbeat_disclosures(self):
        now=datetime.now(scoops.KST)
        date=now.strftime("%Y%m%d")
        rows=[
            {"corpName":"삼성전기","reportName":"신규시설투자등",
             "date":date,"receiptNo":"20261012000001","url":"https://dart.fss.or.kr"},
            {"corpName":"LG화학","reportName":"생산중단",
             "date":date,"receiptNo":"20261012000002","url":"https://dart.fss.or.kr"},
            {"corpName":"두산에너빌리티","reportName":"생산중단",
             "date":date,"receiptNo":"20261012000003","url":"https://dart.fss.or.kr"},
            {"corpName":"포스코퓨처엠","reportName":"회사분할결정",
             "date":date,"receiptNo":"20261012000004","url":"https://dart.fss.or.kr"},
        ]
        public=scoops.build_public_signals([],rows,now,numeric_rows=[])
        self.assertEqual([x["companies"] for x in public],[["두산에너빌리티"]])

    def test_companyless_policy_not_exclusive(self):
        self.assertFalse(scoops.relevant_primary(
            {"policySignal": True, "official": True}, [],
            "소송·분쟁", "법원 판결 및 산업 관련 제도 개선"
        ))
        self.assertTrue(scoops.relevant_primary(
            {"corpName": "기아"}, ["기아"], "사업재편", "공장 신설"
        ))

    def test_dart_seven_argument_bootstrap(self):
        receipt = "20261008800790"
        main = ('<html><script>viewDoc("20261008800790", "11608769", '
                '"0", "0", "0", "HTML", "");</script></html>')
        viewer = '<html><body>' + (
            '생산중단 정정공시 공장 재가동 일정 확정 및 생산 예정일을 '
            '변경했습니다. ' * 5
        ) + '</body></html>'
        requested = []

        def fake_fetch(url, timeout=12):
            requested.append(url)
            return main.encode() if "/dsaf001/main.do" in url else viewer.encode()

        with patch.object(dart, "fetch_bytes", side_effect=fake_fetch):
            diag = {}
            result = dart.fetch_dart_viewer_text(receipt, diag)
        self.assertEqual(diag["parserType"], "viewDoc-call")
        self.assertEqual(diag["documentsFound"], 1)
        self.assertTrue(diag["viewerTextLength"] > 60)
        self.assertIn("공장 재가동", result)
        self.assertTrue(any("dcmNo=11608769" in url for url in requested))

    def test_dart_units_in_table_heading(self):
        text = "3. 처분예정금액(원) 보통주식 258,750,000 기타주식 - 4. 처분예정기간"
        self.assertIn("258,750,000원", dart.extract_heading_values(text))

    def test_dart_heading_never_reads_a_date_as_the_amount(self):
        # Operating dart_numeric.json (2026-10-25) carried "2026원" for 씨에스윈드
        # from a narrative reference to the heading followed by a date.
        narrative = ("'2. 처분대상 주식가격(원)', '3. 처분예정금액(원)'은 이사회 결의일 "
                     "전일(2026년 10월 06일) 한국거래소 정규시장 종가를 기준으로")
        self.assertEqual(dart.extract_heading_values(narrative), [])
        cases = {
            "투자금액(원) 2026년 10월 1일 기준 1,000,000": ["1,000,000원"],
            "생산능력(톤) 2027년 300,000": ["300,000톤"],
            "계약금액(원) 2026.01.01 1,200,000": ["1,200,000원"],
            "투자금액(원) 2026-03-31 기준 500,000,000": ["500,000,000원"],
            "생산능력(대) 2차 증설 후 300,000": ["300,000대"],
            "생산능력(MW) 1호기 1,400": ["1,400MW"],
            "처분예정주식(주) 1,000 일반": ["1,000주"],
            "계약금액(원) 2026년 10월": [],
        }
        for text, expected in cases.items():
            self.assertEqual(dart.extract_heading_values(text), expected, text)

    def test_nlrc_dated_list_rows(self):
        recent = (datetime.now(scout.KST) - timedelta(days=1)).strftime("%Y-%m-%d")
        old = (datetime.now(scout.KST) - timedelta(days=70)).strftime("%Y-%m-%d")
        listing = (f"<html><table><tr><td>2</td><td>"
                   f"<a href='javascript:viewCase()'>원청 사업장의 산업안전 단체교섭 관련 판정사례</a>"
                   f"</td><td>{recent}</td></tr><tr><td>1</td><td>"
                   f"<a href='javascript:viewCase()'>산업안전 이전 오래된 사건 판정사례</a>"
                   f"</td><td>{old}</td></tr></table></html>")
        with patch.object(scout, "get", return_value=listing.encode()):
            rows = scout.fetch_direct_nlrc()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["dateSource"], "노동위원회 판정사례 게시일")
        self.assertEqual(rows[0]["published"][:10], recent)
        self.assertTrue(rows[0]["url"].startswith("https://nlrc.go.kr/nlrc/"))
        self.assertTrue(scout.DIRECT_DIAGNOSTICS["nlrc-case-summaries"]["outsideWindow"] >= 1)

    def test_iris_date_from_detail_not_application_window(self):
        fields, body = scout.parse_iris_detail((IRIS_FIXTURES / "old-detail.html").read_text(encoding="utf-8"))
        self.assertEqual(fields["공고일자"], "2026-09-14")
        self.assertIn("2026-10-12", fields["접수기간"])
        self.assertTrue(body)


IRIS_FIXTURES = Path(__file__).parent / "fixtures" / "iris"


class IrisRegressionTests(unittest.TestCase):
    def setUp(self):
        self.detail = (IRIS_FIXTURES / "detail.html").read_text(encoding="utf-8")
        self.listing = json.loads((IRIS_FIXTURES / "list.json").read_text(encoding="utf-8"))
        self.record = next(r for r in self.listing["listBsnsAncmBtinSitu"] if r["ancmId"] == "024237")
        self.now = datetime(2026, 10, 12, 10, tzinfo=scout.KST)

    def page(self, records, page=1, total_pages=1):
        return json.dumps({"listBsnsAncmBtinSitu": records, "paginationInfo": {
            "currentPageNo": page, "totalPageCount": total_pages,
            "totalRecordCount": len(records) if total_pages == 1 else 20,
        }}, ensure_ascii=False).encode()

    def run_collector(self, detail=None, records=None, responder=None, **kwargs):
        requested = []
        def request(url, data=None, timeout=12):
            requested.append((url, data))
            if responder:
                return responder(url, data)
            if data is not None:
                return self.page((records if records is not None else [self.record]) if data["ancmPrg"] == "ancmIng" else [])
            return (self.detail if detail is None else detail).encode()
        with patch.object(scout, "_iris_request", side_effect=request), patch.object(scout, "datetime") as clock, redirect_stdout(io.StringIO()):
            clock.now.return_value = self.now
            clock.strptime = datetime.strptime
            clock.fromisoformat = datetime.fromisoformat
            clock.min = datetime.min
            rows = scout.fetch_direct_iris_announcements(**kwargs)
        return rows, scout.DIRECT_DIAGNOSTICS["iris-rnd-announcements"], requested

    def test_real_json_and_detail_structure(self):
        rows, diag, requests = self.run_collector(detail='<nav>메뉴전용문구</nav>' + self.detail + '<footer>푸터전용문구</footer>')
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["title"], self.record["ancmTl"])
        self.assertEqual(row["published"][:10], "2026-09-22")
        self.assertEqual(row["dateSource"], "IRIS 공고일자")
        self.assertTrue(row["bodyText"])
        self.assertNotIn("메뉴전용문구", row["bodyText"])
        self.assertNotIn("푸터전용문구", row["bodyText"])
        self.assertIn("소재", row["eligibility"])
        self.assertNotIn("numbers", row)
        url = urllib.parse.urlparse(row["url"])
        self.assertEqual((url.scheme, url.netloc, url.path), ("https", "www.iris.go.kr", "/contents/retrieveBsnsAncmView.do"))
        self.assertEqual(urllib.parse.parse_qs(url.query), {"ancmId": ["024237"], "ancmPrg": ["ancmIng"]})
        self.assertEqual(diag["detailIdsSeen"], 1)
        self.assertEqual(diag["detailPagesFetched"], 1)
        self.assertEqual(diag["datedRecords"], 1)
        self.assertTrue(diag["collectionComplete"])
        self.assertTrue(requests[0][0].endswith(scout.IRIS_LIST_PATH))

    def test_old_announcement_not_refreshed_by_deadline(self):
        old = (IRIS_FIXTURES / "old-detail.html").read_text(encoding="utf-8")
        record = next(r for r in self.listing["listBsnsAncmBtinSitu"] if r["ancmId"] == "024199")
        rows, diag, requests = self.run_collector(detail=old, records=[record])
        self.assertEqual(rows, [])
        self.assertEqual(diag["exclusions"]["outside_lookback"], 1)
        # The old list date only decides not to open the page; nothing is published from the list.
        self.assertEqual(sum(data is None for _, data in requests), 0)
        self.assertEqual(diag["listPrefiltered"], 1)
        self.assertEqual(diag["status"], "no_recent_publications_in_checked_list")

    def test_earlier_verified_detail_is_reused_not_reread(self):
        rows, _, _ = self.run_collector()
        again, diag, requests = self.run_collector(prior_items=rows)
        self.assertEqual(again, rows)
        self.assertEqual(sum(data is None for _, data in requests), 0)
        self.assertEqual(diag["detailReused"], 1)
        self.assertEqual(diag["status"], "recent_announcements_checked")
        # A changed listed title is a different document: read again.
        changed = [{**rows[0], "title": "다른 제목"}]
        _, diag, requests = self.run_collector(prior_items=changed)
        self.assertEqual((diag["detailReused"], sum(data is None for _, data in requests)), (0, 1))

    def test_unrelated_listed_title_is_not_opened(self):
        rows, diag, requests = self.run_collector(records=[{**self.record, "ancmTl": "2026년 보건의료 인력양성 사업 공고"}])
        self.assertEqual(rows, [])
        self.assertEqual(sum(data is None for _, data in requests), 0)
        self.assertEqual(diag["exclusions"]["no_company_or_industry_in_title"], 1)

    def test_consecutive_timeouts_stop_and_defer_the_rest(self):
        records = [{**self.record, "ancmId": f"0242{i:02d}"} for i in range(6)]
        def response(url, data):
            if data is not None:
                return self.page(records)
            raise TimeoutError("test detail timeout")
        with patch.object(scout, "DETAIL_GAP_SECONDS", 0):
            rows, diag, requests = self.run_collector(responder=response)
        self.assertEqual(rows, [])
        self.assertEqual(sum(data is None for _, data in requests), scout.DETAIL_BREAKER * 2)
        self.assertTrue(diag["detailCircuitOpen"])
        self.assertEqual(diag["detailDeferred"], 6 - scout.DETAIL_BREAKER)
        self.assertEqual(diag["status"], "detail_fetch_failed")
        self.assertFalse(diag["collectionComplete"])

    def test_missing_invalid_future_dates_not_today(self):
        for date in ("", "2026-02-30", "2026-12-01"):
            with self.subTest(date=date):
                rows, diag, _ = self.run_collector(detail=self.detail.replace("2026-09-22</span>", date + "</span>"), records=[{**self.record, "ancmDe": ""}])
                self.assertEqual(rows, [])
                self.assertEqual(diag["recentRecords"], 0)

    def test_list_date_is_not_fallback_for_missing_detail_date(self):
        rows, diag, _ = self.run_collector(detail=self.detail.replace("공고일자", "알 수 없는 날짜"))
        self.assertEqual(rows, [])
        self.assertEqual(diag["exclusions"]["announcement_date_missing_or_invalid"], 1)

    def test_wrong_detail_response_is_not_success(self):
        for detail in ("<html>로그인이 필요합니다</html>", self.detail.replace(self.record["ancmTl"], "다른 공고")):
            rows, diag, _ = self.run_collector(detail=detail)
            self.assertEqual(rows, [])
            self.assertEqual(diag["detailPagesFetched"], 1)
            self.assertFalse(diag["collectionComplete"])

    def test_date_conflict_is_explicit(self):
        rows, diag, _ = self.run_collector(records=[{**self.record, "ancmDe": "2026-10-01"}])
        self.assertEqual(rows, [])
        self.assertEqual(diag["exclusions"]["list_detail_date_mismatch"], 1)

    def test_missing_body_is_not_inferred(self):
        rows, diag, _ = self.run_collector(detail=self.detail.split('<div class="tb_contents">')[0])
        self.assertEqual(rows, [])
        self.assertEqual(diag["exclusions"]["body_missing"], 1)

    def test_duplicate_ids_and_invalid_ids(self):
        rows, diag, requests = self.run_collector(records=[self.record, self.record, {"ancmId": "{{:ancmId}}"}, {"ancmId": "024237&evil=1"}])
        self.assertEqual(len(rows), 1)
        self.assertEqual(diag["duplicateIds"], 1)
        self.assertEqual(diag["invalidIds"], 2)
        self.assertEqual(sum(data is None for _, data in requests), 1)

    def test_pagination_and_closed_tab(self):
        def response(url, data):
            if data is None:
                return self.detail.encode()
            if data["ancmPrg"] == "ancmEnd":
                return self.page([self.record])
            return self.page([self.record], data["pageIndex"], 2)
        rows, diag, requests = self.run_collector(responder=response)
        self.assertEqual(len(rows), 1)
        self.assertEqual(diag["listPagesParsed"], 3)
        self.assertEqual(diag["duplicateIds"], 2)
        self.assertTrue(diag["collectionComplete"])
        self.assertTrue(any(data and data["pageIndex"] == 2 for _, data in requests))

    def test_page_and_detail_limits_report_partial_coverage(self):
        def response(url, data):
            if data is None:
                return self.detail.encode()
            return self.page([self.record, {**self.record, "ancmId": "024238"}], data["pageIndex"], 20)
        rows, diag, _ = self.run_collector(responder=response, max_pages=1, max_details=1)
        self.assertEqual(diag["detailsSkippedByLimit"], 1)
        self.assertTrue(diag["coverageLimited"])
        self.assertFalse(diag["collectionComplete"])

    def test_malformed_list_does_not_claim_empty_success(self):
        for payload in (b'<html>error</html>', b'{}', b'{"listBsnsAncmBtinSitu": {}}'):
            rows, diag, _ = self.run_collector(responder=lambda u, d: payload)
            self.assertEqual(rows, [])
            self.assertEqual(diag["listPagesParsed"], 0)
            self.assertEqual(diag["status"], "list_fetch_or_parse_failed")
            self.assertTrue(diag["errors"])

    def test_empty_valid_list_is_distinct(self):
        rows, diag, _ = self.run_collector(records=[])
        self.assertEqual(rows, [])
        self.assertEqual(diag["status"], "empty_official_list")
        self.assertEqual(diag["detailPagesAttempted"], 0)
        self.assertTrue(diag["collectionComplete"])

    def test_detail_timeout_retry_is_bounded(self):
        def response(url, data):
            if data is not None:
                return self.page([self.record])
            raise TimeoutError("test detail timeout")
        rows, diag, requests = self.run_collector(responder=response)
        self.assertEqual(rows, [])
        self.assertEqual(sum(data is None for _, data in requests), 2)
        self.assertEqual(diag["retries"], 1)
        self.assertEqual(diag["status"], "detail_fetch_failed")

    def test_list_failure_is_distinct(self):
        def response(url, data):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        rows, diag, requests = self.run_collector(responder=response)
        self.assertFalse(diag["listFetched"])
        self.assertEqual(diag["listPagesParsed"], 0)
        self.assertEqual(diag["retries"], 0)
        self.assertEqual(len(requests), 2)

    def test_company_mentions_do_not_expand_direct_beat(self):
        for text, expected in (("포스코퓨처엠", ["포스코퓨처엠"]), ("포스코인터내셔널", ["포스코인터내셔널"]),
                               ("BMW 글로벌 기술", []), ("BMW코리아 기술", ["BMW코리아"]),
                               ("GS칼텍스", ["GS칼텍스"]), ("SK온도", [])):
            self.assertEqual(scout._iris_company_mentions(text), expected)
        rows, diag, _ = self.run_collector()
        leads, lead_diag = scoops.build_lead_signals(rows, [], self.now)
        self.assertEqual(leads, [])
        self.assertEqual(lead_diag["out_of_beat"], 1)
        self.assertEqual(rows[0]["companies"], [])
        for company in ("삼성전기", "포스코퓨처엠", "포스코인터내셔널"):
            title = company + " 신규 기술개발 과제 공고"
            rows, _, _ = self.run_collector(detail=self.detail.replace(self.record["ancmTl"], title), records=[{**self.record, "ancmTl": title}])
            leads, lead_diag = scoops.build_lead_signals(rows, [], self.now)
            self.assertEqual(leads, [])
            self.assertEqual(lead_diag["out_of_beat"], 1)


if __name__ == "__main__":
    unittest.main()
