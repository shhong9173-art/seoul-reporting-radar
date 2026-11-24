"""Connector views restate sources; they never upgrade leads or turn 0 into 미보도."""
import json
import re
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
                  {"title": "[단독] 현대제철, 인천 전기로 신설…2028년 가동 목표 - 매체A", "sourceName": "매체A",
                   "published": "2026-10-25T09:00:00+09:00", "companies": ["현대제철"], "url": "https://news.example/2"},
                  {"title": "[단독] 현대제철, 인천 전기로 신설…2028년...", "sourceName": "news.example",   # 네이버 잘린 제목 — 같은 기사
                   "published": "2026-10-25T10:00:00+09:00", "companies": ["현대제철"], "url": "https://news.example/2n"},
                  {"title": "[단독] 믿었던 제네시스가 ‘펑’··· 현대차, 다이오드 문제 - 매체C", "sourceName": "매체C",   # 제네시스·현대차 → 현대차 한 번
                   "published": "2026-10-24T09:00:00+09:00", "companies": ["제네시스", "현대차"], "url": "https://news.example/3"},
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
        # 11-23: 표 제목이 보고 주체로 읽힌 줄('자산항목:비품')과 정렬용 공백이 낀 낱말('운 송')
        {"company": "HL만도", "topic": "segmentSales", "reportingEntity": "자산항목:비품", "rowIdentity": ["인도", "제품, 상품, 기타매출"],
         "priorValue": "743047", "currentValue": "879225", "percentChange": 18.3, "unit": "백만원", "period": "09", "fromYear": 2025, "toYear": 2026, "sourceUrls": []},
        {"company": "금호석유화학", "topic": "segmentSales", "reportingEntity": "주요종속회사:금호티앤엘(주)", "rowIdentity": ["운 송", "서비스"],
         "priorValue": "6757", "currentValue": "8402", "percentChange": 24.4, "unit": "백만원", "period": "09", "fromYear": 2025, "toYear": 2026, "sourceUrls": []},
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
        # 11-23: DART 회사명 'POSCO홀딩스'는 출입처 포스코홀딩스(철강·비철) — 'POSCO' 뒤에 한글이 붙어 낱말 경계로는 안 잡혔다
        self.assertEqual(v.beat_name("POSCO홀딩스"), "포스코홀딩스")
        self.assertEqual(v.team_for(v.beats_in("POSCO홀딩스 풍문또는보도에대한해명(미확정)(자회사의 주요경영사항)")), "철강·비철")

    def test_registry_names_match_the_worker_and_the_dart_registry_aliases(self):
        # 11-23: 'POSCO홀딩스'가 dart_corp_registry 별칭에만 있고 이름표(tool views·Worker)엔 없어 radar_clues에서 '그 외'로 떴다.
        # 세 곳이 어긋나지 않게: Worker(common.mjs) REGISTRY_NAMES == 이 파일 REGISTRY_NAMES, 공식 회사명 별칭은 모두 출입처로 읽힌다
        import dart_corp_registry
        src = (ROOT / "cloudflare" / "common.mjs").read_text(encoding="utf-8")
        block = re.search(r"export const REGISTRY_NAMES = \{(.*?)\n\};", src, re.S).group(1)
        worker = dict(re.findall(r"'([^']+)':\s*'([^']+)'", block))
        self.assertEqual(worker, v.REGISTRY_NAMES)
        for canon, aliases in dart_corp_registry.ALIASES.items():
            for alias in aliases:
                self.assertIsNotNone(v.beat_name(alias), f"{canon} 별칭 {alias}")

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

    def test_merged_stake_row_keeps_the_reporter(self):
        # 11-22 radar_clues: 같은 접수번호의 DART 공시 줄에 지분공시 줄이 합쳐져 '현대제철 · 임원ㆍ주요주주특정증권등소유상황보고서'만 남고
        # 보고자(국민연금공단)가 사라졌다. 첫 보고는 증감이 보유 전체라 '+10.00%p'로 적지 않는다
        rno = "20261119000277"
        dart = v.from_dart_beat({"records": [{"company": "현대제철", "receiptNo": rno, "published": "20261119",
                                               "report": "임원ㆍ주요주주특정증권등소유상황보고서", "sourceUrl": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + rno}]})
        gov = v.from_governance({"items": [{"company": "현대제철", "team": "철강·비철", "kind": "임원·주요주주", "date": "2026-11-19", "receiptNo": rno,
                                            "reporter": "국민연금공단", "role": "10%이상주주", "ratio": 10.0, "ratioChange": 10.0, "firstReport": True,
                                            "tags": ["[10% 이상 주주로 첫 보고 · 보유 10.00%]"], "routine": False}]})
        self.assertEqual(gov[0]["title"], "현대제철 · 임원·주요주주 · 국민연금공단(10%이상주주)")
        row = v.merge_clues(dart + gov)[0]
        self.assertEqual(row["title"], "현대제철 · 임원ㆍ주요주주특정증권등소유상황보고서")
        self.assertEqual(row["note"], "보고자 국민연금공단(10%이상주주) · [10% 이상 주주로 첫 보고 · 보유 10.00%]")
        # 지분공시 줄이 먼저 오면 제목에 보고자가 이미 있다 — 메모에 다시 적지 않는다
        self.assertNotIn("보고자", v.merge_clues(gov + dart)[0]["note"])

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
        self.assertIn("HL만도 부문 매출 (인도 / 제품, 상품, 기타매출)", labels)
        self.assertIn("금호석유화학 부문 매출 (주요종속회사:금호티앤엘(주) / 운송 / 서비스)", labels)
        self.assertEqual(v.tidy_label("한국 공장"), "한국 공장")   # 두 글자 넘는 낱말 사이 공백은 그대로
        self.assertEqual(v.tidy_label("하 역"), "하역")
        self.assertFalse(any("봉형강" in x for x in labels))  # 4% change is not a signal

    def test_dandok_strips_publisher_and_drops_old_rows(self):
        dandok = self.build()["dandok"]
        self.assertEqual([r["title"] for r in dandok["items"]], ["[단독] 현대제철, 인천 전기로 신설…2028년 가동 목표", "[단독] 믿었던 제네시스가 ‘펑’··· 현대차, 다이오드 문제"])
        self.assertEqual(dandok["items"][0]["team"], "철강·비철")
        self.assertEqual(dandok["items"][1]["companies"], ["현대차"])

    def test_dandok_folds_same_outlet_same_day_duplicates(self):
        # 11-22 dandok_monitor: 잘린 제목('...' 없음)과 온전한 제목, 제목 낱말 하나만 바꾼 재게시가 두 줄씩 떴다
        rows = [{"published": "2026-11-20", "source": "이투데이", "title": "[단독] 법원, 현대모비스 램프사업", "url": "u1", "companies": ["현대모비스"]},
                {"published": "2026-11-20", "source": "이투데이", "title": "[단독] 법원, 현대모비스 램프사업 분할 반발 근로자 가처분 기각", "url": "u2", "companies": ["현대모비스"]},
                {"published": "2026-11-20", "source": "전기신문", "title": "[단독] SK온, LFP로 ‘제주 25년 장기계약’ 입찰 도전…초장기 수명 검증 시험대", "url": "u3", "companies": []},
                {"published": "2026-11-20", "source": "전기신문", "title": "[단독] SK온, LFP로 ‘제주 25년 장기계약’ 입찰 참여…초장기 수명 검증 시험대", "url": "u4", "companies": []},
                {"published": "2026-11-19", "source": "mk.co.kr", "title": "[단독] 현대차 '집콕 근무' 사라진다", "url": "u5", "companies": ["현대차"]},
                {"published": "2026-11-19", "source": "매일경제", "title": "[단독] 현대차, 채용 웹사이트서 ‘재택근무’ 항목삭제…집콕 원천차단 속도", "url": "u6", "companies": ["현대차"]}]
        out = v.fold_same_outlet([dict(r) for r in rows])
        self.assertEqual([r["title"] for r in out], ["[단독] 법원, 현대모비스 램프사업 분할 반발 근로자 가처분 기각",
                                                    "[단독] SK온, LFP로 ‘제주 25년 장기계약’ 입찰 도전…초장기 수명 검증 시험대",
                                                    "[단독] 현대차 '집콕 근무' 사라진다",
                                                    "[단독] 현대차, 채용 웹사이트서 ‘재택근무’ 항목삭제…집콕 원천차단 속도"])   # 다른 매체·다른 기사는 그대로
        self.assertEqual(out[0]["url"], "u2")

    def test_dandok_publisher_tails_are_stripped(self):
        # 11-22 dandok_monitor: ' - 머니투데이'가 두 번 붙은 제목, ' By EBN'·' By The Guru - In…' 꼬리
        self.assertEqual(v.strip_publisher("[단독]'TF' 보면 현대차그룹 미래 보인다..대거 신설 - 머니투데이 - 머니투데이"), "[단독]'TF' 보면 현대차그룹 미래 보인다..대거 신설")
        self.assertEqual(v.strip_publisher("[단독] 현대차, 하이브리드 승부수...열효율 45% ’린번 엔진’ 꺼냈다 By EBN"), "[단독] 현대차, 하이브리드 승부수...열효율 45% ’린번 엔진’ 꺼냈다")
        self.assertEqual(v.strip_publisher("[단독] 포스코인터, 러시아서 ’떼인 돈’ 받는다 By The Guru - In"), "[단독] 포스코인터, 러시아서 ’떼인 돈’ 받는다")
        self.assertEqual(v.strip_publisher("[단독] 현대제철, 인천 전기로 신설…2028년 가동 목표 - 매일경제"), "[단독] 현대제철, 인천 전기로 신설…2028년 가동 목표")
        self.assertEqual(v.strip_publisher("[단독] LS-니꼬동제련 지분 정리"), "[단독] LS-니꼬동제련 지분 정리")     # 제목 속 하이픈은 그대로

    def test_health_marks_missing_and_not_connected_sources(self):
        health = self.build()["health"]
        by = {r["source"]: r for r in health["items"]}
        self.assertTrue(by["나라장터 입찰공고"]["problem"])
        self.assertTrue(by["자동차 뉴스 수집"]["problem"])  # file missing in fixture
        self.assertIn("0건이 아니다", health["rule"])

    def test_weekday_only_contract_ledger_does_not_warn_on_sunday(self):
        # 11-22(일) 09:36: 금요일 08:10 판이 49.3시간으로 '⚠ 계약 공시 원장'이 떴다 — 평일(월~금)만 도는 원천이다.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fixture(tmp.name, True)
        sunday = datetime(2026, 11, 22, 9, 36, tzinfo=KST)
        write(tmp.name, "digests/recent_contracts_latest.json", {"generatedAt": "2026-11-20T08:20:00+09:00", "status": "ok"})
        row = {r["source"]: r for r in v.build_health(Path(tmp.name), sunday)["items"]}["계약 공시 원장"]
        self.assertFalse(row["problem"])
        self.assertEqual(row["ageHours"], 49.3)
        self.assertIn("주말 33.6시간 빼면 15.7시간", row["note"])
        # 월요일 판을 놓치면 화요일 아침엔 여전히 알린다(주말 48시간을 빼도 48시간 넘음).
        tuesday = datetime(2026, 11, 24, 9, 0, tzinfo=KST)
        row = {r["source"]: r for r in v.build_health(Path(tmp.name), tuesday)["items"]}["계약 공시 원장"]
        self.assertTrue(row["problem"])
        # 평일만 도는 원천이 아닌 것(DART 출입처 공시)은 주말도 그대로 센다.
        write(tmp.name, "digests/dart_beat_run_health_latest.json", {"generatedAt": "2026-11-20T08:20:00+09:00", "status": "ok"})
        row = {r["source"]: r for r in v.build_health(Path(tmp.name), sunday)["items"]}["DART 출입처 공시"]
        self.assertTrue(row["problem"])
        self.assertNotIn("note", row)

    def test_coverage_check_reads_month_files_and_refuses_a_broken_one(self):
        # 11-24 월별 분할: 지난 달 기사도 대조에 써야 하고, 달 파일이 어긋나면 색인 없음(0건 아님)으로
        from scripts.press_coverage_index import merge_index, write_split_index
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        dec = datetime(2026, 12, 2, 9, 0, tzinfo=KST)
        rows = [{"title": "현대차 10월 기사", "published": "2026-10-20T09:00:00+09:00", "sourceName": "경제신문",
                 "url": "https://example.com/a", "companies": ["현대차"]},
                {"title": "현대차 12월 기사", "published": "2026-12-01T09:00:00+09:00", "sourceName": "경제신문",
                 "url": "https://example.com/b", "companies": ["현대차"]}]
        write_split_index(root / "digests/press_coverage_index_latest.json", merge_index(None, rows, now=dec), dec)
        full = v.load_press_history(root)
        self.assertEqual(full["itemCount"], 2)
        self.assertEqual(v.CoverageIndex(full, None).ok, True)
        self.assertEqual(len(v.CoverageIndex(full, None).rows), 2)
        shard = root / "digests/press_coverage_index/2026-10.json"
        shard.write_text(shard.read_text(encoding="utf-8").replace("10월", "9월"), encoding="utf-8")
        self.assertIsNone(v.load_press_history(root))
        self.assertEqual(v.CoverageIndex(None, None).check({"companies": ["현대차"], "title": "x"})["status"], "index_unavailable")

    def test_publish_files_near_size_limit_are_flagged(self):
        # 11-24: 1년 기보도 색인이 12MiB 발행 상한을 넘어 Auto Desk가 19회 연속 실패 — 80%부터 미리 알린다
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        fixture(tmp.name, True)
        root = Path(tmp.name)
        (root / "data.json").write_text("x" * (10 * 1024 * 1024), encoding="utf-8")       # 12MiB의 83%
        (root / "archive.json").write_text("x" * (20 * 1024 * 1024), encoding="utf-8")    # 32MiB의 62% — 아직
        health = v.build_health(root, NOW)
        rows = {r["source"]: r for r in health["items"]}
        row = rows["발행 파일 크기 data.json"]
        self.assertTrue(row["problem"])
        self.assertIn("10.0MiB / 상한 12MiB(83%)", row["note"])
        self.assertIn("'news' 발행 전체가 멈춘다", row["note"])
        self.assertNotIn("발행 파일 크기 archive.json", rows)
        (root / "archive.json").write_text("x" * (27 * 1024 * 1024), encoding="utf-8")    # 84%
        rows = {r["source"]: r for r in v.build_health(root, NOW)["items"]}
        self.assertIn("27.0MiB / 상한 32MiB(84%)", rows["발행 파일 크기 archive.json"]["note"])

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
