"""Radar press check: hint → candidate, item-date window, verdict history, failures not zero."""
import datetime as dt
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import radar_press_check as rpc  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 28, 8, 50, tzinfo=KST)
SUIT = {"소송": ["소송", "제소", "판결", "항소", "불복"], "국제무역법원": ["국제무역법원", "무역법원", "CIT"]}

# Shape of /ingest/radar-items (digest.mjs radarItems).
ITEMS = [
    {"tier": "A", "watch": "미국 소송·ITC", "id": "cl:74869986", "date": "2026-09-29", "company": "포스코",
     "fact": "국제무역법원(무역구제 소송) · 원고: CIT 「POSCO v. United States」 접수", "url": "https://cl/1",
     "check": {"who": "포스코", "terms": ["국제무역법원", "소송"], "alts": SUIT}},
    {"tier": "A", "watch": "공장등록·관보", "id": "fac:448:2026-10-27", "date": "2026-10-27T11:09:00+09:00", "company": "KG스틸",
     "fact": "등록 내용 변경: 고용 856→690명",
     "check": {"who": "KG스틸", "terms": ["인력", "감축"], "alts": {"인력": ["인력", "인원", "직원"], "감축": ["감축", "감소", "희망퇴직"]}}},
    {"tier": "B", "watch": "국회 법안", "id": "bills:발의|대외무역법|2026-10-27", "date": "2026-10-27", "company": "통상·산업",
     "fact": "법안 발의: 대외무역법 일부개정법률안 — 최수진 대표발의",
     "check": {"who": "대외무역법", "terms": ["개정안", "최수진"], "alts": {"개정안": ["개정안", "발의", "법안"]}}},
    {"tier": "B", "watch": "공장등록·관보", "id": "fac:9", "date": "2026-10-27", "company": "효성중공업(관련)",
     "fact": "새 공장", "check": {"who": "효성중공업(관련)·일진전기", "terms": ["창원", "공장", "신설"], "alts": {}}},
    {"tier": "A", "watch": "공장등록·관보", "id": "fac:10", "date": "2026-10-27", "company": "현대위아", "fact": "업종 문구 변경"},  # no hint
]


class R:
    def __init__(self, code=200, body=None, content=b""):
        self.status_code, self.body, self.content = code, body or {}, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self.body


def article(title, day):
    d = dt.date.fromisoformat(day)
    return {"title": title, "description": "", "originallink": f"https://n/{abs(hash(title)) % 1000}",
            "pubDate": d.strftime("%a, %d %b %Y 09:00:00 +0900")}


def channels(naver_by_word, queries=None):
    def get(url, params=None, headers=None, timeout=None):
        if "naverapihub" in url or "openapi.naver.com" in url:
            q = params["query"]
            if queries is not None:
                queries.append(q)
            return R(200, {"items": [a for w, arts in naver_by_word.items() if w in q for a in arts]})
        return R(200, content=b"<rss><channel></channel></rss>")
    return get


OLD_POSCO = [article("포스코, 美 국제무역법원에 상계관세 소송", "2026-09-20")]  # before the item's window (09-26)
KG = [article("KG스틸, 당진공장 인력 감축 착수", "2026-10-27")]


def go(get, previous=None, now=NOW, naver=True):
    env = {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"} if naver else {"NAVER_CLIENT_ID": "", "NAVER_CLIENT_SECRET": ""}
    with patch.dict(os.environ, env):
        return rpc.run(ITEMS, now=now, previous=previous, get=get, sleep=lambda s: None)


class Candidates(unittest.TestCase):
    def test_hints_become_candidates_a_first_with_item_window(self):
        rows = rpc.candidates(ITEMS, now=NOW)
        self.assertEqual([r["id"] for r in rows], ["fac:448:2026-10-27", "cl:74869986", "bills:발의|대외무역법|2026-10-27", "fac:9"])
        by = {r["id"]: r for r in rows}
        self.assertEqual(by["cl:74869986"]["since"], "2026-09-26")
        self.assertEqual(by["fac:448:2026-10-27"]["since"], "2026-10-24")
        self.assertEqual(by["fac:9"]["company"], "효성중공업")  # '(관련)' and the second company dropped
        self.assertEqual(by["fac:9"]["alts"], {})
        self.assertEqual(by["cl:74869986"]["numbers"], [])  # no number matching for radar items

    def test_limit(self):
        many = [dict(ITEMS[1], id=f"x{i}") for i in range(60)]
        self.assertEqual(len(rpc.candidates(many, now=NOW)), rpc.MAX_ITEMS)


class Run(unittest.TestCase):
    def test_verdicts_respect_the_item_date(self):
        queries = []
        doc = go(channels({"포스코": OLD_POSCO, "KG스틸": KG}, queries))
        by = {r["id"]: r for r in doc["items"]}
        self.assertEqual(by["cl:74869986"]["verdict"], "미보도 후보")  # the only article predates the filing window
        self.assertEqual(by["fac:448:2026-10-27"]["verdict"], "관련 보도 있음")
        self.assertEqual(by["fac:448:2026-10-27"]["evidence"][0]["date"], "2026-10-27")
        self.assertEqual(by["bills:발의|대외무역법|2026-10-27"]["verdict"], "미보도 후보")
        self.assertIn("대외무역법 개정안 최수진", queries)
        self.assertIn("포스코 국제무역법원 소송", queries)
        self.assertEqual((doc["received"], doc["screened"]), (5, 4))
        self.assertEqual(doc["counts"]["미보도 후보"], 3)
        self.assertEqual(by["cl:74869986"]["firstVerdict"], "미보도 후보")
        self.assertEqual(doc["schema"], "radar_check/v1")

    def test_history_shows_when_a_story_appeared(self):
        first = go(channels({"포스코": OLD_POSCO}))
        later = NOW + dt.timedelta(hours=10)
        news = [article("포스코, 美 국제무역법원 상계관세 소송서 패소", "2026-10-28")]
        doc = go(channels({"포스코": news}), previous=first, now=later)
        r = next(x for x in doc["items"] if x["id"] == "cl:74869986")
        self.assertEqual(r["verdict"], "관련 보도 있음")
        self.assertEqual((r["firstVerdict"], r["firstCheckedAt"]), ("미보도 후보", NOW.isoformat(timespec="seconds")))
        self.assertEqual(r["checkedAt"], later.isoformat(timespec="seconds"))

    def test_items_no_longer_listed_are_kept_for_a_while(self):
        first = go(channels({}))
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            doc = rpc.run(ITEMS[:1], now=NOW + dt.timedelta(days=1), previous=first, get=channels({}), sleep=lambda s: None)
        self.assertIn("fac:448:2026-10-27", {r["id"] for r in doc["items"]})
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            old = rpc.run([], now=NOW + dt.timedelta(days=20), previous=doc, get=channels({}), sleep=lambda s: None)
        self.assertEqual(old["items"], [])

    def test_missing_naver_is_unconfirmed_not_unreported(self):
        doc = go(channels({}), naver=False)
        self.assertTrue(all(r["verdict"] == "미확인" for r in doc["items"]))
        self.assertEqual(doc["counts"]["미보도 후보"], 0)


def art(title, day, text=""):
    return dict(article(title, day), description=text)


class HeadlineRule(unittest.TestCase):
    """Production 10-28: body-only mentions pushed unreported items down as '관련 보도 있음'."""

    def one(self, item, arts):
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            return rpc.run([item], now=NOW, get=channels({"": arts}), sleep=lambda s: None)["items"][0]

    def test_company_only_in_someone_elses_story_is_weak(self):
        item = {"tier": "A", "watch": "미국 소송·ITC", "id": "cl:75015895", "date": "2026-10-23", "company": "현대제철",
                "check": {"who": "현대제철", "terms": ["국제무역법원", "소송"], "alts": SUIT}}
        r = self.one(item, [art("[단독] 포스코, 미국 상계관세 소송서 패소", "2026-10-28",
                                "포스코가 미국 국제무역법원 소송에서 졌다. 현대제철도 같은 법원에 소송을 냈다.")])
        self.assertEqual(r["verdict"], "미보도 후보")
        self.assertTrue(r["evidence"][0]["why"].startswith("본문에만"))

    def test_generic_words_do_not_mark_a_price_change_covered(self):
        item = {"tier": "A", "watch": "해외 공식 페이지", "id": "p1", "date": "2026-10-28T06:31:10+09:00", "company": "현대차",
                "check": {"who": "현대차", "terms": ["가격", "미국"], "alts": {"가격": ["가격", "판매가", "MSRP"], "미국": ["미국", "美"]}}}
        r = self.one(item, [art('"아우디도 美 공장 짓는다"…현대차·도요타 이어 현지화 속도', "2026-10-26")])
        self.assertEqual(r["verdict"], "미보도 후보")
        r = self.one(item, [art("현대차, 美 판매가 동결…투싼 2만7600달러", "2026-10-28")])
        self.assertEqual(r["verdict"], "관련 보도 있음")

    def test_headline_with_company_and_event_word_is_covered(self):
        item = {"tier": "A", "watch": "미국 소송·ITC", "id": "op:1", "date": "2026-10-27", "company": "포스코",
                "check": {"who": "포스코", "terms": ["국제무역법원", "판결", "상계관세"],
                          "alts": {**SUIT, "판결": ["판결", "패소", "승소"], "상계관세": ["상계관세"]}}}
        r = self.one(item, [art("[단독] 포스코, 미국 상계관세 소송서 패소", "2026-10-28")])
        self.assertEqual(r["verdict"], "관련 보도 있음")
        self.assertTrue(r["evidence"][0]["why"].startswith("제목에 회사·낱말"))

    def test_place_and_company_alone_do_not_mark_a_local_notice_covered(self):
        # 운영 10-31: 울주군 '건설공사 안전점검 수행기관 지정[온산 고려아연(주), #2ASU…]' ↔ 고려아연 사회공헌 기사
        new = {"신설": ["신설", "준공", "가동", "건설", "착공", "신축", "증설", "새 공장"], "공장": ["공장", "사업장", "생산기지"]}
        item = {"tier": "A", "watch": "지자체 고시·공고", "id": "local:울주군:68156", "date": "2026-10-27", "company": "고려아연",
                "check": {"who": "고려아연", "terms": ["울주", "신설", "공장"], "alts": new, "places": ["울주"]}}
        csr = art("고려아연 온산제련소 지원 울주군 취약계층 집수리 사업 '호응'", "2026-10-27")
        r = self.one(item, [csr])
        self.assertEqual(r["verdict"], "미보도 후보")
        r = self.one(item, [csr, art("고려아연, 울주 온산제련소에 산소공장 증설 착수", "2026-10-28")])
        self.assertEqual(r["verdict"], "관련 보도 있음")
        self.assertIn("신설", r["evidence"][0]["why"])
        # 지명 표시가 없던 예전 낱말이면(지명이 사건 낱말로 쳐짐) 같은 기사로 '관련 보도 있음'이 됐다
        old = dict(item, check={k: v for k, v in item["check"].items() if k != "places"})
        self.assertEqual(self.one(old, [csr])["verdict"], "관련 보도 있음")

    def test_stack_item_needs_the_site_city(self):
        # 운영 10-31 09:18: 포스코 광양제철소 배출구 멈춤(B)이 '포스코 포항제철소 … 설비 장애 감소' 기사로 '관련 보도 있음'
        item = {"tier": "B", "watch": "굴뚝 측정(공장 가동 신호)", "id": "stk:stop:포스코:광양", "date": "2026-10-27T09:17:00+09:00", "company": "포스코",
                "check": {"who": "포스코", "terms": ["광양", "가동 중단", "정비"], "alts": {}, "places": ["광양"], "must": ["광양"]}}
        pohang = art("포스코 포항제철소, 현장 혁신으로 설비 장애 감소·안전 강화", "2026-10-27", "설비 가동 중단을 줄이고 정비 체계를 바꿨다.")
        r = self.one(item, [pohang])
        self.assertEqual(r["verdict"], "미보도 후보")
        self.assertIn("사업장 지명(광양) 없음", r["evidence"][0]["why"])
        r = self.one(item, [pohang, art("포스코 광양제철소 3고로 정비 들어가", "2026-10-28")])
        self.assertEqual(r["verdict"], "관련 보도 있음")
        self.assertEqual(rpc.candidates([item], now=NOW)[0]["must"], ["광양"])

    def test_workforce_increase_is_not_matched_by_common_words(self):
        # 운영 10-31 09:18: 기아 가입자 증가(채용 낱말에 고용·인력이 들어 있었음)가 공장 재편 기사로 '관련 보도 있음'
        hire = ["채용", "증원", "충원", "신입", "공채", "인력 확대", "인원 확대", "인력 증가", "인원 증가"]
        item = {"tier": "B", "watch": "사업장 인력(국민연금)", "id": "wf:delta:기아", "date": "2026-10-27", "company": "기아",
                "check": {"who": "기아", "terms": ["채용"], "alts": {"채용": hire}}}
        r = self.one(item, [art("'효율·고용' 절충…현대차·기아 공장 재편안 나왔다", "2026-10-27")])
        self.assertEqual(r["verdict"], "미보도 후보")
        r = self.one(item, [art("기아, 하반기 생산직 신입 500명 채용", "2026-10-28")])
        self.assertEqual(r["verdict"], "관련 보도 있음")

    def test_bill_story_must_name_the_sponsor(self):
        # 운영 10-31: 박덕흠 전기사업법 개정안이 박성훈 개정안 기사로 '관련 보도 있음'
        item = {"tier": "B", "watch": "국회 법안", "id": "bills:발의|전기사업법|2026-10-27", "date": "2026-10-27", "company": "전력·에너지",
                "check": {"who": "전기사업법", "terms": ["개정안", "박덕흠"], "alts": {"개정안": ["개정안", "발의", "법안"]}, "must": ["박덕흠"]}}
        other = art("히트펌프 전용 전기요금 도입 길 열리나…박성훈 의원, 전기사업법 개정안 발의", "2026-10-27", "박성훈 의원이 전기사업법 일부개정법률안을 대표발의했다.")
        r = self.one(item, [other])
        self.assertEqual(r["verdict"], "미보도 후보")
        self.assertIn("박덕흠 없음", r["evidence"][0]["why"])
        mine = art("박덕흠 의원, 전기사업법 개정안 대표발의", "2026-10-28", "박덕흠 의원이 전기사업법 일부개정법률안을 대표발의했다.")
        self.assertEqual(self.one(item, [other, mine])["verdict"], "관련 보도 있음")

    def test_kepco_tender_story_is_matched_by_hanjeon_and_the_product(self):
        item = {"tier": "B", "watch": "공정위·한전·원자재", "id": "kepco:COM01:G012606058", "date": "2026-10-27", "company": "한국전력공사",
                "check": {"who": "한전", "terms": ["765kV", "변압기", "발주"], "alts": {"발주": ["발주", "입찰", "낙찰", "구매"]}, "places": ["765kV"]}}
        self.assertEqual(self.one(item, [art("한전, 원전 공급망 점검…경주 SMR 포럼", "2026-10-27")])["verdict"], "미보도 후보")
        self.assertEqual(self.one(item, [art("한국전력, 765㎸ 신안성 변압기 발주…효성·HD현대 경쟁", "2026-10-28")])["verdict"], "관련 보도 있음")

    def test_places_join_the_generic_words_per_item(self):
        rows = rpc.candidates([{"tier": "B", "watch": "해외 발주처 낙찰", "id": "bhopen:1:LS전선", "date": "2026-10-30", "company": "LS전선",
                                "check": {"who": "LS전선", "terms": ["바레인", "입찰"], "alts": {}, "places": ["바레인", "공장"]}}], now=NOW)
        self.assertEqual(rows[0]["generic"], ["미국", "공장", "계약", "바레인"])
        self.assertEqual(rpc.candidates(ITEMS[:1], now=NOW)[0]["generic"], rpc.GENERIC)

    def test_bills_match_the_law_name_in_the_text(self):
        item = ITEMS[2] | {"check": {"who": "노동조합 및 노동관계조정법", "terms": ["개정안", "이종배"], "alts": {"개정안": ["개정안", "발의"]}}}
        r = self.one(item, [art("노동조합 불법행위 규율 신설…국힘 이종배 의원, 관련법 개정안 발의", "2026-10-27",
                                "이종배 의원이 노동조합 및 노동관계조정법 일부개정법률안을 대표발의했다.")])
        self.assertEqual(r["verdict"], "관련 보도 있음")

    def test_bills_are_searched_and_matched_by_the_short_name(self):
        # 10-31 운영: '산업기술의 유출방지 및 보호에 관한 법률 개정안 백혜련'으로 찾아 미보도 후보 — 기사는 '산업기술보호법'
        formal = "산업기술의 유출방지 및 보호에 관한 법률"
        item = ITEMS[2] | {"id": "bills:발의|산업기술|2026-10-27", "date": "2026-10-27",
                           "check": {"who": "산업기술보호법", "terms": ["개정안", "백혜련"], "alts": {"개정안": ["개정안", "발의", "법안"]},
                                     "must": ["백혜련"], "names": ["산업기술보호법", formal]}}
        self.assertEqual(rpc.candidates([item], now=NOW)[0]["names"], ["산업기술보호법", formal])
        r = self.one(item, [art("기술유출 처벌 강화…백혜련, 산업기술보호법 개정안 대표발의", "2026-10-28")])
        self.assertEqual(r["verdict"], "관련 보도 있음")
        self.assertIn("산업기술보호법 개정안 백혜련", r["queries"])
        # 다른 법 기사(이름이 없음)는 근거가 아니다
        r = self.one(item, [art("백혜련, 국가첨단전략산업법 개정안 대표발의", "2026-10-28")])
        self.assertEqual(r["verdict"], "미보도 후보")

class Fetch(unittest.TestCase):
    def test_items_endpoint_uses_bearer_and_fails_loudly(self):
        seen = {}

        def ok(url, params=None, headers=None, timeout=None):
            seen.update(url=url, params=params, auth=headers["Authorization"])
            return R(200, {"generatedAt": "x", "hours": 72, "items": ITEMS})
        self.assertEqual(len(rpc.fetch_items("t" * 20, get=ok)), 5)
        self.assertEqual((seen["url"], seen["params"], seen["auth"]),
                         ("https://seoul-reporting-radar.shhong9173.workers.dev/ingest/radar-items", {"hours": 72}, "Bearer " + "t" * 20))
        with self.assertRaises(RuntimeError):
            rpc.fetch_items("t" * 20, get=lambda *a, **k: R(404))
        with self.assertRaises(RuntimeError):
            rpc.fetch_items("t" * 20, get=lambda *a, **k: R(200, {"items": None}))


if __name__ == "__main__":
    unittest.main()
