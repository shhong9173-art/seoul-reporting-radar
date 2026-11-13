"""해외 조사 목록 새 줄(영문 품목) → 그 품목 낱말이 나온 출입처 사업보고서: 용어 표, 약어 경계, 보고서 대조, 다시 받지 않기."""
import datetime as dt
import io
import sys
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ktc_producers as kp  # noqa: E402
import listing_producers as lp  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 14, 7, 40, tzinfo=KST)
# 11-13 운영에서 본 인도 DGTR 줄 그대로
ACETONE = "Anti-dumping investigation concerning imports of Acetone from the Republic of Singapore, the Republic of Korea, Taiwan and the Kingdom of Thailand"
CHISEL = ('Ongoing Investigation Anti-dumping investigation concerning imports of "alloy steel chisel/ tool and hydraulic rock breaker in fully assembled '
          'condition" originating in or exported from China PR and Korea RP')
COUNTRY = "Country: China PR and Korea RP Type of Investigation: Anti-dumping Investigation Type of Proceeding: Anti Circumvention Investigation"


def report_zip(body):
    markup = ('<SECTION-1><TITLE>I. 회사의 개요</TITLE><P>개요 아세톤</P></SECTION-1>'
              f'<SECTION-1><TITLE>II. 사업의 내용</TITLE><P>{body}</P></SECTION-1>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("report.xml", markup)
    return buf.getvalue()


def ev(eid, text, page="in-dgtr", detected="2026-11-13T18:34:00+09:00", **kw):
    return {"id": eid, "pageId": page, "country": "인도", "label": "인도 DGTR 반덤핑 조사", "text": text, "url": f"https://www.dgtr.gov.in/{eid}", "detectedAt": detected, **kw}


class Glossary(unittest.TestCase):
    def test_english_product_names(self):
        names = lambda t: [x[0] for x in lp.products_in(t)]  # noqa: E731
        self.assertEqual(names(ACETONE), ["아세톤"])
        self.assertEqual(names("Sunset Review investigation concerning imports of Toluene Di-isocyanate (TDI) from Korea RP"), ["TDI"])
        self.assertEqual(names("Suspension Grade PVC Resin from Korea RP"), ["PVC"])
        # 11-14 운영에서 본 줄 그대로: CPVC는 PVC가 아니다
        self.assertEqual(names("Anti-Dumping investigation concerning imports of ‘Chlorinated Polyvinyl Chloride (CPVC)- Whether or not further processed into compound’ from Korea RP and China PR"), ["CPVC"])
        self.assertEqual(names("Poly Vinyl Chloride Paste Resin from Korea RP"), ["PVC"])
        self.assertEqual(names("Welded Stainless Steel Pipes and Tubes"), ["스테인리스", "강관"])
        self.assertEqual(names("Hot Rolled flat products of alloy or non-alloy steel"), ["열연"])
        self.assertEqual(names("Styrene Butadiene Rubber (SBR) of 1500 series"), ["SBR"])
        self.assertEqual(names("Fumed silica from China PR and Korea RP"), ["흄드실리카"])
        # 용어 표에 없는 품목·나라 줄은 아무것도 안 붙인다(추측하지 않는다)
        self.assertEqual(names(CHISEL), [])
        self.assertEqual(names(COUNTRY), [])
        self.assertEqual(names("Mid-term review of Sodium Cyanide from Korea RP"), [])
        # 약어는 대문자 그대로일 때만: 'pet food'·'goes'·'bisphenol' 속 phenol
        self.assertEqual(names("pet food that goes to market"), [])
        self.assertEqual(names("Bisphenol-A from Korea RP"), ["비스페놀A"])
        self.assertEqual(names("PET resin from Korea RP"), ["PET"])

    def test_report_words_respect_abbreviation_boundaries(self):
        self.assertEqual(lp.find("당사는 SSBR 설비를 증설했습니다.", ["SBR", "스티렌부타디엔"])[0], 0)       # 'SSBR' 속 'SBR'은 다른 품목
        hits, seg, term = lp.find("합성고무 부문은 SBR, NBR 라텍스를 생산합니다. SBR은 타이어용입니다.", ["SBR", "스티렌부타디엔"])
        self.assertEqual((hits, term), (2, "SBR"))
        self.assertIn("SBR, NBR 라텍스", seg)
        self.assertEqual(lp.find("페놀, 아세톤, BPA를 생산", ["아세톤"])[0], 1)

    def test_korean_words_do_not_match_inside_other_products(self):
        # 11-14 첫 운영: 인도 DGTR '페놀' 줄에 롯데케미칼 보고서의 '비스페놀A(BPA)'가 걸렸다(다른 품목)
        lotte = "[BPA] PC의 주요 원재료인 비스페놀A(BPA)는 원료 가격 및 공급 구조에 따라 가격 변동이 발생합니다."
        self.assertEqual(lp.find(lotte, ["페놀"])[0], 0)
        self.assertEqual(lp.find(lotte, ["비스페놀", "BPA"])[0:3:2], (2, "BPA"))                                # 비스페놀A 줄에는 맞게 걸린다
        self.assertEqual(lp.find("당사는 페놀과 아세톤을 생산합니다. 주요 제품: 페놀(Phenol)", ["페놀"])[0], 2)     # 조사·괄호가 붙는 것은 센다
        self.assertEqual(lp.find("폴리에틸렌테레프탈레이트(PET) 및 폴리에틸렌 테레프탈레이트", ["폴리에틸렌"])[0], 0)
        self.assertEqual(lp.find("고밀도 폴리에틸렌(HDPE)을 생산", ["폴리에틸렌", "HDPE"])[0], 1)
        self.assertEqual(lp.find("폴리프로필렌글리콜(PPG)", ["폴리프로필렌"])[0], 0)
        self.assertEqual(lp.find("아크릴로니트릴부타디엔스티렌(ABS) 수지", ["아크릴로니트릴"])[0], 0)
        self.assertEqual(lp.find("빅데이터 분석도구를 도입", ["석도"])[0], 0)
        self.assertEqual(lp.find("석도강판과 냉연강판", ["석도"])[0], 1)
        self.assertEqual(lp.find("디에틸렌글리콜, 폴리에틸렌글리콜", ["에틸렌글리콜"])[0], 0)
        self.assertEqual(lp.find("NB라텍스 및 H형강", ["라텍스"])[0], 1)                                     # 앞이 영문자인 것은 센다
        self.assertEqual(lp.find("NB라텍스 및 H형강", ["형강"])[0], 1)
        self.assertEqual([x[0] for x in lp.products_in("Acrylic Acid from Korea RP")], [])                    # 용어 표에서 뺌('에틸렌 아크릴산'과 못 가름)


class Attach(unittest.TestCase):
    def setUp(self):
        self.lists, self.docs = [], []
        self.codes = {"LG화학": "00356361", "금호석유화학": "00106368", "롯데케미칼": "00165413", "한화솔루션": "00162461"}
        self._orig = kp.corp_codes
        kp.corp_codes = lambda: self.codes

    def tearDown(self):
        kp.corp_codes = self._orig

    def list_fetch(self, url):
        self.lists.append(url)
        code = url.split("corp_code=")[1].split("&")[0]
        if code == "00165413":
            raise ConnectionError("x")                # 롯데케미칼: 목록 조회 실패 → 미확인
        return {"status": "000", "total_page": 1, "list": [{"corp_code": code, "rcept_no": f"20260310{code[-6:]}", "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260310"}]}

    def doc_fetch(self, url):
        self.docs.append(url)
        if "20260310356361" in url:   # LG화학
            return report_zip("석유화학 부문은 페놀, 아세톤, BPA 등을 생산합니다. 아세톤은 용제로 쓰입니다.")
        if "20260310106368" in url:   # 금호석유화학
            return report_zip("자회사는 페놀·아세톤 사업을 한다.")
        return report_zip("주요 제품은 TDI, 가성소다, PVC이다.")

    def test_reports_are_indexed_once_and_lines_use_the_index(self):
        events = [ev("a1", ACETONE), ev("a2", "Ongoing Investigation " + ACETONE), ev("c1", COUNTRY), ev("x1", CHISEL),
                  ev("old", ACETONE, detected="2026-08-01T07:40:00+09:00"),                       # 45일 넘은 줄은 안 본다
                  ev("k1", "아세톤 덤핑 조사", page="ktc"), ev("r1", ACETONE, renumbered=True)]   # 국내 무역위·번호만 밀린 줄
        doc = {"events": events}
        n, reports = lp.attach(doc, None, "KEY", NOW, list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual((n, reports), (2, 3))
        self.assertEqual(sorted(doc["listingProducers"]), ["a1", "a2"])
        self.assertEqual(len(self.docs), 3)                         # 회사마다 보고서 한 번
        idx = doc["producerIndex"]
        self.assertEqual((idx["LG화학"]["status"], idx["LG화학"]["year"], idx["LG화학"]["terms"]["아세톤"][0]), ("found", 2025, 2))
        self.assertIn("BPA", idx["LG화학"]["terms"])                # 용어 표의 다른 낱말도 한 번에 세어 둔다(다음 줄은 DART를 안 부른다)
        self.assertNotIn("text", idx["LG화학"])                     # 보고서 글 자체는 저장하지 않는다
        got = doc["listingProducers"]["a1"]
        by = {c["company"]: c for c in got["products"][0]["companies"]}
        self.assertEqual((by["LG화학"]["status"], by["LG화학"]["hits"], by["LG화학"]["term"]), ("found", 2, "아세톤"))
        self.assertEqual(by["금호석유화학"]["hits"], 1)
        self.assertEqual(by["한화솔루션"]["status"], "none")        # 보고서에 낱말 없음(안 만든다는 뜻 아님)
        self.assertEqual(by["롯데케미칼"]["status"], "error")
        self.assertEqual(by["S-OIL"]["status"], "no_code")
        self.assertTrue(got["line"].startswith("품목 낱말이 나온 출입처 2025 사업보고서(II. 사업의 내용): 아세톤 — LG화학 2곳 「"))
        self.assertIn("(접수 20260310356361) · 금호석유화학 1곳 「", got["line"])
        self.assertIn("미확인 5곳", got["line"])                    # 조회 실패 1 + 고유번호 없음 4
        self.assertTrue(got["line"].endswith("— 보고서에 낱말이 있다는 것뿐, 조사 대상 수출자인지·그 나라 수출 여부는 미확인(회사 확인)"))
        self.assertNotIn("I. 회사의 개요", got["line"])
        # 다음 실행: 받은 보고서는 다시 받지 않는다. 새 줄(TDI)도 색인으로만 대조한다. 실패한 회사만 다시 묻는다
        self.lists.clear()
        self.docs.clear()
        doc2 = {"events": events + [ev("t1", "Sunset Review investigation concerning imports of Toluene Di-isocyanate (TDI) from Korea RP")]}
        n2, reports2 = lp.attach(doc2, doc, "KEY", NOW + dt.timedelta(days=1), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual((n2, reports2, self.docs), (3, 0, []))
        self.assertEqual(len(self.lists), 1)                        # 롯데케미칼만 다시(나머지 넷은 고유번호 없음 — DART를 부르지 않는다)
        tdi = {c["company"]: c for c in doc2["listingProducers"]["t1"]["products"][0]["companies"]}
        self.assertEqual((tdi["한화솔루션"]["status"], tdi["한화솔루션"]["term"], tdi["LG화학"]["status"]), ("found", "TDI", "none"))
        # 낱말 세는 규칙이 바뀌기 전에 만든 색인(iv 다름)은 버리고 다시 받는다
        stale = {**doc2, "producerIndex": {k: {**v, "iv": lp.INDEX_VERSION - 1} for k, v in doc2["producerIndex"].items()}}
        self.docs.clear()
        lp.attach({"events": events}, stale, "KEY", NOW + dt.timedelta(days=1), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual(len(self.docs), 3)
        # 세 번 실패한 회사는 7일 동안 다시 묻지 않는다
        doc3 = {"events": events}
        lp.attach(doc3, doc2, "KEY", NOW + dt.timedelta(days=2), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual(doc3["producerIndex"]["롯데케미칼"]["tries"], 3)
        self.lists.clear()
        doc4 = {"events": events}
        lp.attach(doc4, doc3, "KEY", NOW + dt.timedelta(days=3), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual(self.lists, [])
        # 키가 없어도 저장된 색인으로 새 줄을 대조한다. 색인도 키도 없으면 아무것도 안 한다
        doc5 = {"events": [ev("n1", ACETONE, detected="2026-11-16T07:40:00+09:00")]}
        self.assertEqual(lp.attach(doc5, doc4, "", NOW + dt.timedelta(days=3)), (1, 0))
        self.assertIn("LG화학 2곳", doc5["listingProducers"]["n1"]["line"])
        doc6 = {"events": [ev("n1", ACETONE)]}
        self.assertEqual(lp.attach(doc6, None, "", NOW), (0, 0))
        self.assertEqual((doc6["listingProducers"], doc6["producerIndex"]), ({}, {}))
        # 보고서 연도가 바뀌면(4월) 색인을 새로 만든다. 120일 지난 줄 결과는 버린다
        doc7 = {"events": []}
        lp.attach(doc7, doc4, "KEY", dt.datetime(2027, 4, 2, 7, 40, tzinfo=KST), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual((doc7["producerIndex"], doc7["listingProducers"]), ({}, {}))

    def test_fetch_false_only_uses_the_stored_index(self):
        # 무역구제 결과를 저장하기 전 단계: 보고서를 받지 않는다(색인이 비어 있으면 줄도 안 붙는다)
        doc = {"events": [ev("a1", ACETONE)]}
        self.assertEqual(lp.attach(doc, None, "KEY", NOW, fetch=False, list_fetch=self.list_fetch, doc_fetch=self.doc_fetch), (1, 0))
        self.assertEqual((self.lists, doc["producerIndex"], doc["listingProducers"]["a1"]["line"]), ([], {}, ""))
        # 저장한 뒤 단계: 같은 doc을 이전 상태로 넘겨 색인을 채우고 줄을 다시 대조한다
        self.assertEqual(lp.attach(doc, doc, "KEY", NOW, list_fetch=self.list_fetch, doc_fetch=self.doc_fetch), (1, 3))
        self.assertIn("LG화학 2곳", doc["listingProducers"]["a1"]["line"])
        doc2 = {"events": [ev("a1", ACETONE), ev("t1", "Toluene Di-isocyanate (TDI) from Korea RP")]}
        self.assertEqual(lp.attach(doc2, doc, "KEY", NOW + dt.timedelta(days=1), fetch=False), (2, 0))
        self.assertIn("한화솔루션", doc2["listingProducers"]["t1"]["line"])

    def test_time_budget_defers_the_rest_to_the_next_run(self):
        # 11-14 첫 운영: 보고서 한 곳에 50초쯤 — 한 실행 TIME_BUDGET초까지, 남은 회사는 다음 실행
        self.codes.pop("롯데케미칼")
        ticks = iter([0, 10, lp.TIME_BUDGET + 10, 2000, 3000, 4000, 5000, 6000, 7000, 8000])
        doc = {"events": [ev("a1", ACETONE)]}
        n, reports = lp.attach(doc, None, "KEY", NOW, list_fetch=self.list_fetch, doc_fetch=self.doc_fetch, clock=lambda: next(ticks))
        self.assertEqual((n, reports, sorted(doc["producerIndex"])), (1, 1, ["LG화학"]))          # 첫 회사만 받고 멈춤
        by = {c["company"]: c for c in doc["listingProducers"]["a1"]["products"][0]["companies"]}
        self.assertEqual((by["LG화학"]["status"], by["금호석유화학"]["status"]), ("found", "pending"))
        self.assertIn("미확인 7곳", doc["listingProducers"]["a1"]["line"])
        doc2 = {"events": [ev("a1", ACETONE)]}
        n2, reports2 = lp.attach(doc2, doc, "KEY", NOW + dt.timedelta(days=1), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual(reports2, 2)                                # 금호석유화학·한화솔루션(LG화학은 다시 안 받음)
        self.assertIn("금호석유화학 1곳", doc2["listingProducers"]["a1"]["line"])

    def test_no_word_in_any_report_adds_no_line(self):
        doc = {"events": [ev("f1", "Fumed silica from China PR and Korea RP")]}
        lp.attach(doc, None, "KEY", NOW, list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual(doc["listingProducers"]["f1"]["line"], "")
        self.assertEqual(lp.line(None), "")
        self.assertEqual(lp.line({"products": []}), "")


if __name__ == "__main__":
    unittest.main()
