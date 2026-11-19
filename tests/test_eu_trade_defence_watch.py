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


# 탐침 22(11-19, 470일 목록)의 실제 제목
TPTA_I = "Notice of initiation of an anti-dumping proceeding concerning imports of terephthalic acid, originating in the Republic of Korea and Mexico"
TPTA_P = ("Commission Implementing Regulation (EU) 2026/801 of 9 April 2026 imposing provisional anti-dumping duties on imports of terephthalic acid originating "
          "in the Republic of Korea and the United Mexican States")
TPTA_D = ("Commission Implementing Regulation (EU) 2026/1904 of 7 August 2026 imposing a definitive anti-dumping duty and definitively collecting the provisional "
          "duty imposed on imports of terephthalic acid originating in the Republic of Korea and the United Mexican States")
TTP_I = ("Notice of initiation of an expiry review of the anti-dumping measures applicable to imports of certain heavyweight thermal paper originating in the "
         "Republic of Korea")
TPVC_I = ("Notice of initiation of an anti-dumping proceeding concerning imports of certain Polyvinyl chloride (PVC) originating in the People’s Republic of "
          "China, Republic of Korea, Mexico and Taiwan")
TCE_I = "Notice of initiation of an anti-dumping proceeding concerning imports of certain cellulose ethers originating in the People’s Republic of China and the Republic of Korea"
THYB_I = "Notice of initiation of a safeguard investigation concerning imports of certain new hybrid vehicles for the transport of persons"
TSI_A = "Notice amending the notice of initiation of an interim review of the anti-dumping measures applicable to imports of silicon originating in the People’s Republic of China"
HIST = [("52025XC04539", "2025-08-13", TPTA_I), ("32026R0801", "2026-04-09", TPTA_P), ("32026R1904", "2026-08-07", TPTA_D),
        ("52025XC05537", "2025-10-17", TTP_I), ("32026R2311", "2026-10-19", T2311), ("52026XC04912", "2026-09-23", TPVC_I),
        ("52026XC04924", "2026-09-24", TCE_I), ("52026XC05780", "2026-10-30", THYB_I), ("52026XC06003", "2026-11-16", TSI_A)]
BODY_PVC = ("<p>8. SCHEDULE OF THE INVESTIGATION</p><p>The investigation will be concluded, pursuant to Article 6(9) of the basic Regulation within 13 months, "
            "but not later than 14 months of the date of the publication of this Notice. In accordance with Article 7(1) of the basic Regulation, provisional "
            "duties may be imposed normally not later than 7 months, but in any event not later than 8 months from the publication of this Notice. "
            "Interested parties are invited to submit comments.</p>")
BODY_HYB = ("<p>8. SCHEDULE OF THE INVESTIGATION</p><p>If the Commission determines that measures are necessary, the Commission shall take the necessary decisions "
            "in accordance with Chapter V of Regulations (EU) 2015/478 and (EU) 2015/755 respectively, no later than nine months from the date of initiation, unless "
            "exceptional circumstances exist, in which case that time limit may be extended by a maximum period of two months. If critical circumstances so require, "
            "the Commission may impose provisional measures. The duration of such measures shall not exceed 200 days.</p>")


class Proceedings(unittest.TestCase):
    def test_calendar_from_initiations_with_stages_and_deadlines(self):
        get, calls = fake(BASE + HIST, bodies={"52026XC04912": BODY_PVC, "52026XC05780": BODY_HYB})
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        self.assertEqual(calls.count("SPARQL"), 2)                           # 21일 목록 + 하루 한 번 긴 목록
        p = {x["celex"]: x for x in doc["proceedings"]}
        self.assertNotIn("52025XC04539", p)                                  # 테레프탈산: 08-07 확정(60일 넘음) — 끝난 사건
        self.assertNotIn("52026XC06003", p)                                  # 개시 공고 변경 공고는 사건이 아니다
        self.assertNotIn("52026XC06025", p)                                  # 중국산(제목에 한국 없음) 재심
        tp = p["52025XC05537"]
        self.assertEqual((tp["type"], tp["stage"], tp["deadlines"], tp["steps"][-1]["number"], tp["steps"][-1]["kind"]),
                         ("er", "done", [], "2026/2311", "확정 관세 연장(종료재심 결과)"))
        pvc = p["52026XC04912"]
        self.assertEqual((pvc["type"], pvc["typeKo"], pvc["stage"], pvc["korea"], pvc["beat"], pvc["product"]),
                         ("ad", "반덤핑 조사", "open", True, True, "Polyvinyl chloride (PVC)"))
        self.assertEqual([x["kind"] for x in pvc["steps"]], ["수입 등록"])
        self.assertEqual([(x["key"], x["date"]) for x in pvc["deadlines"]],
                         [("pre", "2027-03-26"), ("prov", "2027-04-23"), ("provMax", "2027-05-23"), ("final", "2027-11-23")])
        self.assertEqual(len(pvc["schedule"]), 2)
        self.assertTrue(pvc["schedule"][1].startswith("In accordance with Article 7(1) of the basic Regulation, provisional duties may be imposed normally not later than 7 months"))
        ce = p["52026XC04924"]
        self.assertEqual((ce["korea"], ce["beat"], ce["stage"], [x["kind"] for x in ce["steps"]]), (True, False, "open", ["수입 등록"]))
        hy = p["52026XC05780"]
        self.assertEqual((hy["type"], hy["korea"], hy["beat"], hy["product"]), ("sg", False, True, "new hybrid vehicles for the transport of persons"))
        self.assertEqual([(x["key"], x["date"]) for x in hy["deadlines"]], [("final", "2027-07-30"), ("finalMax", "2027-09-30")])
        self.assertIsNone(hy["schedule"])                                    # 일정 문장 읽기는 한 실행 2건 — 세 번째는 다음 실행
        self.assertEqual(ce["schedule"], [])                                 # 읽었지만 일정 문장 없음(다시 안 읽음)
        # 다음 실행(3시간 뒤): 긴 목록은 다시 안 받고, 남은 일정 문장을 읽고, 새 21일 목록의 잠정 관세 규정을 바로 반영한다
        tprov = ("Commission Implementing Regulation (EU) 2027/50 of 18 November 2026 imposing a provisional anti-dumping duty on imports of certain polyvinyl "
                 "chloride (PVC) originating in the People’s Republic of China, Republic of Korea, Mexico and Taiwan")
        get2, calls2 = fake(BASE + [("32027R0050", "2026-11-18", tprov)], bodies={"52026XC05780": BODY_HYB})
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertEqual(calls2.count("SPARQL"), 1)
        p2 = {x["celex"]: x for x in doc2["proceedings"]}
        self.assertEqual((p2["52026XC04912"]["stage"], [x["key"] for x in p2["52026XC04912"]["deadlines"]]), ("provisional", ["final"]))
        self.assertEqual(p2["52026XC04912"]["schedule"], pvc["schedule"])    # 읽어 둔 문장은 그대로
        self.assertTrue(any("no later than nine months from the date of initiation" in t for t in p2["52026XC05780"]["schedule"]))
        self.assertTrue(any("200 days" in t for t in p2["52026XC05780"]["schedule"]))

    def test_history_failure_keeps_previous_calendar(self):
        get, _ = fake(BASE + HIST)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        n = len(doc["proceedings"])
        calls = {"n": 0}

        def get2(url, params=None, headers=None, timeout=None):
            if url == w.SPARQL:
                calls["n"] += 1
                return R(200, rows(*BASE)) if calls["n"] == 1 else R(503)
            return R(200, text="<p>nothing</p>")
        doc2 = w.run(NOW + dt.timedelta(hours=25), doc, get=get2, sleep=lambda s: None)
        self.assertEqual(len(doc2["proceedings"]), n)
        self.assertEqual(doc2["historyAt"], doc["historyAt"])
        self.assertEqual(doc2["status"], "partial")
        self.assertIn("판정 일정 목록 HTTP 503 — 직전 목록", doc2["checks"][0]["error"])

    def test_safeguard_initiation_on_beat_product_is_a_event(self):
        get, _ = fake(BASE)
        doc = w.run(NOW, None, get=get, sleep=lambda s: None)
        get2, calls2 = fake(BASE + [("52026XC05780", "2026-11-18", THYB_I)], bodies={"52026XC05780": BODY_HYB})
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, get=get2, sleep=lambda s: None)
        self.assertIn(w.CELLAR + "52026XC05780", calls2)
        e = doc2["events"][0]
        self.assertEqual((e["tier"], e["kind"], e["korea"], e["safeguard"]), ("A", "EU 관보 무역구제(세이프가드 조사 개시)", False, True))
        self.assertIn("세이프가드 — 원산지 구분 없이 모든 수입(한국산 포함) 대상", e["text"])
        self.assertEqual(w.kind_of("Notice of initiation concerning the review of the safeguard measures applicable to imports of certain ferro-alloying elements")[0], "세이프가드 재심 개시")
        self.assertEqual(w.kind_of("Commission Implementing Regulation (EU) 2027/1 imposing provisional safeguard measures on imports of certain new hybrid vehicles")[0], "세이프가드 잠정 조치")
        # 업종 밖 품목 세이프가드는 본문을 받지 않는다
        get3, calls3 = fake(BASE + [("52026XC09999", "2026-11-18", "Notice of initiation of a safeguard investigation concerning imports of certain frozen fish fillets")])
        w.run(NOW + dt.timedelta(hours=3), doc, get=get3, sleep=lambda s: None)
        self.assertNotIn(w.CELLAR + "52026XC09999", calls3)

    def test_add_months_clamps_month_end(self):
        self.assertEqual(w.add_months(dt.date(2026, 8, 31), 6), dt.date(2027, 2, 28))
        self.assertEqual(w.add_months(dt.date(2026, 10, 30), 9), dt.date(2027, 7, 30))
        self.assertEqual(w.add_months(dt.date(2026, 12, 15), 1), dt.date(2027, 1, 15))

    def test_schedule_quote_is_trimmed(self):
        # 운영 11-19: 절 제목 뒤 공백이 따옴표 안에 남았다(" If the Commission …")
        self.assertEqual(w.schedule_quote("8. SCHEDULE OF THE INVESTIGATION  If the Commission determines that measures are necessary, no later than nine months from the date of initiation. Other."),
                         ["If the Commission determines that measures are necessary, no later than nine months from the date of initiation."])


if __name__ == "__main__":
    unittest.main()
