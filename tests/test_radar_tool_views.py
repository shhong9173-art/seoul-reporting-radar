"""Connector views restate sources; they never upgrade leads or turn 0 into 미보도."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import radar_tool_views as v  # noqa: E402

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 26, 9, 0, tzinfo=KST)


def write(root, rel, data):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fixture(root, with_index=True):
    write(root, "pre_scoop.json", {"generatedAt": "2026-10-26T08:00:00+09:00", "items": [
        {"officialLabel": "팩토리온", "sourceGroup": "공장·산업단지", "title": "동국씨엠 부산공장 공장등록 변경",
         "url": "https://www.factoryon.go.kr/a", "published": "2026-10-24T00:00:00+09:00", "companies": []},
        {"officialLabel": "한전 전자조달", "sourceGroup": "공기업·조달", "title": "154kV 변압기 구매 입찰",
         "url": "javascript:fnSelectView(1)", "published": "2026-10-23T00:00:00+09:00", "companies": []},
        {"officialLabel": "팩토리온", "sourceGroup": "공장·산업단지", "title": "세아씨엠 군산공장 증설",
         "url": "https://www.factoryon.go.kr/b", "published": "2026-10-24T00:00:00+09:00", "companies": []},
    ]})
    write(root, "digests/dart_beat_monitor_latest.json", {"generatedAt": "2026-10-26T07:00:00+09:00", "records": [
        {"company": "엘에스일렉트릭", "receiptNo": "20261023000111", "published": "20261023",
         "report": "단일판매ㆍ공급계약체결", "category": "공급계약", "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261023000111"},
        {"company": "현대위아", "receiptNo": "20261022000222", "published": "20261022",
         "report": "주주명부폐쇄기간또는기준일설정", "category": "기타", "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261022000222"},
    ]})
    write(root, "scoop.json", {"generatedAt": "2026-10-26T08:00:00+09:00", "items": [], "leadSignals": [],
                               "publicSignals": [{"title": "엘에스일렉트릭 단일판매ㆍ공급계약체결", "companies": ["LS일렉트릭"],
                                                  "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261023000111",
                                                  "published": "2026-10-23T00:00:00+09:00", "sourceName": "DART"}],
                               "heldDartResearch": []})
    if with_index:
        write(root, "digests/press_coverage_index_latest.json", {"generatedAt": "2026-10-26T06:00:00+09:00", "items": [
            {"title": "LS일렉트릭, 북미 초고압 변압기 공급계약 체결 - 전기신문", "sourceName": "전기신문",
             "published": "2026-10-23T11:00:00+09:00", "companies": ["LS일렉트릭"], "url": "https://news.example/1"},
        ]})
        write(root, "digests/historical_exclusive_press_index_latest.json", {"generatedAt": "2026-10-26T06:00:00+09:00",
              "status": "ok", "items": [
                  {"title": "[단독] 현대제철, 인천 전기로 신설 - 매체A", "sourceName": "매체A",
                   "published": "2026-10-25T09:00:00+09:00", "companies": ["현대제철"], "url": "https://news.example/2"},
                  {"title": "[단독] 오래된 기사 - 매체B", "sourceName": "매체B",
                   "published": "2026-03-01T09:00:00+09:00", "companies": ["현대차"], "url": "https://news.example/3"},
              ]})
    write(root, "digests/customs_tenday_latest.json", {"generatedAt": "2026-10-21T16:00:00+09:00",
          "observed": [{"series": "exp_item", "month": f"2026{m:02d}", "cutoff": 20,
                        "items": [{"name": "철강제품", "amountKUsd": str(1000 + m)}]} for m in range(1, 10)],
          "focus": [{"series": "exp_item", "item": "철강제품", "month": "202610", "cutoff": 20, "periodLabel": "01~20",
                     "amountKUsd": "2588", "priorYearAmountKUsd": "1814", "yoyPercent": 42.6,
                     "sourceUrl": "https://www.data.go.kr/data/15157908/openapi.do"}]})
    write(root, "digests/recent_metric_changes_latest.json", {"generatedAt": "2026-10-23T21:00:00+09:00", "items": [
        {"company": "엘에스일렉트릭", "topic": "productionCapacity", "rowIdentity": ["부산", "변압기"], "priorValue": "100",
         "currentValue": "211", "percentChange": 111.0, "unit": "백만원", "period": "06", "fromYear": 2025, "toYear": 2026,
         "sourceUrls": ["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814003088"]},
        {"company": "현대제철", "topic": "segmentSales", "rowIdentity": ["봉형강"], "priorValue": "100", "currentValue": "104",
         "percentChange": 4.0, "unit": "백만원", "fromYear": 2025, "toYear": 2026, "sourceUrls": []},
    ]})
    write(root, "digests/governance_latest.json", {"generatedAt": "2026-10-26T07:40:00+09:00", "status": "complete", "items": [
        {"company": "고려아연", "team": "철강·비철", "kind": "대량보유(5%)", "date": "2026-10-20", "receiptNo": "20261020000111",
         "reporter": "영풍", "ratioChange": -1.45, "tags": ["[지분율 -1.45%p]"], "reason": "보유주식 처분", "routine": False,
         "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261020000111"},
        {"company": "현대차", "team": "자동차", "kind": "대량보유(5%)", "date": "2026-10-21", "receiptNo": "20261021000222",
         "reporter": "국민연금공단", "ratioChange": 0.05, "tags": [], "reason": "단순투자", "routine": True,
         "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261021000222"}]})
    write(root, "digests/earnings_compare_latest.json", {"generatedAt": "2026-10-25T18:40:00+09:00", "status": "complete",
        "period": {"year": 2026, "report": "11014", "label": "2026년 3분기"}, "companies": [
        {"company": "현대제철", "team": "철강·비철", "status": "filed", "basis": "연결", "filedOn": "2026-10-24",
         "receipts": ["20261024000333"], "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261024000333",
         "quarter": {"ratios": {"costRatio": 92.0, "sgaRatio": 6.0, "opMargin": 2.0}}, "tags": ["[원가율 +3.5%p]"]},
        {"company": "기아", "team": "자동차", "status": "filed", "basis": "연결", "filedOn": "2026-10-24",
         "receipts": ["20261024000444"], "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261024000444",
         "quarter": {"ratios": {"costRatio": 78.0}}, "tags": []},
        {"company": "영풍", "team": "철강·비철", "status": "not_filed"}]})
    write(root, "digests/g2b_source_status_latest.json", {"generatedAt": "2026-10-26T01:37:40+09:00",
                                                            "status": "not_connected", "note": "no key"})


class Views(unittest.TestCase):
    def build(self, with_index=True, previous=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fixture(tmp.name, with_index)
        out = Path(tmp.name) / "tools"
        if previous:
            write(out, "clues.json", previous)
        v.build_all(Path(tmp.name), out, now=NOW)
        return {name: json.loads((out / f"{name}.json").read_text(encoding="utf-8"))
                for name in ("clues", "stats", "dandok", "health", "big_picture")}

    def clue(self, views, needle):
        return next(r for r in views["clues"]["items"] if needle in r["title"])

    def test_recall_group_title_carries_the_first_notice_row(self):
        # 10-31 운영 scoop.json publicSignals: 묶음 제목만으로는 차종·부품을 모른다
        rows = v.from_scoop({"publicSignals": [{"id": "r1", "kind": "공개 리콜 공지", "title": "기아, 10월 30일 리콜 공지 1건", "companies": ["기아"],
                                                  "details": ["[기아] 쏘렌토 - 저압연료라인 어셈블리 관련 리콜 중대리콜(화재위험)"],
                                                  "published": "2026-10-30T00:00:00+09:00", "url": "https://car.go.kr/ri/stat/list.do?searchProductName=x"},
                                                 {"id": "r2", "kind": "공개 리콜 공지", "title": "현대차, 10월 14일 리콜 공지 2건", "companies": ["현대차"],
                                                  "details": ["[현대] 아이오닉9 - 전동시트 제어기 관련 리콜", "[현대] 팰리세이드 - 같은 원인"],
                                                  "published": "2026-10-14T00:00:00+09:00", "url": "https://car.go.kr/ri/stat/list.do"}]})
        self.assertEqual([r["title"] for r in rows], ["기아, 10월 30일 리콜 공지 1건 — [기아] 쏘렌토 - 저압연료라인 어셈블리 관련 리콜 중대리콜(화재위험)",
                                                     "현대차, 10월 14일 리콜 공지 2건 — [현대] 아이오닉9 - 전동시트 제어기 관련 리콜 외 1건"])

    def test_scoop_items_take_date_and_url_from_their_source(self):
        # 10-31 운영 scoop.json items: 주소·게시일이 originalSourceUrl·sources[]에만 있다
        rows = v.from_scoop({"items": [{"id": "c5", "kind": "공시", "title": "현대자동차, 주요사항보고서(자기주식처분결정)", "companies": ["현대차"],
                                        "originalSourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029000247",
                                        "sources": [{"source": "DART", "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029000247",
                                                     "published": "2026-10-29T00:00:00+09:00"}]}]})
        self.assertEqual((rows[0]["published"], rows[0]["receiptNo"], rows[0]["tier"]), ("2026-10-29", "20261029000247", v.TIER_CANDIDATE))
        self.assertTrue(rows[0]["url"].startswith("https://dart.fss.or.kr/"))
        self.assertEqual(rows[0]["id"], v.clue_id("레이더", "c5"))  # 단서 id는 예전 그대로(판정·처음 본 날 유지)

    def test_us_recall_clue_title_names_the_models(self):
        rows = v.from_crossborder({"items": [{"id": "usrecall:26V692000", "type": "overseas_safety_domestic_comparison",
            "companyGroup": "현대차·기아·제네시스", "headline": "미국 리콜 26V692000 · 국내 동일 부품/시정조치 대조 필요",
            "officialPublicationDate": "2026-10-20", "reporterPriority": "background_followup",
            "sourceEvidence": [{"url": "https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber=26V692000"}],
            "officialFact": {"usModelYears": [{"model": "ELANTRA", "year": "2026"}, {"model": "TUCSON HYBRID", "year": "2026"}, {"model": "ELANTRA", "year": "2026"}]}}]})
        self.assertEqual(rows[0]["title"], "미국 리콜 26V692000 · ELANTRA·TUCSON HYBRID · 국내 동일 부품/시정조치 대조 필요")

    def test_registry_names_and_exact_beats_pick_the_team(self):
        views = self.build()
        self.assertEqual(self.clue(views, "엘에스일렉트릭")["team"], "전력·에너지")
        self.assertEqual(self.clue(views, "동국씨엠")["team"], "철강·비철")
        # 세아씨엠 is monitored but not a confirmed direct beat.
        self.assertEqual(self.clue(views, "세아씨엠")["team"], "그 외")
        self.assertEqual(self.clue(views, "154kV")["team"], "조달")

    def test_same_receipt_merges_without_upgrading_tier(self):
        views = self.build()
        rows = [r for r in views["clues"]["items"] if r["receiptNo"] == "20261023000111"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["tier"], v.TIER_PUBLIC)
        self.assertNotIn(v.TIER_CANDIDATE, {r["tier"] for r in views["clues"]["items"]})

    def test_coverage_labels_never_claim_unreported(self):
        views = self.build()
        ls = self.clue(views, "엘에스일렉트릭")["coverage"]
        self.assertEqual(ls["status"], "similar_headlines")
        self.assertIn("같은 사건인지 원문 확인", ls["label"])
        dk = self.clue(views, "동국씨엠")["coverage"]
        self.assertEqual(dk["status"], "none_in_index")
        self.assertIn("미보도 증거 아님", dk["label"])
        self.assertEqual(self.clue(views, "154kV")["coverage"]["status"], "not_compared")
        blob = json.dumps(views["clues"], ensure_ascii=False)
        self.assertNotIn('"미보도"', blob)

    def test_missing_index_is_unavailable_not_zero(self):
        views = self.build(with_index=False)
        self.assertEqual(self.clue(views, "엘에스일렉트릭")["coverage"]["status"], "index_unavailable")

    def test_published_and_first_seen_are_separate_and_first_seen_persists(self):
        first = self.build()
        row = self.clue(first, "동국씨엠")
        self.assertEqual(row["published"], "2026-10-24")
        old = {"items": [{"id": row["id"], "firstSeen": "2026-10-24T10:00:00+09:00"}]}
        second = self.build(previous=old)
        self.assertEqual(self.clue(second, "동국씨엠")["firstSeen"], "2026-10-24T10:00:00+09:00")

    def test_stake_filings_become_public_clues_with_routine_flag(self):
        views = self.build()
        zinc = self.clue(views, "고려아연 · 대량보유(5%) · 영풍")
        self.assertEqual(zinc["team"], "철강·비철")
        self.assertEqual(zinc["tier"], v.TIER_PUBLIC)
        self.assertIn("-1.45%p", zinc["title"])
        self.assertFalse(zinc["routine"])
        self.assertTrue(self.clue(views, "국민연금공단")["routine"])

    def test_group_affiliate_disclosures_are_routine(self):
        # 10-29~30 운영 제목(공정거래법 대규모기업집단 정기 공시)
        for t in ["현대자동차 · 특수관계인으로부터채권매수", "현대자동차 · 특수관계인에대한부동산임대", "현대자동차 · 특수관계인과의내부거래",
                  "현대자동차 · 약관에의한금융거래시계열금융회사의거래상대방의공시", "현대자동차 · 공정거래자율준수프로그램운영현황(안내공시)",
                  "GS칼텍스 · 동일인등출자계열회사와의상품ㆍ용역거래변경", "두산에너빌리티 · 특수관계인과의수익증권거래"]:
            self.assertTrue(v.ROUTINE_RE.search(t), t)
        for t in ["현대자동차 · 현금ㆍ현물배당결정", "OCI홀딩스 · 정기·주요공시 · 주식소각결정", "두산에너빌리티 · 풍문또는보도에대한해명",
                  "LS전선 · 정기·주요공시 · [기재정정]주요사항보고서(교환사채권발행결정)", "현대오토에버 · 정기·주요공시 · 타법인주식및출자증권취득결정",
                  "기아 · 특수관계인에대한출자", "현대자동차 · 특수관계인에대한자금대여"]:  # 출자·자금대여는 새 법인·지원일 수 있음
            self.assertFalse(v.ROUTINE_RE.search(t), t)

    def test_only_flagged_filed_companies_become_earnings_clues(self):
        views = self.build()
        steel = self.clue(views, "현대제철 · 2026년 3분기")
        self.assertIn("원가율 92.0%", steel["title"])
        self.assertIn("[원가율 +3.5%p]", steel["note"])
        self.assertEqual(steel["signal"], "earnings")
        titles = [c["title"] for c in views["clues"]["items"]]
        self.assertFalse(any("기아 · 2026년 3분기" in t for t in titles))
        self.assertFalse(any(t.startswith("영풍 · 2026년") for t in titles))

    def test_link_less_list_rows_are_kept_with_a_note(self):
        row = self.clue(self.build(), "154kV")
        self.assertIsNone(row["url"])
        self.assertIn("원문 링크 없음", row["note"])

    def test_procedural_filings_are_flagged_and_sorted_last(self):
        views = self.build()
        routine = self.clue(views, "주주명부폐쇄")
        self.assertTrue(routine["routine"])
        auto = [r for r in views["clues"]["items"] if r["team"] == "자동차"]
        self.assertTrue(auto[-1]["routine"])

    def test_stats_keep_scope_and_only_observed_maximum(self):
        stats = self.build()["stats"]["items"]
        steel = next(s for s in stats if s["kind"] == "customs_tenday")
        self.assertIn("[급변]", steel["tags"])
        self.assertTrue(any(t.startswith("[관측 구간 최대") for t in steel["tags"]))
        self.assertNotIn("역대", json.dumps(steel["tags"], ensure_ascii=False))
        self.assertIn("기업 실적 아님", steel["caveat"])
        labels = [s["label"] for s in stats]
        self.assertTrue(any("LS일렉트릭 생산능력" in x for x in labels))
        self.assertFalse(any("봉형강" in x for x in labels))  # 4% change is not a signal

    def test_dandok_strips_publisher_and_drops_old_rows(self):
        dandok = self.build()["dandok"]
        self.assertEqual([r["title"] for r in dandok["items"]], ["[단독] 현대제철, 인천 전기로 신설"])
        self.assertEqual(dandok["items"][0]["team"], "철강·비철")

    def test_health_marks_missing_and_not_connected_sources(self):
        health = self.build()["health"]
        by = {r["source"]: r for r in health["items"]}
        self.assertTrue(by["나라장터 입찰공고"]["problem"])
        self.assertTrue(by["자동차 뉴스 수집"]["problem"])  # file missing in fixture
        self.assertIn("0건이 아니다", health["rule"])

    def test_kipris_row_reads_the_shared_ledger_not_the_old_budget_file(self):
        # 11-02: 예전 예산 파일만 읽어 'KIPRIS 특허: ok · 다음 1회 확인 None'이 떴다
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fixture(tmp.name, True)
        write(tmp.name, "digests/kipris_source_request_budget_latest.json", {"nextProviderProbeAt": None, "lastProviderResponseAt": "2026-10-20T08:00:00+09:00"})
        write(tmp.name, "digests/kipris_account_ledger_latest.json", {
            "month": "2026-11", "counted": 160, "monthlyLimit": 900, "effectiveNextProbeAt": {},
            "lastSuccessAt": {"patent": (NOW - timedelta(hours=2)).isoformat(), "trademark": (NOW - timedelta(hours=3)).isoformat()}})
        rows = {r["source"]: r for r in v.build_health(Path(tmp.name), NOW)["items"]}
        k = rows["KIPRIS 특허·상표"]
        self.assertNotIn("KIPRIS 특허", rows)
        self.assertFalse(k["problem"])
        self.assertIn("장부 160/900회", k["note"])
        self.assertIn("대기 없음", k["note"])
        self.assertNotIn("None", k["note"])
        write(tmp.name, "digests/kipris_account_ledger_latest.json", {
            "month": "2026-11", "counted": 161, "monthlyLimit": 900, "effectiveNextProbeAt": {"trademark": "2026-11-03T07:10:00+09:00"},
            "lastSuccessAt": {"patent": (NOW - timedelta(hours=80)).isoformat()}})
        k = {r["source"]: r for r in v.build_health(Path(tmp.name), NOW)["items"]}["KIPRIS 특허·상표"]
        self.assertTrue(k["problem"])                       # 특허 3일 넘게 성공 없음
        self.assertEqual(k["status"], "waiting")
        self.assertIn("제공기관 대기 상표 2026-11-03T07:10부터", k["note"])

    def test_big_picture_has_no_private_reporter_state(self):
        big = self.build()["big_picture"]
        blob = json.dumps(big, ensure_ascii=False)
        for word in ("package", "feedback", "접음", "발제함"):
            self.assertNotIn(word, blob)
        self.assertTrue(big["topStats"])
        self.assertEqual(big["dandokLast7DaysByCompany"][0]["company"], "현대제철")

    def test_real_operating_files_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = v.build_all(ROOT, Path(tmp), now=NOW)
            self.assertGreater(summary["clues"], 0)
            clues = json.loads((Path(tmp) / "clues.json").read_text(encoding="utf-8"))
            self.assertNotIn(v.TIER_CANDIDATE, {r["tier"] for r in clues["items"]} - {
                r["tier"] for r in clues["items"] if r["source"] in ("레이더",)})
            for row in clues["items"]:
                self.assertIn(row["team"], v.TEAM_ORDER)
                self.assertTrue(row["url"] is None or row["url"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
