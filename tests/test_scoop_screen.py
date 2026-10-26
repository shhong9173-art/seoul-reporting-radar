"""Scoop screening: queries from real-looking clues, same-number vs related vs not-found, failures stay 미확인."""
import datetime as dt
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scoop_screen as s  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 7, 10, tzinfo=KST)

CLUES = {"items": [
    {"id": "a1", "team": "자동차", "published": None, "source": "DART_METRIC", "companies": ["현대차"], "routine": False,
     "tier": "취재 단서·단독 미확정", "url": "https://dart.fss.or.kr/x",
     "title": "현대자동차 · HMTR/튀르키예 — 공식 2025→2026 동일기간·단위 숫자 117600 → 95900 (대)"},
    {"id": "a2", "team": "자동차", "published": "2026-10-19", "source": "DART", "companies": ["현대위아"], "routine": False,
     "tier": "공개 원자료 추적", "url": "https://dart.fss.or.kr/y", "title": "현대위아 · 영업양도결정"},
    {"id": "a3", "team": "자동차", "published": "2026-08-01", "source": "DART", "companies": ["기아"], "routine": False,
     "tier": "공개 원자료 추적", "title": "기아 · 오래된 공시"},
    {"id": "a4", "team": "자동차", "published": "2026-10-25", "source": "DART", "companies": ["기아"], "routine": True,
     "tier": "공개 원자료 추적", "title": "기아 · 기업설명회(IR)개최"},
    {"id": "a5", "team": "철강·비철", "published": "2026-10-22", "source": "미 연방관보", "companies": ["포스코"], "routine": False,
     "tier": "공개 원자료 추적", "title": "Certain Hot-Rolled Steel Flat Products From Korea"},
]}
STATS = {"items": [
    {"id": "s1", "team": "전력·에너지", "company": "LS일렉트릭", "label": "LS일렉트릭 생산능력 (부산 / 초고압변압기, 배전변압기)",
     "period": "2025→2026 06월 누적", "current": "484052", "prior": "228651", "unit": "백만원", "changePercent": 111.7,
     "strength": 120, "source": "DART 분기·반기 사업의 내용", "sourceUrls": ["https://dart.fss.or.kr/z"]},
    {"id": "s2", "team": "전력·에너지", "company": "LS일렉트릭", "label": "약한 변화", "current": "10", "prior": "9", "strength": 10},
]}


class Numbers(unittest.TestCase):
    def test_forms_cover_comma_man_and_eok(self):
        self.assertTrue({"117,600", "11만7600"} <= s.num_forms("117600", "대"))
        self.assertTrue({"4,840억", "4840억"} <= s.num_forms("484052", "백만원"))
        self.assertIn("1조2345억", s.num_forms("1234500", "백만원"))
        self.assertIn("12조3450억", s.num_forms("12345000", "백만원"))
        self.assertEqual(s.num_forms("42", "대"), set())  # too common to be evidence
        self.assertIn("2.1배", s.ratio_forms("228651", "484052"))


class Selection(unittest.TestCase):
    def test_strong_and_fresh_clues_and_strong_stats_only(self):
        rows = s.select(CLUES, STATS, now=NOW)
        ids = [r["id"] for r in rows]
        self.assertIn("clue:a1", ids)
        self.assertIn("clue:a2", ids)
        self.assertNotIn("clue:a3", ids)  # stale and weak
        self.assertNotIn("clue:a4", ids)  # routine
        self.assertNotIn("clue:a5", ids)  # English prose only → no usable Korean query
        self.assertIn("stat:s1", ids)
        self.assertNotIn("stat:s2", ids)
        hmtr = next(r for r in rows if r["id"] == "clue:a1")
        self.assertEqual(s.queries(hmtr), ["현대차 튀르키예", "현대차 튀르키예 HMTR"])
        self.assertIn("95,900", hmtr["numbers"])
        wia = next(r for r in rows if r["id"] == "clue:a2")
        self.assertEqual(wia["terms"], ["영업양도"])  # 양도 keeps its last syllable

    def test_old_table_numbers_are_labelled_and_ranked_down(self):
        rows = s.select(CLUES, STATS, now=NOW)
        stat = next(r for r in rows if r["id"] == "stat:s1")
        self.assertIsNone(stat.get("staleDays"))  # fixture URL has no receipt number
        old = dict(STATS["items"][0], id="s3", sourceUrls=["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260814003088"])
        rows = s.select(CLUES, {"items": [old]}, now=NOW)
        stale = next(r for r in rows if r["id"] == "stat:s3")
        self.assertEqual(stale["filedOn"], "2026-08-14")
        self.assertEqual(stale["staleDays"], 74)
        self.assertEqual(stale["strength"], 1.5)

    def test_particles_and_stopwords(self):
        self.assertEqual(s.terms_from("두산에너빌리티 압력용기의 내외부를 이를", "두산에너빌리티"), ["압력용기", "내외부"])


def channels(naver_items=(), bing_items=(), google_status="ok", naver_status="ok"):
    return {"naver": {"status": naver_status, "items": list(naver_items)},
            "bing": {"status": "ok", "items": list(bing_items)}, "google": {"status": google_status, "items": []}}


class Judge(unittest.TestCase):
    def setUp(self):
        self.c = s.select(CLUES, STATS, now=NOW)[0] if False else next(
            r for r in s.select(CLUES, STATS, now=NOW) if r["id"] == "clue:a1")

    def test_same_number_beats_related(self):
        art = {"title": "현대차 튀르키예 공장 생산 9만5900대로 감소", "text": "", "url": "u1", "date": "2026-09-01"}
        verdict, ev = s.judge(self.c, channels([art]), now=NOW)
        self.assertEqual(verdict, "같은 수치 선행")
        self.assertIn("9만5900", ev[0]["why"])

    def test_related_needs_company_and_terms(self):
        rel = {"title": "현대차 HMTR 튀르키예 공장 감산", "text": "", "url": "u2", "date": "2026-09-01"}
        other = {"title": "기아 HMTR 튀르키예", "text": "", "url": "u3", "date": "2026-09-01"}
        old = {"title": "현대차 HMTR 튀르키예 9만5900대", "text": "", "url": "u4", "date": "2025-01-01"}
        verdict, ev = s.judge(self.c, channels([rel, other, old]), now=NOW)
        self.assertEqual(verdict, "관련 보도 있음")
        self.assertEqual([e["url"] for e in ev], ["u2"])

    def test_lead_term_in_a_headline_with_the_company_counts_as_related(self):
        art = {"title": "현대차, 튀르키예산 아이오닉3 9월 판매 6486대", "text": "", "url": "u5", "date": "2026-10-25"}
        body_only = {"title": "현대차 유럽 전략", "text": "튀르키예 공장도 언급", "url": "u6", "date": "2026-10-25"}
        verdict, ev = s.judge(self.c, channels([art, body_only]), now=NOW)
        self.assertEqual(verdict, "관련 보도 있음")
        self.assertEqual([e["url"] for e in ev], ["u5"])

    def test_generic_first_word_alone_is_not_related(self):
        c = {"company": "HD현대일렉트릭", "terms": ["변압기", "철심공장"], "numbers": [], "ratios": []}
        self.assertEqual(s.lead(c["terms"]), "철심공장")
        generic = {"title": "HD현대일렉트릭, 美 변압기 수주", "text": "", "url": "g1", "date": "2026-10-01"}
        specific = {"title": "HD현대일렉트릭 철심공장 준공 연기", "text": "", "url": "g2", "date": "2026-10-01"}
        self.assertEqual(s.judge(c, channels([generic]), now=NOW)[0], "미보도 후보")
        self.assertEqual(s.judge(c, channels([specific]), now=NOW)[0], "관련 보도 있음")

    def test_not_found_only_when_naver_and_a_web_index_answered(self):
        self.assertEqual(s.judge(self.c, channels(), now=NOW)[0], "미보도 후보")
        self.assertEqual(s.judge(self.c, channels(naver_status="failed"), now=NOW)[0], "미확인")
        self.assertEqual(s.judge(self.c, channels(naver_status="not_configured"), now=NOW)[0], "미확인")
        both_web_down = channels()
        both_web_down["bing"]["status"] = "failed"
        both_web_down["google"]["status"] = "failed"
        self.assertEqual(s.judge(self.c, both_web_down, now=NOW)[0], "미확인")


class R:
    def __init__(self, code=200, body=None, content=b""):
        self.status_code, self.body, self.content = code, body or {}, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def json(self):
        return self.body


class Screen(unittest.TestCase):
    def test_end_to_end_with_fake_channels_and_counts_only_log(self):
        rss_empty = b"<rss><channel></channel></rss>"
        def get(url, params=None, headers=None, timeout=None):
            if "naverapihub" in url:
                q = params["query"]
                items = [{"title": "<b>현대위아</b> 영업양도 결정", "description": "", "originallink": "https://n/1",
                          "pubDate": "Mon, 20 Oct 2026 09:00:00 +0900"}] if "현대위아" in q else []
                return R(200, {"items": items})
            return R(200, content=rss_empty)
        cands = s.select(CLUES, STATS, now=NOW)
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "i", "NAVER_CLIENT_SECRET": "k"}):
            rows = s.screen(cands, now=NOW, get=get, sleep=lambda x: None)
        by = {r["id"]: r for r in rows}
        self.assertEqual(by["clue:a2"]["verdict"], "관련 보도 있음")
        self.assertEqual(by["clue:a1"]["verdict"], "미보도 후보")
        self.assertEqual(by["clue:a1"]["channels"]["naver"]["via"], "API HUB")
        self.assertEqual(rows[0]["verdict"], "미보도 후보")  # unreported first
        doc = s.report(rows, now=NOW, inputs={})
        self.assertEqual(doc["schema"], "scoop_screen/v1")
        self.assertEqual(doc["confirmedScoops"], 0)
        self.assertEqual(sum(doc["counts"].values()), len(rows))

    def test_without_naver_everything_is_unconfirmed(self):
        def get(url, params=None, headers=None, timeout=None):
            return R(200, content=b"<rss><channel></channel></rss>")
        with patch.dict(os.environ, {"NAVER_CLIENT_ID": "", "NAVER_CLIENT_SECRET": ""}):
            rows = s.screen(s.select(CLUES, STATS, now=NOW), now=NOW, get=get, sleep=lambda x: None)
        self.assertTrue(all(r["verdict"] == "미확인" for r in rows))

    def test_push_sends_bearer_token_to_private_ingest(self):
        seen = {}
        def post(url, data, headers, timeout):
            seen.update(url=url, auth=headers["Authorization"], body=data)
            return R(200)
        self.assertEqual(s.push({"schema": "scoop_screen/v1"}, "tok", post=post), 200)
        self.assertTrue(seen["url"].endswith("/ingest/scoop-screen"))
        self.assertEqual(seen["auth"], "Bearer tok")


if __name__ == "__main__":
    unittest.main()
