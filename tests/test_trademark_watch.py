"""Trademark watch: grouping, new/baseline, tiers, provider 22, budget, never storing the key."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import trademark_watch as tw
from kipris_account_ledger import KiprisAccountLedger

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 2, 7, 10, tzinfo=KST)
CFG = {
    "windowDays": 90, "rowsPerPage": 500, "maxPagesPerApplicant": 2, "runCallCap": 34,
    "keepFilingDays": 120, "keepSeenDays": 400,
    "industries": {"auto": {"label": "완성차", "core": ["12", "09"]},
                   "electric": {"label": "전력", "core": ["09"]}},
    "applicants": [
        {"company": "현대자동차", "industry": "auto", "names": ["현대자동차주식회사", "현대자동차 주식회사"]},
        {"company": "효성중공업", "industry": "electric", "names": ["효성중공업주식회사"], "related": True},
    ],
}


def item(number, title, date, cls, owner="현대자동차주식회사", status="출원"):
    return (f"<item><agentName>대리인</agentName><applicantName>{owner}</applicantName>"
            f"<applicationDate>{date}</applicationDate><applicationNumber>{number}</applicationNumber>"
            f"<applicationStatus>{status}</applicationStatus>"
            f"<bigDrawing>http://plus.kipris.or.kr/kiprisplusws/fileToss.jsp?arg=deadbeef</bigDrawing>"
            f"<classificationCode>{cls}</classificationCode><title>{title}</title></item>")


def reply(items, total=None, code="00"):
    total = len(items) if total is None else total
    return (f"<response><header><resultCode>{code}</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>"
            f"<body><items>{''.join(items)}</items><count><numOfRows>500</numOfRows><pageNo>1</pageNo>"
            f"<totalCount>{total}</totalCount></count></body></response>").encode()


LIMITED = (b"<response><header><resultCode>22</resultCode><resultMsg>LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS ERROR."
           b"</resultMsg></header></response>")


class Fake:
    def __init__(self, by_owner):
        self.by_owner, self.urls = by_owner, []

    def __call__(self, url):
        self.urls.append(url)
        q = parse_qs(urlsplit(url).query)
        page = int(q["pageNo"][0])
        answer = self.by_owner.get(q["applicantName"][0], reply([]))
        return answer[page - 1] if isinstance(answer, list) else answer


def ledger(folder, now=NOW, **kw):
    return KiprisAccountLedger(Path(folder) / "ledger.json", now=now, legacy_path=None,
                               sleep=lambda _s: None, **kw)


BASE_ROWS = [item("4020260100001", "NUTRIMACY", "20260910", "12"),
             item("4020260100002", "NUTRIMACY", "20260910", "09"),
             item("4020260100003", "PLEOS", "20260801", "09")]


class Watch(unittest.TestCase):
    def first_run(self, folder):
        fake = Fake({"현대자동차주식회사": reply(BASE_ROWS)})
        book = ledger(folder)
        doc = tw.run(CFG, now=NOW, key="SECRET-KEY", ledger=book, fetch=book.fetcher("trademark", fake))
        return doc, fake, book

    def test_baseline_groups_classes_and_marks_nothing_new(self):
        with tempfile.TemporaryDirectory() as folder:
            doc, fake, _ = self.first_run(folder)
            self.assertTrue(doc["baselineSince"])
            hy = [f for f in doc["filings"] if f["company"] == "현대자동차"]
            self.assertEqual(len(hy), 2)
            nutri = next(f for f in hy if f["title"] == "NUTRIMACY")
            self.assertEqual(nutri["classes"], ["09", "12"])
            self.assertEqual(len(nutri["applicationNumbers"]), 2)
            self.assertFalse(any(f["isNew"] for f in doc["filings"]))
            self.assertEqual(doc["fresh"], [])
            self.assertEqual(len(fake.urls), 2)  # one call per applicant

    def test_request_has_required_flags_window_and_document_never_keeps_key_or_image(self):
        with tempfile.TemporaryDirectory() as folder:
            doc, fake, _ = self.first_run(folder)
            q = parse_qs(urlsplit(fake.urls[0]).query)
            self.assertEqual(q["applicationDate"], ["20260804~20261102"])
            for flag in ("application", "trademark", "character", "visual", "geoCertMark", "abandonment"):
                self.assertEqual(q[flag], ["true"])
            self.assertTrue(fake.urls[0].endswith("ServiceKey=SECRET-KEY"))
            text = json.dumps(doc, ensure_ascii=False)
            self.assertNotIn("SECRET-KEY", text)
            self.assertNotIn("fileToss", text)

    def test_second_run_new_name_is_B_added_class_and_related_are_C(self):
        with tempfile.TemporaryDirectory() as folder:
            first, _, _ = self.first_run(folder)
            later = NOW + timedelta(days=7)
            rows = BASE_ROWS + [item("4020260100004", "NUTRIMACY", "20260910", "07"),       # more classes, known name
                                item("4020260100005", "AERO DRIVE", "20261020", "12"),      # new name, core class
                                item("4020260100006", "STORE CAFE", "20261021", "43")]      # new name, not core
            fake = Fake({"현대자동차주식회사": reply(rows),
                         "효성중공업주식회사": reply([item("4020260200001", "GRIDMAX", "20261015", "09", owner="효성중공업주식회사")])})
            book = ledger(folder, now=later)
            doc = tw.run(CFG, now=later, previous=first, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            by_title = {f["title"]: f for f in doc["filings"]}
            self.assertEqual(by_title["AERO DRIVE"]["tier"], "B")
            self.assertTrue(by_title["AERO DRIVE"]["titleNew"])
            self.assertEqual(by_title["STORE CAFE"]["tier"], "C")
            self.assertEqual(by_title["NUTRIMACY"]["tier"], "C")
            self.assertEqual(by_title["NUTRIMACY"]["newNumbers"], ["4020260100004"])
            self.assertEqual(by_title["NUTRIMACY"]["firstSeen"], first["generatedAt"])
            self.assertEqual(by_title["GRIDMAX"]["tier"], "C")  # related company never above C
            self.assertFalse(by_title["PLEOS"]["isNew"])
            self.assertEqual(set(doc["fresh"]), {by_title[t]["id"] for t in ("AERO DRIVE", "STORE CAFE", "NUTRIMACY", "GRIDMAX")})

    def test_other_applicants_dropped_and_all_mismatch_is_a_failure_not_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [item("4020260100009", "X", "20261001", "12", owner="현대자동차그룹재단"),
                    item("4020260100010", "Y", "20261001", "12", owner="현대자동차주식회사|기아주식회사")]
            fake = Fake({"현대자동차주식회사": reply(rows), "효성중공업주식회사": reply([item("4020260100011", "Z", "20261001", "09", owner="딴회사")])})
            book = ledger(folder)
            doc = tw.run(CFG, now=NOW, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            hy = next(c for c in doc["checks"] if c["source"] == "상표 현대자동차")
            self.assertEqual((hy["status"], hy["kept"], hy["otherApplicants"]), ("ok", 1, 1))
            hs = next(c for c in doc["checks"] if c["source"] == "상표 효성중공업")
            self.assertEqual(hs["status"], "failed")

    def test_customer_number_and_short_form_still_match(self):
        self.assertTrue(tw.owner_matches("현대자동차주식회사(119980045698)", tw.name_variants(["현대자동차주식회사"])))
        self.assertTrue(tw.owner_matches("(주)에이치엘만도", tw.name_variants(["주식회사에이치엘만도"])))
        self.assertFalse(tw.owner_matches("현대자동차투자증권주식회사", tw.name_variants(["현대자동차주식회사"])))

    def test_code_22_one_call_then_waiting_and_previous_data_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            first, _, _ = self.first_run(folder)
            later = NOW + timedelta(days=7)
            fake = Fake({"현대자동차주식회사": LIMITED, "효성중공업주식회사": reply([])})
            book = ledger(folder, now=later)
            doc = tw.run(CFG, now=later, previous=first, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            self.assertEqual(len(fake.urls), 1)
            st = [c["status"] for c in doc["checks"]]
            self.assertEqual(st, ["failed", "waiting"])
            self.assertIn("22", doc["checks"][0]["error"])
            self.assertEqual(len(doc["filings"]), len(first["filings"]))
            self.assertEqual(doc["seen"], first["seen"])
            self.assertIn("trademark", book.public()["providerCooldown"])
            self.assertNotIn("patent", book.public()["providerCooldown"])

    def test_monthly_trademark_limit_means_waiting_without_calls(self):
        with tempfile.TemporaryDirectory() as folder:
            book = ledger(folder, monthly_limit=10, group_limits={"patent": 8, "trademark": 1, "diagnostic": 1})
            fake = Fake({"현대자동차주식회사": reply(BASE_ROWS)})
            doc = tw.run(CFG, now=NOW, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            self.assertEqual(len(fake.urls), 1)
            self.assertEqual(doc["checks"][1]["status"], "waiting")
            self.assertEqual(doc["checks"][1]["reason"], "monthly_trademark_limit")

    def test_paging_and_inconsistent_totals(self):
        with tempfile.TemporaryDirectory() as folder:
            page1 = reply([item(f"40202601{i:05d}", f"N{i}", "20261001", "12") for i in range(3)], total=5)
            page2 = reply([item(f"40202602{i:05d}", f"M{i}", "20261001", "12") for i in range(2)], total=5)
            fake = Fake({"현대자동차주식회사": [page1, page2]})
            book = ledger(folder)
            doc = tw.run(CFG, now=NOW, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            hy = doc["checks"][0]
            self.assertEqual((hy["status"], hy["requests"], hy["kept"]), ("ok", 2, 5))
            bad = Fake({"현대자동차주식회사": [page1, reply([item("4020260300001", "Q", "20261001", "12")], total=9)]})
            book2 = ledger(folder)
            doc2 = tw.run(CFG, now=NOW, key="k", ledger=book2, fetch=book2.fetcher("trademark", bad))
            self.assertEqual(doc2["checks"][0]["status"], "failed")

    def test_no_key_is_unset_and_no_baseline(self):
        doc = tw.run(CFG, now=NOW, key="", ledger=None, fetch=None)
        self.assertEqual({c["status"] for c in doc["checks"]}, {"unset"})
        self.assertEqual(doc["status"], "unset")
        self.assertIsNone(doc["baselineSince"])
        again = tw.run(CFG, now=NOW + timedelta(days=7), previous=doc, key="", ledger=None, fetch=None)
        self.assertIsNone(again["baselineSince"])

    def test_document_without_baseline_is_still_treated_as_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = tw.run(CFG, now=NOW, key="", ledger=None, fetch=None)
            fake = Fake({"현대자동차주식회사": reply(BASE_ROWS)})
            book = ledger(folder)
            doc = tw.run(CFG, now=NOW, previous=empty, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            self.assertFalse(any(f["isNew"] for f in doc["filings"]))

    def test_company_with_changed_or_unverified_name_is_its_own_baseline(self):
        # 11-02: '주식회사엘지화학'으로 0건(이름 미확인) → 실제 응답 이름 '주식회사 엘지화학'을 먼저 보내도록 바꾼 첫 실행
        cfg = json.loads(json.dumps(CFG))
        cfg["applicants"].append({"company": "LG화학", "industry": "electric", "names": ["주식회사 엘지화학", "주식회사엘지화학"]})
        with tempfile.TemporaryDirectory() as folder:
            first, _, _ = self.first_run(folder)
            first["checks"].append({"source": "상표 LG화학", "status": "ok", "rawTotal": 0, "nameVerified": False})
            later = NOW + timedelta(days=7)
            lg = [item("4020260300001", "LUCETTE", "20261001", "09", owner="주식회사 엘지화학")]
            fake = Fake({"현대자동차주식회사": reply(BASE_ROWS), "주식회사 엘지화학": reply(lg)})
            book = ledger(folder, now=later)
            doc = tw.run(cfg, now=later, previous=first, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            lucette = next(f for f in doc["filings"] if f["title"] == "LUCETTE")
            self.assertFalse(lucette["isNew"])  # 그 회사 첫 읽기 — 기준선
            chk = next(c for c in doc["checks"] if c["source"] == "상표 LG화학")
            self.assertEqual((chk["query"], chk.get("baseline")), ("주식회사 엘지화학", True))
            # 다음 실행(같은 이름)부터는 새 출원이 신규
            again = later + timedelta(days=7)
            lg2 = lg + [item("4020260300002", "NEOCHEM", "20261101", "09", owner="주식회사 엘지화학")]
            fake = Fake({"현대자동차주식회사": reply(BASE_ROWS), "주식회사 엘지화학": reply(lg2)})
            book = ledger(folder, now=again)
            doc2 = tw.run(cfg, now=again, previous=doc, key="k", ledger=book, fetch=book.fetcher("trademark", fake))
            self.assertTrue(next(f for f in doc2["filings"] if f["title"] == "NEOCHEM")["isNew"])
            self.assertNotIn("baseline", next(c for c in doc2["checks"] if c["source"] == "상표 LG화학"))

    def test_config_fits_trademark_budget(self):
        cfg = json.loads(tw.CONFIG.read_text(encoding="utf-8"))
        from kipris_account_ledger import GROUP_LIMITS
        self.assertLessEqual(len(cfg["applicants"]), cfg["runCallCap"])
        self.assertLessEqual(len(cfg["applicants"]) * 5, GROUP_LIMITS["trademark"])  # five Mondays in a month
        for a in cfg["applicants"]:
            self.assertIn(a["industry"], cfg["industries"])
        direct = {a["company"] for a in cfg["applicants"] if not a.get("related")}
        self.assertNotIn("효성중공업", direct)
        self.assertNotIn("일진전기", direct)


if __name__ == "__main__":
    unittest.main()
