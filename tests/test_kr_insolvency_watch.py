"""협력사 회생·파산 공고 감시: 공고 종류, 공장등록 업종으로 등급, 협력사 명단, 기준선·새 항목, 업종 조회 예산, 실패는 0건이 아님."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_insolvency_watch as k  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 29, 17, 20, tzinfo=KST)


class Resp:
    def __init__(self, body=None, status=200, text=None):
        self._body, self.status_code = body, status
        self.text = text if text is not None else json.dumps(body or {}, ensure_ascii=False)

    def json(self):
        return self._body


def notice(cort, csno, name, title, code, day="20261028", seq=1):
    return {"cortCd": cort, "csNo": csno, "jdbnCd": "5017", "btprtNm": name, "pbancBgngYmd": day, "inetPbancDvsCd": code, "inetPbancSeq": seq,
            "didntEcdocId": "X", "jdbnCdNm": "제17부", "csNoNm": f"2026회합 {csno[-4:]}", "pbancTitlNm": title, "encParam": f"enc{csno}"}


SEOUL = [notice("000221", "20262920001129", "주식회사 엠디스틸", "회생절차 개시결정 공고", "26"),
         notice("000221", "20262920001130", "주식회사 한빛오토텍", "포괄적 금지명령 공고", "72"),
         notice("000221", "20262920001131", "주식회사 동네빵집", "회생절차 개시결정 공고", "26"),
         notice("000221", "20262920001132", "주식회사 메탈153", "회생절차 개시결정 공고", "26"),
         notice("000221", "20262920001133", "주식회사 엠디스틸", "회생계획안 제출기간 연장결정 공고", "30"),
         notice("000221", "20262920001134", "의료법인 정애의료재단", "회생절차 개시결정 공고", "26"),
         notice("000221", "20252920000291", "주식회사 팩슨", "회생절차 폐지결정 공고", "34", day="20261027"),
         notice("000221", "20262920001135", "주식회사 금진테크", "회생절차 개시결정 공고", "26")]
FACTORIES = {
    "엠디스틸": [{"fctryManageNo": "1", "cmpnyNm": "(주)엠디스틸", "rnAdres": "경기도 화성시 …", "allEmplyCo": "85", "rprsntvIndutyCode": "24121",
                 "indutyNm": "냉간 압연 및 압출 제품 제조업", "mainProductCn": "냉연강판"}],
    "한빛오토텍": [{"fctryManageNo": "2", "cmpnyNm": "한빛오토텍(주)", "rnAdres": "충청남도 아산시 …", "allEmplyCo": "120", "rprsntvIndutyCode": "25912",
                  "indutyNm": "자동차용 금속 프레스 가공품", "mainProductCn": "자동차 차체 프레스 부품"}],
    "팩슨": [{"fctryManageNo": "3", "cmpnyNm": "주식회사 팩슨", "rnAdres": "인천", "allEmplyCo": "40", "rprsntvIndutyCode": "30332",
             "indutyNm": "자동차 부품", "mainProductCn": "브레이크 부품"}],
    "금진테크": [{"fctryManageNo": "5", "cmpnyNm": "주식회사 금진테크", "rnAdres": "서울 …", "allEmplyCo": "15", "rprsntvIndutyCode": "25929",
                "indutyNm": "그 외 기타 금속 가공업", "mainProductCn": "덕트"}],  # 10-31 운영: 관련 업종(25)·주생산품 덕트로 B였다
    "동네빵집": [{"fctryManageNo": "4", "cmpnyNm": "동네빵집", "rnAdres": "서울", "allEmplyCo": "5", "rprsntvIndutyCode": "10712", "indutyNm": "빵류", "mainProductCn": "빵"}],
}
MA_HTML = ('<table><tbody><tr><td>92</td><td>서울회생법원</td><td><a href="/portal/notice/mainfo/MaNoticeView.work?pageIndex=1&amp;business=01&amp;seqnum=467">'
           '<span style="font-size:0px;">x</span> 제조업(기계,금속,중공업)</a></td><td><a href="/portal/notice/mainfo/MaNoticeView.work?pageIndex=1&amp;business=01&amp;seqnum=467">'
           ' 주식회사 파이프텍코리아 </a></td><td>2026-10-16</td></tr></tbody></table>')


def fakes(rows_by_court=None, fail_courts=(), factories=FACTORIES, ma_html=MA_HTML):
    rows_by_court = {"000221/4": SEOUL} if rows_by_court is None else rows_by_court
    calls = {"list": 0, "factory": []}

    def post(url, data=None, headers=None, timeout=None):
        calls["list"] += 1
        b = json.loads(data)
        key = f"{b['dma_search']['cortCd']}/{b['dma_search']['taskDvs']}"
        if b["dma_search"]["cortCd"] in fail_courts:
            raise ConnectionError("timeout")
        rows = rows_by_court.get(key, []) if b["dma_pageInfo"]["pageNo"] == 1 else []
        return Resp({"status": 200, "data": {"dlt_pbancLst": rows, "dma_pageInfo": {"totalCnt": len(rows)}}})

    def get(url, params=None, headers=None, timeout=None):
        if url == k.MA_LIST:
            return Resp(text=ma_html if params["business"] == "01" else "<table><tr><td>자료가 없습니다</td></tr></table>")
        if url == k.FACTORY_API:
            q = params["cmpnyNm"]
            calls["factory"].append(q)
            items = factories.get(q, [])
            return Resp(text=json.dumps({"response": {"header": {"resultCode": "00"}, "body": {"items": {"item": items}, "totalCount": len(items)}}}, ensure_ascii=False))
        raise AssertionError(url)
    return post, get, calls


class Insolvency(unittest.TestCase):
    def test_kinds_and_names(self):
        self.assertEqual(k.kind_of("회생절차 개시결정 공고"), ("회생 개시", "start"))
        self.assertEqual(k.kind_of("H1 기타공고(채무자 주식회사 탭샵바 포괄적 금지명령 공고)"), ("포괄적 금지명령", "start"))
        self.assertEqual(k.kind_of("파산선고공고(간이파산)"), ("파산 선고", "start"))
        self.assertEqual(k.kind_of("회생절차 폐지결정 공고"), ("회생 폐지", "end"))
        self.assertEqual(k.kind_of("회생절차 폐지결정에 관한 의견제출기한 공고"), (None, None))
        self.assertEqual(k.kind_of("관계인집회기일 변경공고"), (None, None))
        self.assertEqual(k.firm_key("주식회사 단지(632-88-00237)"), "단지")
        self.assertEqual(k.firm_key("(분할신설회사)주식회사 바이오빌에셋"), "바이오빌에셋")
        self.assertTrue(k.viewer_url("abc").startswith(k.VIEWER))

    def test_industry_tiers_and_watchlist(self):
        post, get, calls = fakes()
        doc = k.run("key", now=NOW, previous={"events": [], "generatedAt": "2026-10-28T17:20:00+09:00"}, post=post, get=get,
                    sleep=lambda s: None, watchlist={"메탈153": {"name": "주식회사 메탈153", "beat": "현대제철", "relation": "스크랩 납품", "evidence": "기자 확인"}})
        ev = {e["company"]: e for e in doc["events"]}
        self.assertEqual(ev["주식회사 엠디스틸"]["tier"], "A")  # 1차 철강(241) + 개시, 종업원 85명
        self.assertEqual(ev["주식회사 엠디스틸"]["industry"]["label"], "1차 철강")
        self.assertEqual(ev["주식회사 엠디스틸"]["industry"]["employees"], 85)
        self.assertEqual(ev["주식회사 한빛오토텍"]["tier"], "B")  # 금속가공(25) + 자동차 주생산품 + 포괄적 금지명령
        self.assertEqual(ev["주식회사 한빛오토텍"]["match"], "product")
        self.assertEqual(ev["주식회사 메탈153"]["tier"], "A")  # 협력사 명단
        self.assertEqual(ev["주식회사 메탈153"]["watch"]["beat"], "현대제철")
        self.assertEqual(ev["주식회사 팩슨"]["tier"], "B")  # 자동차 부품 + 폐지
        self.assertEqual((ev["주식회사 금진테크"]["match"], ev["주식회사 금진테크"]["tier"]), ("related", "C"))  # 관련 업종, 출입 업종 주생산품 아님
        self.assertNotIn("주식회사 동네빵집", ev)  # 빵류: 출입 업종 아님
        self.assertNotIn("의료법인 정애의료재단", ev)
        self.assertEqual(sum(1 for e in doc["events"] if e["company"] == "주식회사 엠디스틸"), 1)  # 제출기간 연장 공고는 버림
        self.assertNotIn("메탈153", calls["factory"])  # 명단에 있으면 조회 안 함
        self.assertTrue(all(e["isNew"] for e in doc["events"]))
        self.assertEqual(doc["status"], "complete")
        ma = [e for e in doc["events"] if e["source"] == "회생회사 M&A 공고"]
        self.assertEqual(ma, [])  # 파이프텍코리아: 공장등록 없음, 이름 낱말 없음 → 버림

    def test_baseline_then_new_and_cache(self):
        post, get, calls = fakes()
        first = k.run("key", now=NOW, previous=None, post=post, get=get, sleep=lambda s: None, watchlist={})
        self.assertTrue(all(e["baseline"] and not e["isNew"] for e in first["events"]))
        self.assertEqual(first["windowStart"], "2026-10-15")
        n_calls = len(calls["factory"])
        more = SEOUL + [notice("000221", "20262920001200", "주식회사 엠디스틸", "회생절차 폐지결정 공고", "34", day="20261029", seq=9)]
        post2, get2, calls2 = fakes(rows_by_court={"000221/4": more})
        second = k.run("key", now=NOW + dt.timedelta(days=1), previous=first, post=post2, get=get2, sleep=lambda s: None, watchlist={})
        new = [e for e in second["events"] if e["isNew"]]
        self.assertEqual([(e["company"], e["kind"], e["tier"]) for e in new], [("주식회사 엠디스틸", "회생 폐지", "B")])
        self.assertEqual(calls2["factory"], [])  # 90일 안의 업종 조회 결과를 다시 쓴다
        self.assertGreater(n_calls, 0)
        self.assertEqual(second["windowStart"], "2026-10-27")

    def test_same_name_elsewhere_is_downgraded(self):
        suwon = [notice("000249", "20262920000227", "삼보산업 주식회사", "회생절차 개시결정 공고", "26"),
                 notice("000249", "20262920000228", "주식회사 서우", "회생절차 개시결정 공고", "26"),
                 notice("000249", "20262920000229", "주식회사 세명테크", "회생절차 개시결정 공고", "26")]
        fac = {
            "삼보산업": [{"fctryManageNo": "9", "cmpnyNm": "삼보산업(주)", "rnAdres": "대구광역시 서구 염색공단천로", "allEmplyCo": "22", "rprsntvNm": "김",
                       "rprsntvIndutyCode": "30332", "indutyNm": "자동차 부품", "mainProductCn": "자동차부품"}],
            "서우": [{"fctryManageNo": "10", "cmpnyNm": "(주)서우", "rnAdres": "대구광역시 달서구", "allEmplyCo": "60", "rprsntvNm": "박", "rprsntvIndutyCode": "30332",
                     "indutyNm": "자동차 부품", "mainProductCn": "시트"},
                    {"fctryManageNo": "11", "cmpnyNm": "주식회사 서우", "rnAdres": "경기도 화성시", "allEmplyCo": "6", "rprsntvNm": "이", "rprsntvIndutyCode": "30332",
                     "indutyNm": "자동차 부품", "mainProductCn": "브레이크"}],
            "세명테크": [{"fctryManageNo": str(20 + i), "cmpnyNm": "세명테크", "rnAdres": "경기도 안산시", "allEmplyCo": "10", "rprsntvNm": n, "rprsntvIndutyCode": "30399",
                       "indutyNm": "자동차 부품", "mainProductCn": "부품"} for i, n in enumerate("가나다")],
        }
        post, get, _ = fakes(rows_by_court={"000249/4": suwon}, factories=fac)
        doc = k.run("key", now=NOW, previous={"events": [], "generatedAt": "2026-10-28T17:20:00+09:00"}, post=post, get=get, sleep=lambda s: None, watchlist={})
        ev = {e["company"]: e for e in doc["events"]}
        self.assertEqual((ev["삼보산업 주식회사"]["tier"], ev["삼보산업 주식회사"]["industry"]["regionMismatch"]), ("B", True))  # 수원 법원, 대구 공장
        # 관할 안 공장을 고른다(종업원 6명이라 A가 아니라 B — 50명 미만 규칙)
        self.assertEqual((ev["주식회사 서우"]["tier"], ev["주식회사 서우"]["industry"]["address"]), ("B", "경기도 화성시"))
        self.assertEqual((ev["주식회사 세명테크"]["tier"], ev["주식회사 세명테크"]["industry"]["owners"]), ("B", 3))  # 같은 이름 대표자 3명

    def test_small_firms_are_not_a(self):
        # 10-31 운영: 보성알앤디(자동차 부품, 종업원 17명) 회생 개시가 A — 최근 30일 A 대부분이 5~37명 업체
        ind = {"employees": 17}
        self.assertEqual(k.tier_of("start", "core", None, ind), "B")
        self.assertEqual(k.tier_of("start", "core", None, {"employees": 166}), "A")
        self.assertEqual(k.tier_of("start", "core", None, {"employees": None}), "A")  # 모르면 그대로
        self.assertEqual(k.tier_of("start", "core", {"beat": "현대차"}, ind), "A")  # 협력사 명단은 A
        self.assertEqual(k.tier_of("end", "core", None, ind), "B")  # 이미 B인 단계는 그대로
        self.assertEqual(k.tier_of("start", "core", None, {"employees": 17, "owners": 3}), "B")  # 이름 의심과 겹쳐도 한 단계만
        # 11-01 운영: 종업원 0명(등록만 남은 공장) 파산 선고가 B — 공급망 단서 아님
        self.assertEqual(k.tier_of("start", "core", None, {"employees": 0, "owners": 6}), "C")
        self.assertEqual(k.tier_of("start", "core", {"beat": "현대차"}, {"employees": 0}), "A")  # 협력사 명단은 그대로

    def test_rehabilitation_courts_cover_their_high_court_area(self):
        self.assertTrue(k.region_rx("부산회생법원").search("울산광역시 남구 용연로"))
        self.assertTrue(k.region_rx("광주회생법원").search("전북특별자치도 완주군"))
        self.assertFalse(k.region_rx("울산지방법원").search("경기도 용인시"))
        self.assertIsNone(k.region_rx("서울회생법원"))
        self.assertTrue(k.region_rx("대전지방법원").search("세종특별자치시"))

    def test_lookup_budget_leaves_pending(self):
        many = [notice("000221", f"2026292000{i:04d}", f"주식회사 스틸{i}", "회생절차 개시결정 공고", "26", seq=i) for i in range(5)]
        post, get, calls = fakes(rows_by_court={"000221/4": many}, factories={})
        old = k.LOOKUP_BUDGET
        k.LOOKUP_BUDGET = 2
        try:
            doc = k.run("key", now=NOW, previous=None, post=post, get=get, sleep=lambda s: None, watchlist={})
        finally:
            k.LOOKUP_BUDGET = old
        chk = [c for c in doc["checks"] if c["source"] == "공장등록 업종 조회"][0]
        self.assertEqual((chk["status"], chk["pending"]), ("partial", 4))  # 스틸 3 + M&A 1
        self.assertTrue(all(e["tier"] == "C" and e["match"] == "name" for e in doc["events"]))  # 공장등록 없음 → 이름 낱말만

    def test_court_failures_are_not_zero(self):
        post, get, _ = fakes(fail_courts={c for c, _ in k.COURTS})
        doc = k.run("key", now=NOW, previous=None, post=post, get=get, sleep=lambda s: None, watchlist={})
        self.assertEqual(doc["status"], "failed")
        post, get, _ = fakes(fail_courts={"000443"})
        doc = k.run("key", now=NOW, previous=None, post=post, get=get, sleep=lambda s: None, watchlist={})
        self.assertEqual(doc["status"], "partial")
        self.assertTrue(any(c["source"] == "부산회생법원 법인회생" and c["status"] == "failed" for c in doc["checks"]))

    def test_site_down_fails_fast_and_court_windows_keep_the_gap(self):
        post, get, calls = fakes()
        first = k.run("key", now=NOW, previous=None, post=post, get=get, sleep=lambda s: None, watchlist={})
        self.assertEqual(set(first["courtLastOk"]), {f"{c} {t}" for _, c in k.COURTS for _, t in k.TASKS})
        # 10-30 07:20처럼 대법원 사이트가 통째로 안 열리면: 앞 4곳만 시도하고 나머지는 건너뛰고, 실패로 끝나 저장하지 않는다
        post2, get2, calls2 = fakes(fail_courts={c for c, _ in k.COURTS})
        down = k.run("key", now=NOW + dt.timedelta(days=1), previous=first, post=post2, get=get2, sleep=lambda s: None, watchlist={})
        self.assertEqual(down["status"], "failed")
        self.assertEqual(calls2["list"], k.DOWN_AFTER * 2)  # 법원마다 두 번(20초·45초) 시도
        self.assertIn("대법원 사이트 접속 불가", next(c for c in down["checks"] if c["source"] == "부산회생법원 법인회생")["error"])
        # 한 법원만 며칠 실패하면 그 법원은 마지막으로 다 읽은 날부터 다시 본다(다른 법원은 평소대로)
        post3, get3, _ = fakes(fail_courts={"000443"})
        part = k.run("key", now=NOW + dt.timedelta(days=1), previous=first, post=post3, get=get3, sleep=lambda s: None, watchlist={})
        post4, get4, _ = fakes()
        later = k.run("key", now=NOW + dt.timedelta(days=5), previous=part, post=post4, get=get4, sleep=lambda s: None, watchlist={})
        since = {c["source"]: c.get("since") for c in later["checks"]}
        self.assertEqual(since["부산회생법원 법인회생"], "2026-10-27")  # 첫 실행(10-29) − 2일
        self.assertEqual(since["서울회생법원 법인회생"], "2026-10-28")  # 10-30 성공 − 2일
        self.assertEqual(later["windowStart"], "2026-10-27")

    def test_no_key_marks_industry_unset(self):
        post, get, calls = fakes()
        doc = k.run("", now=NOW, previous=None, post=post, get=get, sleep=lambda s: None, watchlist={})
        chk = [c for c in doc["checks"] if c["source"] == "공장등록 업종 조회"][0]
        self.assertEqual(chk["status"], "unset")
        self.assertEqual(calls["factory"], [])
        names = {e["company"] for e in doc["events"]}
        self.assertEqual(names, {"주식회사 엠디스틸", "주식회사 메탈153"})  # 이름 낱말(스틸·메탈)만 C


if __name__ == "__main__":
    unittest.main()
