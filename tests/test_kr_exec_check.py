import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import kr_exec_check as kc  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 5, 5, 50, tzinfo=KST)
AS_OF = dt.date(2026, 6, 30)
OWN = ["현대자동차", "현대차", "기아", "현대모비스", "현대위아", "현대제철"]


class R:
    def __init__(self, body):
        self.status_code, self._body = 200, body

    def json(self):
        return self._body

    def raise_for_status(self):
        pass


def api(rcept, people):
    return {"status": "000", "list": [{"rcept_no": rcept, "nm": n, "birth_ym": b, "ofcps": o, "rgist_exctv_at": reg, "fte_at": "비상근",
                                       "chrg_job": "-", "main_career": c, "mxmm_shrholdr_relate": "-", "hffc_pd": per, "tenure_end_on": "2028년 03월 19일"}
                                      for n, b, o, reg, c, per in people]}


class Rules(unittest.TestCase):
    def test_tenure(self):
        self.assertEqual(kc.tenure_months("6년 3개월", AS_OF), 75)
        self.assertEqual(kc.tenure_months("75개월", AS_OF), 75)
        self.assertEqual(kc.tenure_months("2019.03~", AS_OF), 87)
        self.assertEqual(kc.tenure_months("2013년4월1일 ~", AS_OF), 158)
        self.assertEqual(kc.tenure_months("21.4", AS_OF), 62)
        self.assertEqual(kc.tenure_months("3년", AS_OF), 36)
        self.assertIsNone(kc.tenure_months("-", AS_OF))

    def test_current_directorships_skip_nonprofits_and_own_group(self):
        career = "現) ○○전자㈜ 사외이사 / 現) △△화학 감사 / 現) 한국경영학회 이사 / 現) 기아 사외이사 / 前) ◇◇건설 사외이사"
        self.assertEqual(kc.current_directorships(career, OWN), ["現) ○○전자㈜ 사외이사", "現) △△화학 감사"])

    def test_affiliate_recent(self):
        self.assertEqual(kc.affiliate_recent("2021~2024 현대모비스 전무 / 2025~현재 ○○대 교수", OWN, AS_OF), ["2021~2024 현대모비스 전무"])
        self.assertEqual(kc.affiliate_recent("2010~2015 현대모비스 전무", OWN, AS_OF), [])            # 3년 넘음
        self.assertEqual(kc.affiliate_recent("2024~ 기아 사외이사", OWN, AS_OF), [])                   # 사외이사 경력은 상무 종사 아님

    def test_internal_exec_company_incident_is_not_a_person_lead(self):
        items = [{"title": "현대차 공장 사망사고…정회장 사과", "text": "현대차", "date": "2026-10-01", "url": "c1"},
                 {"title": "정회장 음주운전 적발", "text": "현대차 정회장", "date": "2026-10-02", "url": "c2"}]
        hits = kc.news_hits(items, "정회장", ["현대차"], skip_in_title=["현대차", "현대자동차"])
        self.assertEqual([h["url"] for h in hits], ["c2"])
        self.assertEqual(kc.current_directorships("현) 교보생명 사외이사 / 현) KPMG ACI(감사위원회 지원센터) 자문교수", OWN), ["현) 교보생명 사외이사"])

    def test_columns_speeches_and_namesakes_are_not_leads(self):
        items = [{"title": "[시론/오윤]해외유출 탈세자금에 ‘방울’ 달자", "text": "롯데케미칼", "url": "x1"},
                 {"title": "김현웅 법무부장관 \"불법 집회, 끝까지 추적\"", "text": "HD현대오일뱅크", "url": "x2"},
                 {"title": "박현주 시옷 대표 “車 해킹 취약”", "text": "LS", "url": "x3"},
                 {"title": "이호준 중견련 상근부회장, 중기소식", "text": "OCI", "url": "x4"},
                 {"title": "허연수 책임론…GS리테일 166만명 정보 유출", "text": "GS", "url": "x5"}]
        names = {"x1": "오윤", "x2": "김현웅", "x3": "박현주", "x4": "이호준", "x5": "허연수"}
        kept = [it["url"] for it in items if kc.news_hits([it], names[it["url"]], ["롯데케미칼", "HD현대오일뱅크", "LS", "OCI", "GS"])]
        self.assertEqual(kept, ["x5"])
        self.assertTrue(kc.keep_title("허연수 책임론…GS리테일 정보 유출", "허연수"))
        self.assertFalse(kc.keep_title("[박재환 교수의 회계로 읽는 자본시장] 피싱과 분식회계", "박재환"))

    def test_official_duty_quotes(self):
        self.assertFalse(kc.keep_title('김현웅 법무부장관, 민노총 총파업 대회 예고에 "불법파업 책임 추궁할...', "김현웅"))
        self.assertFalse(kc.keep_title("유영숙 환경부장관, 칠곡 고엽제 의혹 캠프캐럴 방문", "유영숙"))
        self.assertTrue(kc.keep_title("박순애 교육부장관 후보자, '음주운전'에 '논문표절' 논란", "박순애"))       # 그 사람의 일
        self.assertTrue(kc.keep_title("영풍·MBK “최윤범, 회사자금 유용 의혹에 직접 답해야”", "최윤범"))       # 남이 그 사람을 두고 한 말
        self.assertTrue(kc.keep_title("GS리테일 166만명 정보 유출…전담조직도 없었다, 허연수·허서홍 책임은...", "허연수"))

    def test_news_hits(self):
        items = [{"title": "홍길동 전 한빛카드 대표, 해킹 사고 책임지고 사퇴", "text": "한빛카드 …", "date": "2025-12-10", "url": "u1"},
                 {"title": "현대차, 신차 출시", "text": "홍길동 사외이사 …", "date": "2026-01-01", "url": "u2"},
                 {"title": "홍길동 교수 칼럼: 소송 남발 문제", "text": "현대차와 무관", "date": "2026-02-01", "url": "u3"}]
        hits = kc.news_hits(items, "홍길동", ["한빛카드"])
        self.assertEqual([(h["url"], h["strong"], h["word"]) for h in hits], [("u1", True, "해킹")])
        self.assertEqual(kc.main_org("前 한빛카드 대표이사 / 現 △△대 교수", OWN), "한빛카드")


class Runs(unittest.TestCase):
    def setUp(self):
        self.data = {("00164742", 2026, "11014"): None,
                     ("00164742", 2026, "11012"): api("20260814003521", [
                         ("정회장", "1970년 10월", "회장", "사내이사", "기아자동차 사장", "2025.3.20~"),
                         ("김오래", "1955년 01월", "이사", "독립이사", "前 한빛카드 대표이사 / 現) 오성전자㈜ 사외이사 / 現) 한결화학 감사", "7년 2개월"),
                         ("이최근", "1962년 03월", "이사", "독립이사", "2021~2024 현대모비스 전무", "1년")])}
        self.calls, self.codes = [], []

    def get(self, url, params=None, **kw):
        self.calls.append(url.rsplit("/", 1)[-1])
        self.codes.append(params["corp_code"])
        body = self.data.get((params["corp_code"], int(params["bsns_year"]), params["reprt_code"]))
        return R(body or {"status": "013"})

    def news(self, q):
        self.calls.append(("news", q))
        if q == "김오래 한빛카드":
            return {"status": "ok", "items": [{"title": "김오래 한빛카드 대표, 고객정보 유출 책임지고 사퇴", "text": "한빛카드 해킹", "date": "2025-12-10", "url": "n1"}]}
        return {"status": "ok", "items": []}

    def article(self, url):
        return {"status": "ok", "url": url, "method": "fixture", "body":
                "김오래 한빛카드 대표는 고객정보 유출 사고의 책임을 지고 사퇴했다. "
                "이 자료는 테스트용 가상 인물과 기업을 사용하며 실제 사건을 뜻하지 않는다. " * 2}

    def go(self, previous=None, table=None, exec_doc=None, **kw):
        exec_doc = exec_doc if exec_doc is not None else {"rosters": {"현대자동차": {"people": [["박사장", "1966.02", "사장", "미등기", "", "", "제조"]]},
                                                                    "기아": {"people": [["김오래", "1955.01", "이사", "사외이사", "", "", ""]]}}}
        return kc.run("k", now=NOW, previous=previous, exec_doc=exec_doc, get=self.get, news=self.news, sleep=lambda s: None,
                      registry={"companies": {"현대자동차": {"corp_code": "00164742"}}}, table=table if table is not None else {},
                      article_fetch=self.article, **kw)

    def test_flags(self):
        doc = self.go()
        p = {x["name"]: x for x in doc["people"] if x["company"] == "현대차"}
        self.assertEqual(set(p), {"정회장", "김오래", "이최근", "박사장"})                 # 미등기 사장급도 기사 점검
        kinds = {f["kind"]: f for f in p["김오래"]["flags"]}
        self.assertEqual(set(kinds), {"법정 한도: 재직 6년 초과 가능", "겸직 확인: 경력 칸 현직 이사·감사", "과거 논란 기사"})
        self.assertIn("7년 2개월", kinds["법정 한도: 재직 6년 초과 가능"]["text"])
        self.assertEqual(kinds["겸직 확인: 경력 칸 현직 이사·감사"]["tier"], "B")         # 경력 칸만으로는 B
        self.assertIn("기아: 명단 순환·출입처 명단에서 확인", kinds["겸직 확인: 경력 칸 현직 이사·감사"]["text"])
        self.assertIn("오성전자: DART 고유번호 못 찾음", kinds["겸직 확인: 경력 칸 현직 이사·감사"]["text"])   # 표가 없으면 확인 불가로 남긴다
        self.assertEqual(kinds["과거 논란 기사"]["tier"], "B")
        self.assertIn("고객정보 유출 책임지고 사퇴", kinds["과거 논란 기사"]["text"])
        self.assertEqual([f["kind"] for f in p["이최근"]["flags"]], ["독립성: 같은 그룹 최근 근무 가능"])
        self.assertEqual(p["정회장"]["flags"], [])                                        # 사내이사는 법정 한도 점검 대상 아님
        self.assertIn(("news", "김오래 한빛카드"), self.calls)
        self.assertEqual(doc["counts"]["A"], 1)
        self.assertTrue(all(e["id"].startswith("execc:") and e.get("baseline") for e in doc["events"]))   # 첫 실행은 기준선
        again = self.go(previous=doc)
        self.assertEqual(again["counts"]["newEvents"], 0)
        self.assertEqual(again["counts"]["newsChecked"], 0)                               # 14일 안엔 기사를 다시 찾지 않는다
        self.assertEqual({f["kind"] for x in again["people"] if x["name"] == "김오래" for f in x["flags"]}, set(kinds))

    def test_body_failure_preserves_history_without_live_flag(self):
        first = self.go()
        from unittest.mock import patch
        self.article = lambda url: {"status": "fetch_failed"}
        with patch.object(kc, "REFRESH", True):
            doc = self.go(previous=first)
        p = next(p for p in doc["people"] if p["name"] == "김오래")
        self.assertEqual(p["newsStatus"], "ok")
        self.assertEqual(p["bodyStatus"], "unconfirmed")
        self.assertFalse(any(f["kind"] == "과거 논란 기사" for f in p["flags"]))
        self.assertEqual(next(e["reviewStatus"] for e in doc["events"] if e["kind"] == "과거 논란 기사"), "unconfirmed")
        self.assertEqual(doc["counts"]["articleReview"], {"fetch_failed": 1})

    def test_body_budget_is_retried_without_researching_news(self):
        first = self.go(article_budget=0)
        self.assertEqual(first["counts"]["articleReview"], {"budget_exhausted": 1})
        doc = self.go(previous=first)
        self.assertEqual(doc["counts"]["newsChecked"], 0)
        self.assertEqual(doc["counts"]["articleReview"], {"context_linked": 1})

    def test_listed_rosters_confirm_two_other_boards(self):
        import hashlib
        h = hashlib.sha256("김오래|195501".encode()).hexdigest()[:8]
        market = {"companies": {"00999001": {"n": "디비보험", "p": "202611012", "dk": [h]}, "00999002": {"n": "에스부품", "p": "202611012", "dk": [h]}}}
        exec_doc = {"rosters": {}}
        doc = kc.run("k", now=NOW, exec_doc=exec_doc, market_doc=market, get=self.get, news=self.news, sleep=lambda s: None,
                     registry={"companies": {"현대자동차": {"corp_code": "00164742"}}}, table={}, article_fetch=self.article)
        f = next(f for x in doc["people"] if x["name"] == "김오래" for f in x["flags"] if f["kind"].startswith("법정 한도: 다른 회사"))
        self.assertEqual(f["tier"], "A")
        self.assertIn("디비보험: 명단 순환·출입처 명단에서 확인", f["text"])
        self.assertIn("에스부품: 명단 순환·출입처 명단에서 확인", f["text"])
        self.assertEqual(kc.current_directorships("('17 ~ '19) ㈜GS글로벌 대표이사 / ('20 ~ 현재) 코스맥스㈜ 감사", OWN), ["('20 ~ 현재) 코스맥스㈜ 감사"])

    def test_news_budget_and_failure(self):
        doc = self.go(news_budget=2)
        self.assertTrue(any(c["source"] == "네이버 뉴스" and c.get("pending") for c in doc["checks"]))
        self.news = lambda q: {"status": "failed", "items": []}
        doc2 = self.go()
        self.assertTrue(any(c["source"] == "네이버 뉴스" and "검색 실패" in c.get("error", "") for c in doc2["checks"]))

    def test_incomplete_birth_cannot_confirm_other_boards(self):
        import hashlib
        for birth in ("", "1955", "1955년", "1955.13"):
            body = self.data[("00164742", 2026, "11012")]
            body["list"][1]["birth_ym"] = birth
            h = hashlib.sha256(f"김오래|{kc.kx.birth_key(birth)}".encode()).hexdigest()[:8]
            market = {"companies": {str(i): {"n": f"비교회사{i}", "p": "202611012", "dk": [h]} for i in range(2)}}
            doc = self.go(market_doc=market)
            flags = next(p["flags"] for p in doc["people"] if p["name"] == "김오래")
            self.assertFalse(any(f["kind"].startswith("법정 한도: 다른 회사") for f in flags), birth)

    def test_partial_search_keeps_last_complete_time_and_retries(self):
        first = self.go()
        from unittest.mock import patch
        original = self.news
        def partial(q):
            return {"status": "failed", "items": []} if q == "김오래 현대차" else original(q)
        self.news = partial
        with patch.object(kc, "REFRESH", True):
            doc = self.go(previous=first)
        person = next(p for p in doc["people"] if p["name"] == "김오래")
        self.assertEqual(person["newsStatus"], "partial")
        self.assertEqual((person["newsQueriesCompleted"],person["newsQueriesExpected"]),(1,2))
        self.assertFalse(any(f["kind"] == "과거 논란 기사" for f in person["flags"]))
        self.assertTrue(any(c["source"] == "네이버 뉴스" and c["status"] == "partial" for c in doc["checks"]))
        self.calls.clear()
        self.go(previous=doc)
        self.assertIn(("news", "김오래 한빛카드"), self.calls)
        event = next(e for e in doc["events"] if e["kind"] == "과거 논란 기사")
        self.assertEqual(event["reviewStatus"], "unconfirmed")

    def test_budget_mid_person_is_not_a_complete_search(self):
        doc = self.go(news_budget=2) # 정회장 1회, 김오래의 2개 질의 중 1회만
        p = next(p for p in doc["people"] if p["name"] == "김오래")
        self.assertEqual(p["newsStatus"], "partial")
        self.assertIsNone(p["newsAt"])

    def test_removed_flag_stays_history_but_not_live_event(self):
        doc = self.go()
        event = next(e for e in doc["events"] if e["kind"] == "과거 논란 기사")
        for p in doc["people"]:
            if p["name"] == "김오래":
                p["news"] = [{"title": '[시론/김오래] 정보 유출 예방', "strong": True, "word": "유출", "url": "noise"}]
        new = self.go(previous=doc)
        old = next(e for e in new["events"] if e["id"] == event["id"])
        self.assertEqual(old["reviewStatus"], "inactive")
        self.assertEqual(old["detectedAt"], event["detectedAt"])

    def test_failed_roster_does_not_resolve_old_flags(self):
        doc = self.go()
        self.get = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("unavailable"))
        new = self.go(previous=doc)
        self.assertTrue(new["events"])
        self.assertTrue(all(e["reviewStatus"] == "unconfirmed" for e in new["events"]))

    def test_legacy_ambiguous_person_is_not_reactivated(self):
        event = {"id":"legacy", "company":"현대차", "person":{"name":"동명이인", "birth":"1960"}, "flags":[{"kind":"과거 논란 기사","text":"old"}]}
        people = [dict(id=str(i),company="현대차",name="동명이인",birth="1960",flags=event["flags"],newsStatus="ok") for i in range(2)]
        kc.reconcile_events({"legacy":event},people,[{"source":"현대차","status":"ok"}],NOW.isoformat())
        self.assertEqual(event["reviewStatus"],"unconfirmed")


    def test_naver_inlink_is_read_first_original_kept(self):
        fetched, base = [], self.article
        def article(url):
            fetched.append(url)
            return base(url)
        self.article = article
        original = self.news
        def news(q):
            res = original(q)
            for it in res["items"]:
                it["naverUrl"] = "https://n.news.naver.com/mnews/article/001/0000000001"
            return res
        self.news = news
        doc = self.go()
        p = next(x for x in doc["people"] if x["name"] == "김오래")
        self.assertEqual(fetched, ["https://n.news.naver.com/mnews/article/001/0000000001"])
        self.assertEqual(p["news"][0]["url"], "n1")                      # 원문 주소는 그대로
        self.assertEqual(p["bodyStatus"], "linked")

    def test_unread_body_is_retried_next_run(self):
        base = self.article
        self.article = lambda url: {"status": "unsupported_source"}
        first = self.go()
        self.assertEqual(first["counts"]["articleReview"], {"unsupported_source": 1})
        self.assertTrue(any(c["source"] == "기사 본문" and c.get("hosts") for c in first["checks"]))
        self.article = base
        doc = self.go(previous=first)                                  # 하루 안이라도 못 읽은 것은 다시 읽는다
        self.assertEqual(doc["counts"]["articleReview"], {"context_linked": 1})

    # ---- 공식 제재 기록 대조 ----
    def test_official_sanctions_overlap_is_b_unknown_timing_is_c(self):
        from unittest.mock import patch
        import official_sanctions as osn
        body = self.data[("00164742", 2026, "11012")]
        body["list"][1]["main_career"] = "(2019~2021) 한빛카드 대표이사 / 前) 오성증권 사장"
        prev = {"schema": kc.SCHEMA, "people": [], "events": [], "sanctions": {
            "fss": {"done": True, "rows": {"fss:202100001-1": {"id": "fss:202100001-1", "org": "한빛카드주식회사", "date": "2021-10-26"},
                                           "fss:201500001-1": {"id": "fss:201500001-1", "org": "오성증권㈜", "date": "2015-01-01"}}},
            "pipc": {"posts": {"1": [{"agency": "개인정보위", "id": "pipc:1:1", "org": "한빛카드", "date": "2022-03-18", "what": "안전조치의무",
                                       "inst": "과징금 7,088만원", "major": True, "url": "https://www.pipc.go.kr/x"}]}}}}

        class W:
            def __init__(self, text="", content=b""):
                self.text, self.content, self.status_code = text, content, 200
        pages = []

        def web(url, **kw):
            pages.append(url)
            if "selectBoard" in url or "list.do" in url:
                return W("")
            if "view.do" in url:
                return W('<a href="/fss.hpdownload?path=/dtm/opn/&amp;file=x.pdf">x.pdf</a>')
            return W(content=b"%PDF-1.4")
        pdf = ("3. 제재조치내용 대상 내용 기 관 기관경고 임 원 주의적 경고 : 2명 직 원 등 견책 1명 4. 제재대상사실 가. 문책사항")
        with patch.object(osn, "pdf_text", lambda raw, n=4: pdf):
            doc = self.go(previous=prev, web_get=web)
        p = next(x for x in doc["people"] if x["name"] == "김오래")
        f = next(f for f in p["flags"] if f["kind"] == "공식 제재: 재임 중 소속 회사 제재")
        self.assertEqual(f["tier"], "B")
        self.assertIn("한빛카드 대표이사(경력 칸 2019~2021) — 개인정보위 2022-03-18 제재: 안전조치의무 — 과징금 7,088만원", f["text"])
        self.assertIn("금감원 2021-10-26 제재: 임원 주의적 경고 : 2명", f["text"])
        self.assertIn("공개 기록엔 개인 이름이 없음", f["text"])
        c = next(x for x in p["sanctions"] if x["org"] == "오성증권㈜")
        self.assertEqual((c["timing"], c["strong"]), ("timing_unknown", False))      # 시점 미확인 → C(목록만)
        self.assertEqual(sum(1 for u in pages if "view.do" in u), 1)                  # 공개안은 기간이 겹친 것만 연다
        again = self.go(previous=doc)                                                 # web_get 없음 → 앞 상태·공개안 요약 재사용
        self.assertTrue(any(f["kind"].startswith("공식 제재") for x in again["people"] if x["name"] == "김오래" for f in x["flags"]))
        self.assertEqual(again["counts"]["newEvents"], 0)

    # ---- 겸직 명단 직접 대조(3호) ----
    def boards(self, first=("1955년 01월", "사외이사"), second=("1955년 01월", "감사")):
        self.data[("00999001", 2026, "11012")] = api("20260814000001", [("김오래", first[0], "이사", first[1], "", "2년")])
        self.data[("00999002", 2026, "11012")] = api("20260814000002", [("김오래", second[0], "감사", second[1], "", "1년")])
        return {"오성전자": [["00999001", "111111"]], "한결화학": [["00999002", ""]], "한결화학(주)": [["00999002", ""]]}

    def test_named_boards_are_opened_and_confirmed(self):
        doc = self.go(table=self.boards(), exec_doc={"rosters": {}})
        p = next(x for x in doc["people"] if x["name"] == "김오래")
        f = next(f for f in p["flags"] if f["kind"] == "법정 한도: 다른 회사 이사·감사 2곳 이상 가능")
        self.assertEqual(f["tier"], "A")
        self.assertIn("오성전자: 명단 확인(사외이사·2026년 반기(6-30 기준))", f["text"])
        self.assertIn("한결화학: 명단 확인", f["text"])
        self.assertIn("동시 재임·선임일은 각 회사 공시로 확인", f["text"])
        self.assertFalse(any(f["kind"].startswith("겸직 확인") for f in p["flags"]))
        self.assertEqual({d["status"] for d in p["directorChecks"]}, {"confirmed"})
        self.assertTrue(any(c["source"] == "겸직 명단 대조" and c["status"] == "ok" and c["companies"] == 2 for c in doc["checks"]))
        # 앞 철(반기) 보고서로 본 것은 3일 안엔 다시 열지 않고, 3일이 지나면 새 분기보고서를 찾으러 다시 연다
        self.codes.clear()
        again = self.go(previous=doc, table=self.boards(), exec_doc={"rosters": {}})
        self.assertNotIn("00999001", self.codes)
        self.assertEqual(again["counts"]["newEvents"], 0)
        later = kc.run("k", now=NOW + kc.dt.timedelta(days=4), previous=doc, exec_doc={"rosters": {}}, get=self.get, news=self.news,
                       sleep=lambda s: None, registry={"companies": {"현대자동차": {"corp_code": "00164742"}}}, table=self.boards(),
                       article_fetch=self.article)
        self.assertIn("00999001", self.codes)
        self.data[("00999001", 2026, "11014")] = api("20261114000001", [("김오래", "1955년 01월", "이사", "사외이사", "", "2년")])
        self.codes.clear()
        q3 = kc.run("k", now=NOW + kc.dt.timedelta(days=9), previous=later, exec_doc={"rosters": {}}, get=self.get, news=self.news,
                    sleep=lambda s: None, registry={"companies": {"현대자동차": {"corp_code": "00164742"}}}, table=self.boards(),
                    article_fetch=self.article)
        d = next(d for x in q3["people"] if x["name"] == "김오래" for d in x["directorChecks"] if d["org"] == "오성전자")
        self.assertEqual((d["period"], d["report"][:9]), ("202611014", "2026년 3분기"))
        self.codes.clear()
        kc.run("k", now=NOW + kc.dt.timedelta(days=14), previous=q3, exec_doc={"rosters": {}}, get=self.get, news=self.news,
               sleep=lambda s: None, registry={"companies": {"현대자동차": {"corp_code": "00164742"}}}, table=self.boards(), article_fetch=self.article)
        self.assertNotIn("00999001", self.codes)                        # 지금 철 보고서까지 본 것은 14일 재사용

    def test_namesake_and_absent_are_not_counted(self):
        table = self.boards(second=("1961년 03월", "감사"))          # 같은 이름 다른 출생연도
        doc = self.go(table=table, exec_doc={"rosters": {}})
        p = next(x for x in doc["people"] if x["name"] == "김오래")
        self.assertFalse(any("다른 회사" in f["kind"] or f["kind"].startswith("겸직 확인") for f in p["flags"]))
        self.assertEqual({d["org"]: d["status"] for d in p["directorChecks"]}, {"오성전자": "confirmed", "한결화학": "namesake"})
        del self.data[("00999002", 2026, "11012")]                    # 보고서 없음 → 현직 표기라 확인 불가 → B
        doc = self.go(table=table, exec_doc={"rosters": {}})
        p = next(x for x in doc["people"] if x["name"] == "김오래")
        f = next(f for f in p["flags"] if f["kind"].startswith("겸직 확인"))
        self.assertEqual(f["tier"], "B")
        self.assertIn("한결화학: 최근 정기보고서 없음(확인 불가)", f["text"])

    def test_same_company_from_market_is_counted_once(self):
        import hashlib
        h = hashlib.sha256("김오래|195501".encode()).hexdigest()[:8]
        market = {"companies": {"00999001": {"n": "오성전자", "p": "202611012", "dk": [h]}}}
        table = self.boards()
        self.data[("00999002", 2026, "11012")] = api("20260814000002", [("다른사람", "1950년 01월", "감사", "감사", "", "1년")])
        doc = self.go(table=table, exec_doc={"rosters": {}}, market_doc=market)
        p = next(x for x in doc["people"] if x["name"] == "김오래")
        self.assertFalse(any("다른 회사" in f["kind"] or f["kind"].startswith("겸직 확인") for f in p["flags"]))   # 오성전자 1곳뿐
        self.assertNotIn("00999001", self.codes)                     # 명단 순환에서 본 회사는 다시 열지 않는다
        self.assertEqual({d["org"]: d["status"] for d in p["directorChecks"]}, {"오성전자": "filed", "한결화학": "absent"})

    def test_lookup_budget_is_unconfirmed_not_zero(self):
        from unittest.mock import patch
        with patch.object(kc, "DIRECTOR_BUDGET", 0):
            doc = self.go(table=self.boards(), exec_doc={"rosters": {}})
        p = next(x for x in doc["people"] if x["name"] == "김오래")
        f = next(f for f in p["flags"] if f["kind"].startswith("겸직 확인"))
        self.assertIn("한 실행 조회 한도", f["text"])
        self.assertTrue(any(c["source"] == "겸직 명단 대조" and c["status"] == "partial" for c in doc["checks"]))
        again = self.go(previous=doc, table=self.boards(), exec_doc={"rosters": {}})   # 한도로 못 본 것은 다음 실행에 연다
        self.assertTrue(any(f["kind"].startswith("법정 한도: 다른 회사") for x in again["people"] if x["name"] == "김오래" for f in x["flags"]))

    def test_director_orgs_from_glued_career(self):
        career = ("現)디비손보(주) 독립이사 (現)엘에이치자산(주) 부문장 에스부품(주) 독립이사케이자산운용 경영자문역 금융투자협회 비상근 부회장"
                  "케이자산운용 대표이사 사장 / ('17 ~ '19) ㈜지에스글로벌 대표이사 / 2019~2021 대성산업 사외이사 / 現) 한국경영학회 이사 / 前) 오성건설 사외이사")
        got = [(o["org"], o["current"]) for o in kc.director_orgs(career, OWN)]
        self.assertEqual(got, [("디비손보", True), ("에스부품", True), ("케이자산운용", False)])
        self.assertEqual(kc.director_orgs("現) 현대모비스 사외이사 / 現)법무법인(유) 율촌 변호사 兼)(주)노브랜드 독립이사", OWN)[0]["org"], "노브랜드")

if __name__ == "__main__":
    unittest.main()
