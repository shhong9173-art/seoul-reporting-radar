"""Offline regression checks for public-source parsers; no network or secrets required."""
import sys
import unittest
from datetime import datetime, timedelta
from correction_cases import CorrectionTests
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dart_numeric_extractor as dart
import pre_scoop_radar as scout
import scoop_scout as scoops


class CollectorRegressionTests(unittest.TestCase):
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
            "BMW 740d 제작결함 리콜": "BMW코리아",
            "포스코홀딩스 광물 사업 투자": "포스코홀딩스",
            "LS일렉트릭 HVDC 변압기 수주": "LS일렉트릭",
            "동국제강 철강제품 생산조정": "동국제강",
            "세아씨엠 공장 설비 증설": "세아씨엠",
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
        today = datetime.now(scout.KST).strftime("%Y-%m-%d")
        listing = ('<a href="/contents/retrieveBsnsAncmView.do?ancmId=024237">'
                   '2026년도 소재부품기술개발사업 공고</a>')
        detail = (f"<html><body>공고번호 산업통상부 2026-613 "
                  f"공고명 2026년도 소재부품기술개발사업 신규지원 대상과제 공고 "
                  f"공고일자 {today} 재공고 여부 N 접수기간 2026-10-13 ~ 2026-10-21"
                  f"</body></html>")

        def fake_get(url, timeout=12):
            return listing.encode() if "ListView" in url else detail.encode()

        with patch.object(scout, "get", side_effect=fake_get):
            rows = scout.fetch_direct_iris_announcements()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["published"][:10], today)
        self.assertEqual(rows[0]["dateSource"], "IRIS 공고일자")
        self.assertTrue(rows[0]["url"].endswith("ancmId=024237"))


if __name__ == "__main__":
    unittest.main()
