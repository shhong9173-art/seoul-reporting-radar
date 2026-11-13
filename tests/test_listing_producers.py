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

    def test_attach_once_per_line_and_reports_once_per_run(self):
        events = [ev("a1", ACETONE), ev("a2", "Ongoing Investigation " + ACETONE), ev("c1", COUNTRY), ev("x1", CHISEL),
                  ev("old", ACETONE, detected="2026-08-01T07:40:00+09:00"),                       # 45일 넘은 줄은 안 본다
                  ev("k1", "아세톤 덤핑 조사", page="ktc"), ev("r1", ACETONE, renumbered=True)]   # 국내 무역위·번호만 밀린 줄
        doc = {"events": events}
        n, reports = lp.attach(doc, None, "KEY", NOW, list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual((n, reports), (2, 3))
        self.assertEqual(sorted(doc["listingProducers"]), ["a1", "a2"])
        self.assertEqual(len(self.docs), 3)                         # 회사마다 보고서 한 번(두 줄이 같은 보고서를 다시 받지 않는다)
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
        # 다음 실행: 이미 본 줄은 다시 받지 않는다
        self.lists.clear()
        doc2 = {"events": events}
        self.assertEqual(lp.attach(doc2, doc, "KEY", NOW + dt.timedelta(days=1), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch), (0, 0))
        self.assertEqual((self.lists, sorted(doc2["listingProducers"])), ([], ["a1", "a2"]))
        # 키가 없으면 대조하지 않고 지난 결과만 넘긴다
        doc3 = {"events": events + [ev("t1", "Toluene Di-isocyanate (TDI) from Korea RP")]}
        self.assertEqual(lp.attach(doc3, doc2, "", NOW), (0, 0))
        self.assertNotIn("t1", doc3["listingProducers"])
        # 120일 지난 결과는 버린다
        doc4 = {"events": []}
        lp.attach(doc4, doc2, "KEY", NOW + dt.timedelta(days=130), list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual(doc4["listingProducers"], {})

    def test_no_word_in_any_report_adds_no_line(self):
        doc = {"events": [ev("f1", "Fumed silica from China PR and Korea RP")]}
        lp.attach(doc, None, "KEY", NOW, list_fetch=self.list_fetch, doc_fetch=self.doc_fetch)
        self.assertEqual(doc["listingProducers"]["f1"]["line"], "")
        self.assertEqual(lp.line(None), "")
        self.assertEqual(lp.line({"products": []}), "")


if __name__ == "__main__":
    unittest.main()
