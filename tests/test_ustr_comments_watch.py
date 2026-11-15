import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ustr_comments_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 15, 23, 20, tzinfo=KST)
REBAR = ("II. Korean Trade Barriers The Korean government provides substantial subsidies to its steel producers, including rebar producers. "
         "U.S. imports of Korean rebar rose from 906 metric tons in 2023 to roughly 18,000 metric tons in 2025. In the first eight months of 2026, Korean rebar exports "
         "reached approximately 560,100 metric tons. Major rebar producers, including Hyundai Steel, operate as part of sprawling industrial conglomerates. "
         "More significant steps, including slashing Korean shipment volumes through the further use of Section 232 or Section 301, are necessary.")
FORD = ("III. East Asia South Korea U.S. automakers exporting into South Korea face a myriad of changing barriers that make it almost impossible to export to South Korea. "
        "The 2025 U.S.–Korea trade deal includes commitments for Korea to remove the 50,000-vehicle annual cap on U.S.-origin vehicles. "
        "However, implementation has been impossible due to the remaining barriers listed below, and the market is inaccessible to Ford exports. " + "p" * 300)
WINE = "Korea maintains a 15 percent tariff on imported wine and a liquor tax that burdens U.S. distillers. " + "z" * 600
NK = "Sanctions on North Korea remain in place. " + "q" * 900


class R:
    def __init__(self, body=None, status=200, content=b""):
        self._body, self.status_code, self.content = body, status, content

    def json(self):
        return self._body


class Ustr(unittest.TestCase):
    def test_passages_need_korea_next_to_a_beat_sector_or_company(self):
        r = w.analyze(REBAR)
        self.assertEqual((r["hits"][0]["sectors"], r["hits"][0]["companies"]), (["철강·비철"], ["현대제철"]))
        self.assertIn("560,100 metric tons", r["hits"][0]["excerpt"])
        self.assertEqual([h["sectors"] for h in w.analyze(FORD)["hits"]], [["자동차"]])
        self.assertEqual((w.analyze(WINE)["korea"], w.analyze(WINE)["hits"]), (1, []))      # 한국은 나오지만 출입 업종이 아니다
        self.assertEqual(w.analyze(NK)["korea"], 0)                                          # North Korea는 세지 않는다
        self.assertEqual(w.companies_in("Korean steel producer POSCO received loans. POSCO International and LG Energy Solution are separate."), ["포스코"])   # 계열사는 출입처가 아니다
        self.assertEqual(w.companies_in("Hanwha Qcells and Hyundai Motor Group filed comments"), ["현대차", "한화솔루션"])

    def collect(self, texts, previous=None, now=NOW, read_budget=50, fail=()):
        """texts: {commentId: (게시일, 제출자, 본문)}"""
        calls = []
        orig = w.pdf_text
        w.pdf_text = lambda data: (data.decode("utf-8"), 3)

        def get(url, params=None, headers=None, timeout=None):
            calls.append(url)
            if url.endswith("/comments"):
                return R({"data": [{"id": cid, "attributes": {"postedDate": f"{posted}T04:00:00Z", "title": f"Comment from {who}"}} for cid, (posted, who, _) in texts.items()], "meta": {"hasNextPage": False}})
            if "/comments/" in url:
                cid = url.rsplit("/", 1)[1]
                if cid in fail:
                    return R(status=500)
                return R({"data": {"attributes": {"comment": "See attached file(s)"}}, "included": [{"attributes": {"fileFormats": [{"format": "pdf", "fileUrl": f"https://downloads.regulations.gov/{cid}/attachment_1.pdf"}]}}]})
            if "downloads.regulations.gov" in url:
                return R(content=texts[url.split("/")[3]][2].encode("utf-8"))
            if "/dockets/" in url:
                return R({"data": {"attributes": {"title": "Request for Comments on Significant Foreign Trade Barriers for the 2027 National Trade Estimate Report"}}})
            if "federalregister.gov" in url:
                return R({"results": [{"title": "Request for Public Comments Relating to the Operation of the USMCA", "publication_date": "2026-10-05", "document_number": "2026-20341",
                                       "docket_ids": ["Docket Nos. USTR-2026-0595"], "comments_close_on": None, "html_url": "https://www.federalregister.gov/d/2026-20341", "abstract": "automotive rules of origin"}]})
            raise AssertionError(url)

        try:
            return w.collect("k", now=now, previous=previous, get=get, sleep=lambda s: None, budget=w.uc.Budget(999), read_budget=read_budget), calls
        finally:
            w.pdf_text = orig

    def test_reads_each_comment_once_and_marks_old_ones_as_baseline(self):
        texts = {"USTR-2026-0498-0147": ("2026-10-30", "Rebar Trade Action Coalition", REBAR), "USTR-2026-0498-0079": ("2026-10-30", "Distilled Spirits Council", WINE),
                 "USTR-2026-0661-0012": ("2026-11-14", "Ford Motor Company", FORD)}
        doc, calls = self.collect(texts)
        ids = {x["commentId"]: x for x in doc["items"]}
        self.assertEqual(sorted(ids), ["USTR-2026-0498-0147", "USTR-2026-0661-0012"])           # 업종 대목 없는 주류 단체는 항목이 아니다
        rebar = ids["USTR-2026-0498-0147"]
        self.assertEqual((rebar["id"], rebar["tier"], rebar["submitter"], rebar["companies"], rebar["sectors"], rebar["baseline"], rebar["docketId"]),
                         ("ustr:USTR-2026-0498-0147", "B", "Rebar Trade Action Coalition", ["현대제철"], ["철강·비철"], True, "USTR-2026-0498"))   # 감시 시작 16일 전 게시 — 기준선
        self.assertEqual((ids["USTR-2026-0661-0012"]["baseline"], ids["USTR-2026-0661-0012"]["companies"]), (False, []))
        self.assertEqual(rebar["docketTitle"][:40], "Request for Comments on Significant Fore")
        self.assertEqual((doc["summary"]["readNow"], doc["summary"]["korea"], doc["summary"]["items"], doc["summary"]["fresh"], doc["status"]), (3, 3, 2, 1, "ok"))
        self.assertEqual((doc["notices"][0]["number"], doc["notices"][0]["sectors"]), ("2026-20341", ["자동차"]))
        again, calls = self.collect(texts, previous=doc, now=NOW + dt.timedelta(hours=8))
        self.assertEqual([c for c in calls if "/comments/" in c or "downloads" in c], [])       # 한 번 읽은 의견서는 다시 받지 않는다
        self.assertEqual((len(again["items"]), again["summary"]["fresh"], again["startedAt"]), (2, 0, doc["startedAt"]))
        # 다음 날 새로 게시된 의견서만 읽고, 기준선이 아니다
        texts["USTR-2026-0595-0003"] = ("2026-11-16", "American Iron and Steel Institute", REBAR.replace("rebar", "steel"))
        nxt, calls = self.collect(texts, previous=again, now=NOW + dt.timedelta(days=1))
        self.assertEqual(len([c for c in calls if "/comments/" in c]), 1)
        self.assertEqual([(x["commentId"], x["baseline"]) for x in nxt["items"]][0], ("USTR-2026-0595-0003", False))

    def test_budget_and_failures_are_waiting_not_zero(self):
        texts = {f"USTR-2026-0498-{i:04d}": ("2026-10-30", f"Group {i}", REBAR) for i in range(5)}
        doc, _ = self.collect(texts, read_budget=2, fail={"USTR-2026-0498-0000"})
        self.assertEqual((doc["summary"]["readNow"], doc["summary"]["waiting"], doc["summary"]["failed"], doc["status"]), (2, 3, 1, "partial"))
        self.assertIn({"source": "본문 읽기 한도", "status": "waiting", "error": "3건 다음 실행에서 읽음"}, doc["checks"])
        # 다음 실행: 첫 읽기가 여러 실행에 걸쳐도 기준선 기준(감시 시작일)은 같다
        nxt, _ = self.collect(texts, previous=doc, now=NOW + dt.timedelta(days=5), read_budget=10)
        self.assertEqual((nxt["summary"]["waiting"], len(nxt["items"]), all(x["baseline"] for x in nxt["items"])), (0, 5, True))


if __name__ == "__main__":
    unittest.main()
