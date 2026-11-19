"""EU 관보 무역구제 감시 — 탐침 19·20(11-19)의 실제 제목·CELEX·본문 모양으로."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import eu_trade_defence_watch as w  # noqa: E402

KST = w.KST
NOW = dt.datetime(2026, 11, 19, 17, 50, tzinfo=KST)
T2547 = ("Commission Implementing Regulation (EU) 2026/2547 of 13 November 2026 imposing a definitive anti-dumping duty on imports of certain cold-rolled "
         "flat steel products originating in India, Japan, Taiwan, Türkiye and Vietnam")
T2345 = ("Commission Implementing Regulation (EU) 2026/2345 of 23 October 2026 making imports of certain Polyvinyl chloride (PVC) originating in the "
         "People’s Republic of China, Republic of Korea, Mexico and Taiwan subject to registration")
T2391 = ("Commission Implementing Regulation (EU) 2026/2391 of 29 October 2026 making imports of certain cellulose ethers originating in the People’s "
         "Republic of China and the Republic of Korea subject to registration")
T2311 = ("Commission Implementing Regulation (EU) 2026/2311 of 19 October 2026 imposing a definitive anti-dumping duty on imports of certain heavyweight "
         "thermal paper originating in the Republic of Korea following an expiry review")
TFIB = "Notice of initiation of an expiry review of the anti-dumping measures applicable to imports of optical fibre cables originating in the People’s Republic of China"
TCOURT = "Judgment of the Court (Fifth Chamber) of 12 November 2026.#A.A. v Wojewoda Śląski."
# 탐침 20에서 읽은 2026/2547 본문 대목(전문의 POSCO 문장, 결정부 제1조 표 줄)은 실제 글, 나머지는 줄임
BODY2547 = ("<p>(11) POSCO VIETNAM Co., Ltd, Ho Chi Minh City (‘POSVIET’) and Tatmetal Çelik Sanayi ve Ticaret A. Ş., Istanbul (‘Tatmetal’) alleged that the "
            "evidence of PMS included in the complaint with respect to Vietnam was insufficient. (12) Article 1(4) of the basic Regulation applies.</p>"
            "<p>HAS ADOPTED THIS REGULATION:</p><p>Article 1</p><p>1. A definitive anti-dumping duty is imposed on imports of certain cold-rolled flat steel products.</p>"
            "<table><tr><td>All other imports originating in Taiwan</td><td>27,0</td><td>8999</td></tr>"
            "<tr><td>Türkiye</td><td>Tatmetal Çelik Sanayi ve Ticaret A. Ş.</td><td>3,0</td><td>88GJ</td></tr>"
            "<tr><td>Vietnam</td><td>POSCO VIETNAM CO., LTD</td><td>16,0</td><td>88GO</td></tr>"
            "<tr><td>Other cooperating companies listed in the Annex</td><td>16,0</td><td>See Annex</td></tr></table>"
            "<p>Article 2</p><p>This Regulation shall enter into force on the day following that of its publication.</p>")
BODY2345 = ("<p>HAS ADOPTED THIS REGULATION:</p><p>Article 1</p><p>1. The customs authorities are hereby directed, under Article 14(5) of Regulation (EU) 2016/1036, "
            "to take the appropriate steps to register imports into the Union of certain polyvinyl chloride originating in the Republic of Korea.</p><p>Article 2</p>")


class R:
    def __init__(self, status=200, data=None, text=""):
        self.status_code, self._d, self.text = status, data, text

    def json(self):
        return self._d


def rows(*items):
    return {"results": {"bindings": [{"celex": {"value": c}, "date": {"value": d}, "title": {"value": t}} for c, d, t in items]}}


BASE = [("32026R2345", "2026-10-23", T2345), ("32026R2391", "2026-10-29", T2391), ("62025CJ0254", "2026-11-12", TCOURT),
        ("52026XC06025", "2026-11-17", TFIB), ("02023R0265-20261021", "2026-10-21", "Commission Implementing Regulation (EU) 2023/265 (consolidated)")]


def fake(listed, bodies=None, fail=()):
    calls = []
    bodies = {"32026R2547": BODY2547, "32026R2345": BODY2345, **(bodies or {})}

    def get(url, params=None, headers=None, timeout=None):
        calls.append(url if not params else "SPARQL")
        if url == w.SPARQL:
            return R(503) if "sparql" in fail else R(200, rows(*listed))
        celex = url.rsplit("/", 1)[-1]
        if celex in fail:
            return R(500)
        return R(200, text=bodies.get(celex, "<p>HAS ADOPTED THIS REGULATION: Article 1 nothing Article 2</p>"))
    return get, calls


class Eu(unittest.TestCase):
    def test_first_run_baseline_then_posco_vietnam_regulation_is_event(self):
        get, calls = fake(BASE)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual(doc["events"], [])
        ids = {r["id"]: r for r in doc["records"]}
        self.assertEqual(list(ids), ["euoj:32026R2345"])                     # 한국 PVC 수입 등록만(셀룰로스 에테르는 업종 밖)
        self.assertEqual((ids["euoj:32026R2345"]["kind"], ids["euoj:32026R2345"]["tier"], ids["euoj:32026R2345"]["baseline"]), ("수입 등록", "B", True))
        self.assertNotIn(w.CELLAR + "62025CJ0254", calls)                    # 법원 판결·통합본은 목록에서 뺀다
        self.assertNotIn(w.CELLAR + "32026R2391", calls)                     # 업종 밖 품목은 본문을 안 받는다
        self.assertNotIn(w.CELLAR + "52026XC06025", calls)                   # 중국산 재심 개시(제목에 한국 없음)
        # 다음 실행: 제목에 한국이 없는 냉연 확정 규정 — 본문에 포스코 베트남이 수출자
        get2, calls2 = fake(BASE + [("32026R2547", "2026-11-13", T2547)])
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual(calls2, ["SPARQL", w.CELLAR + "32026R2547"])        # 본 문서는 다시 안 받는다
        self.assertEqual(len(doc2["events"]), 1)
        e = doc2["events"][0]
        self.assertEqual((e["id"], e["tier"], e["kind"], e["companies"], e["number"], e["date"], e["korea"]),
                         ("euoj:32026R2547", "A", "EU 관보 무역구제(확정 관세)", ["포스코"], "2026/2547", "2026-11-13", False))
        self.assertEqual(e["product"], "cold-rolled flat steel products")
        self.assertIn("EU 관보 무역구제 — 확정 관세: 2026/2547 「Commission Implementing Regulation (EU) 2026/2547", e["text"])
        self.assertIn("· 본문에 출입처 포스코 · 제1조 세율 POSCO VIETNAM CO., LTD 16.0%(88GO) · 본문 대목 「(11) POSCO VIETNAM Co., Ltd, Ho Chi Minh City", e["text"])
        self.assertIn("출입처 해외 법인이 수출자로 나온 것은 그 나라산 조치", e["text"])
        self.assertEqual(e["url"], "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R2547")
        get3, calls3 = fake(BASE + [("32026R2547", "2026-11-13", T2547)])
        self.assertEqual(len(w.run(NOW + dt.timedelta(hours=6), doc2, get=get3, sleep=lambda s: None)["events"]), 1)
        self.assertEqual(calls3, ["SPARQL"])

    def test_beat_product_regulation_without_beat_names_is_dropped(self):
        get, _ = fake(BASE)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        t = T2547.replace("2026/2547", "2026/2600").replace("cold-rolled flat steel", "certain hot-rolled flat steel")
        get2, calls2 = fake(BASE + [("32026R2600", "2026-11-18", t)], bodies={"32026R2600": "<p>HAS ADOPTED THIS REGULATION: Article 1 Tata Steel 10,0 C123 Article 2</p>"})
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertIn(w.CELLAR + "32026R2600", calls2)
        self.assertEqual(doc2["events"], [])                                 # 제목에 한국 없고 본문에 출입처 이름 없음
        self.assertEqual(doc2["skipped"], 1 + 0)

    def test_korea_title_beat_product_definitive_is_a_even_without_names(self):
        get, _ = fake(BASE)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        t = "Commission Implementing Regulation (EU) 2026/2700 of 18 November 2026 imposing a provisional anti-dumping duty on imports of certain polyvinyl chloride originating in the Republic of Korea"
        get2, _ = fake(BASE + [("32026R2700", "2026-11-18", t)])
        e = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)["events"][0]
        self.assertEqual((e["tier"], e["kind"], e["korea"], e["companies"]), ("A", "EU 관보 무역구제(잠정 관세)", True, []))
        self.assertIn("본문에 출입처 이름 없음(한국산 품목)", e["text"])

    def test_body_budget_and_failures_carry_over(self):
        get, _ = fake(BASE)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, _ = fake(BASE + [("32026R2547", "2026-11-13", T2547)], fail=("32026R2547",))
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], doc2["events"]), ("partial", []))
        self.assertNotIn("32026R2547", doc2["seen"])                          # 못 읽은 본문은 다음 실행에 다시
        get3, _ = fake(BASE + [("32026R2547", "2026-11-13", T2547)])
        self.assertEqual([e["id"] for e in w.run(NOW + dt.timedelta(hours=6), doc2, get=get3, sleep=lambda s: None)["events"]], ["euoj:32026R2547"])

    def test_list_failure_keeps_previous(self):
        get, _ = fake(BASE)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, _ = fake(BASE, fail=("sparql",))
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual((doc2["status"], len(doc2["records"]), doc2["stale"]), ("failed", 1, True))
        self.assertEqual(w.run(NOW, None, get=get2, sleep=lambda s: None)["records"], [])

    def test_kinds_from_real_titles(self):
        k = lambda t: w.kind_of(t)[0]
        self.assertEqual(k(T2311), "확정 관세 연장(종료재심 결과)")
        self.assertEqual(k("Commission Implementing Regulation (EU) 2026/2393 of 29 October 2026 imposing a definitive anti-dumping duty and definitively collecting the provisional duty imposed on imports of PET Spunbond"), "확정 관세")
        self.assertEqual(k("Commission Implementing Regulation (EU) 2026/2538 of 17 November 2026 correcting Implementing Regulation (EU) 2025/1919 imposing a definitive anti-dumping duty"), "변경·정정")
        self.assertEqual(k("Commission Implementing Regulation (EU) 2026/2310 of 19 October 2026 repealing definitive countervailing duties on imports of solar glass originating in the People’s Republic of China following an expiry review"), "조사 종료·조치 폐지")
        self.assertEqual(k(TFIB), "재심·우회 조사 개시")
        self.assertEqual(k("Notice of initiation of an anti-dumping proceeding concerning imports of polyamide-6 originating in the People’s Republic of China"), "조사 개시")
        self.assertEqual(k("Commission Implementing Regulation (EU) 2026/2512 of 10 November 2026 imposing provisional anti-dumping duties on imports of certain acrylic esters"), "잠정 관세")
        self.assertEqual(k("Notice of the impending expiry of certain anti-dumping measures"), "만료 예정 공고")
        self.assertEqual(w.number_of(T2547, "32026R2547"), "2026/2547")


if __name__ == "__main__":
    unittest.main()
