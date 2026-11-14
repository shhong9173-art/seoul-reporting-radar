"""인도 DGTR 판정문·개시 고시 PDF 대목 뽑기 — 탐침 234·235에서 본 글 꼴(흄드실리카 일몰재심 판정문, IPA 개시 고시 글자 인식본)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dgtr_docs as d  # noqa: E402

BEAT = [("OCI홀딩스", r"\bOCI\b"), ("LG화학", r"\bLG Chem")]

# 탐침 235: 판정문 1~3쪽(쪽 머리·꼬리 줄 포함), 32~33쪽 통계 표, 권고, 51쪽 세율 표 — 줄바꿈 자리 그대로
FINDINGS_PAGES = ["""F. No. 7/09/2026-DGTR – Final Findings Non-confidential
DGTR, Department of Commerce, Government of India 1 | P a g e
Case No. AD (SSR) – 05/2026
F. No. 7/09/2026-DGTR
Government of India
Ministry of Commerce & Industry
Department of Commerce
Directorate General of Trade Remedies
4th Floor, Jeevan Tara Building, 5, Parliament Street,
New Delhi – 110001
Dated November 2026
NOTIFICATION
FINAL FINDINGS
Case No. AD (SSR)-05/2026
Sunset review investigation concerning anti -dumping duty imposed on the imports of
“Untreated Fumed Silica” originating in or exported from China PR
F. No. 7/09/2026-DGTR: Having regard to the Customs Tariff Act, 1975, as amended from
time to time (hereinafter referred to as the “Act”) and the Customs Tariff Rules, 1995, the Designated Authority hereby issues these final findings.
A. BACKGROUND OF THE CASE
2. The Authority received an application from the domestic industry.
3. The original anti -dumping investigation concerning imports of the product under
consideration from China PR and Korea RP was initiated by the Authority vide notification
dated 22 nd September 2020. Pursuant to a duly substantiated application filed by the
domestic industry, the Authority recommended definitive duties.
""", """F. No. 7/09/2026-DGTR – Final Findings Non-confidential
DGTR, Department of Commerce, Government of India 3 | P a g e
7. Anti-dumping duties are in force on the imports of the product under consideration from
China PR and Korea RP. The application was filed in respect of dumping of the product
under consideration from China PR only. Accordingly, since there was no duly
substantiated request alleging the likelihood of continuation or recurrence of
dumping and injury to the domestic industry in the event of cessation of anti-dumping duty
from Korea RP, the present review was not initiated in respect of imports from Korea RP.
8. In accordance with the above, the Authority is required to review, on the basis of a duly
substantiated request, whether the expiry of duty is likely to lead to continuation of dumping.
42. M/s OCI Company Ltd. has not filed any questionnaire response in the present review.
""", """7/09/2026-DGTR I/145225/2026
100. It is noted that, other than the subject imports, imports have entered from Korea RP,
Belgium, Japan and Germany. The volume of these imports has increased. However, the
exports from Belgium, Japan and Germany are at prices significantly higher than the
subject imports and the Imports from Korea RP are negligible. Imports from other
countries are not undercutting the prices of the domestic industry.
China MT 770 960 1,300 1,381
Korea RP MT 56 71 104 82
European Union MT 791 780 966 930
N. RECOMMENDATION
162. The Authority notes that the present proceedings were conducted in accordance with the
Act and the Rules. All interested parties were duly notified and were granted adequate
opportunity to provide information. Pursuant to the sunset
review, the Authority has arrived at the conclusion that continuation of the existing anti -
dumping duties is required in the present case for a further period of five years.
163. The Authority considers it appropriate to recommend continuation of the definitive anti -dumping duty
recommended vide Final Findings No. 6/40/2020 -DGTR dated 20th September 2021.
164. The Authority, after examining submissions made by all interested parties in the present
investigation, considers it appropriate and necessary to recommend continuation of
definitive duties equal to the figure indicated in Column 7 of the duty table below for a
period of five (5) years, on all imports of the subject goods originating in or exported from
the subject country.
Duty Table
S
N Heading Description
Country
of
Origin
Country
of
export
Producer Amount UOM Currency
1 2 3 4 5 6 7 8 9
1 2811220
0
Untreated
Fumed
Silica
China
PR
Any
country
includi
ng
China
PR
Shandong
Dongyue
Silicone
Material Co.,
Ltd.
1,296 MT USD
2 do do China
PR
Any
country
includi
ng
China
PR
Wacker
Chemicals
Fumed Silica
(Zhangjiagang)
Co., Ltd.
NIL MT USD
3 do do China
PR
Any
country
Any other
producer
1,296 MT USD
165. An exporter claiming the individual duty rate shall present a valid commercial invoice.
O. FURTHER PROCEDURE
167. An appeal against the determination of the Designated Authority in these final findings
shall lie before the Customs, Excise and Service Tax Appellate Tribunal.
"""]

# 탐침 235: IPA 개시 고시 글자 인식본(8쪽)의 앞부분·소제목 꼴. 신청인 이름은 지어낸 것(탐침은 그 줄을 찍지 않았다)
INITIATION_TEXT = """To be published in Part-I Section I of the Gazette of India Extraordinary
F. No. 6/62/2026-DGTR
Government of India
Department of Commerce
Ministry of Commerce and Industry
(Directorate General of Trade Remedies)
4th Floor, Jeevan Tara Building 5, Parliament Street, New Delhi - 110001
Dated: 28.09.2026
INITIATION NOTIFICATION
SETU CASE ID - AD/OI/063/2026
Subject: Initiation of anti-dumping investigation concerning imports of Isopropyl
Alcohol from the European Union, South Korea, Taiwan and the United States of
America.
1. F. No. 6/62/2026-DGTR: Having regards to the Customs Tariff Act, 1975, as amended
from time to time (hereinafter referred to as the ‘Act’) and the Rules, M/s Example Phenolics Limited
(hereinafter referred to as the ‘applicant’) has filed an application before the Designated
Authority (hereinafter referred to as the ‘Authority’), for initiation of an anti-dumping investigation on
imports of Isopropyl Alcohol (hereinafter referred to as the ‘product under consideration’) from
the European Union, South Korea, Taiwan and the United States of America (hereinafter referred to as the ‘subject countries’).
2. The applicant has alleged that material injury is being caused to the domestic industry.
A. Product under consideration
4. The product under consideration in the present investigation is “Isopropyl Alcohol”, also known as isopropanol or IPA.
C. Domestic industry & standing
11. The application has been filed by M/s Example Phenolics Limited. There is one other producer of the subject goods in India.
D. Subject countries
13. The subject countries in the present investigation are the European Union, South Korea, Taiwan and the United States of America.
E. Period of investigation
14. The applicant has proposed the period of investigation as Ist April 2025 to 31st March 2026, which is a period of 12 months. The Authority has considered the period of
investigation as Ist April 2025 to 31st March 2026. The injury investigation period will cover 2022-23, 2023-24, 2024-25 and the period of investigation.
K. Time limit
26. Any information relating to the present investigation should be sent to the Authority within thirty days from the date of receipt of the notice.
"""


class Findings(unittest.TestCase):
    def setUp(self):
        self.f = d.findings_from_pages(FINDINGS_PAGES, BEAT, pages=52)

    def test_subject_and_case_number_come_from_the_first_page(self):
        self.assertEqual(self.f["subject"], "Sunset review investigation concerning anti -dumping duty imposed on the imports of “Untreated Fumed Silica” originating in or exported from China PR")
        self.assertEqual((self.f["caseNo"], self.f["pages"], self.f["ocr"]), ("AD (SSR) – 05/2026", 52, False))
        self.assertNotIn("hereinafter", self.f["subject"])                                          # 11-14 운영: 번호 없는 1항('F. No. …: Having regard to')이 설명 줄에 딸려 왔다

    def test_korea_sentences_are_original_and_decisive_first(self):
        k = self.f["korea"]
        self.assertEqual(self.f["koreaTotal"], 3)
        self.assertTrue(k[0].startswith("(7항) "))                                                    # 결정에 닿는 문단 먼저
        self.assertIn("the present review was not initiated in respect of imports from Korea RP.", k[0])
        self.assertTrue(any("Imports from Korea RP are negligible" in x for x in k))
        self.assertFalse(any("56 71 104 82" in x for x in k))                                       # 통계 표 숫자 줄은 섞지 않는다
        self.assertFalse(any("P a g e" in x or "I/145225" in x for x in k))                         # 쪽 머리·꼬리 줄 없음
        self.assertFalse(any("Shandong" in x for x in k))                                           # 세율 표 줄은 문단이 아니다

    def test_recommendation_and_duty_table(self):
        self.assertIn("continuation of the existing anti - dumping duties is required in the present case for a further period of five years.", self.f["recommendation"])
        self.assertNotIn("Shandong", self.f["recommendation"])
        self.assertTrue(self.f["recommendation"].startswith("Pursuant to the sunset review, the Authority has arrived at the conclusion"))   # 절차 문장('duly notified …')은 앞에 오지 않는다
        self.assertNotIn("duly notified", self.f["recommendation"])
        duty = self.f["duty"]
        self.assertEqual((duty["rows"], duty["korea"]), (3, []))                                    # 세율 표에 한국 줄이 없다 — 이번 재심은 중국만
        self.assertEqual(duty["sample"][0], "1 2811220 0 Untreated Fumed Silica China PR Any country includi ng China PR Shandong Dongyue Silicone Material Co., Ltd. 1,296 MT USD")
        self.assertTrue(duty["sample"][1].endswith("Co., Ltd. NIL MT USD"))
        self.assertEqual((self.f["beat"], len(self.f["beatLines"])), (["OCI홀딩스"], 1))
        self.assertIn("OCI Company Ltd. has not filed", self.f["beatLines"][0])

    def test_table_without_korea_and_no_table(self):
        korea_table = FINDINGS_PAGES[2].replace("3 do do China\nPR\nAny\ncountry\nAny other\nproducer\n1,296 MT USD", "3 do do Korea\nRP\nKorea\nRP\nAny\nproducer\n301.5 MT USD")
        f = d.findings_from_pages(FINDINGS_PAGES[:2] + [korea_table], BEAT)
        self.assertEqual(f["duty"]["korea"], ["3 do do Korea RP Korea RP Any producer 301.5 MT USD"])
        none = d.findings_from_pages(["FINAL FINDINGS\nSubject line here\n1. Text only.\n2. The Authority recommends termination of the investigation against Korea RP."], BEAT)
        self.assertEqual((none["duty"]["rows"], none["recommendation"]), (0, ""))
        self.assertIn("termination of the investigation against Korea RP", none["korea"][0])

    def test_long_sentence_keeps_the_part_around_korea(self):
        long = "9. " + "The Authority examined the submissions of all the parties in great detail " * 12 + "and found that the dumping margin for exports from Korea RP is de minimis."
        s = d.sentences_with(long, d.KOREA, 200)
        self.assertTrue(s.startswith("…") and "Korea RP is de minimis." in s and len(s) <= 205)


class Initiation(unittest.TestCase):
    def test_applicant_period_and_time_limit(self):
        i = d.initiation_from_pages([INITIATION_TEXT], BEAT, ocr=True, pages=8)
        self.assertEqual(i["subject"], "Initiation of anti-dumping investigation concerning imports of Isopropyl Alcohol from the European Union, South Korea, Taiwan and the United States of America.")
        self.assertEqual((i["dated"], i["ocr"], i["pages"]), ("28.09.2026", True, 8))
        self.assertIn("M/s Example Phenolics Limited (hereinafter referred to as the ‘applicant’) has filed an application", i["applicant"])
        self.assertTrue(i["poi"].startswith("14. The applicant has proposed the period of investigation as Ist April 2025 to 31st March 2026"))   # 글자 인식 그대로('Ist')
        self.assertTrue(i["industry"].startswith("11. The application has been filed by M/s Example Phenolics Limited."))
        self.assertIn("within thirty days", i["timeLimit"])
        self.assertEqual(i["beat"], [])

    def test_missing_sections_stay_empty(self):
        i = d.initiation_from_pages(["INITIATION NOTIFICATION\nSubject: Initiation of sunset review\n1. The petitioner has requested a review. The period of investigation is 1st April 2025 to 31st March 2026."], BEAT)
        self.assertEqual((i["applicant"], i["industry"], i["timeLimit"]), ("", "", ""))
        self.assertIn("period of investigation is 1st April 2025", i["poi"])


class Reading(unittest.TestCase):
    def test_scanned_pdf_goes_through_ocr_and_failures_are_errors(self):
        orig = d.pdf_pages
        try:
            d.pdf_pages = lambda data, limit=d.MAX_PAGES: (8, [""] * 8)
            calls = []

            def ocr(data, ranges):
                calls.append(ranges)
                return [INITIATION_TEXT], None
            n, texts, scanned = d.page_texts(b"%PDF", "initiation", ocr=ocr)
            self.assertEqual((n, scanned, calls), (8, True, [[(1, 8)]]))
            d.pdf_pages = lambda data, limit=d.MAX_PAGES: (52, [""] * 52)
            d.page_texts(b"%PDF", "findings", ocr=ocr)
            self.assertEqual(calls[-1], [(1, 3), (43, 52)])                                         # 스캔 판정문은 앞 3쪽·끝 10쪽만
            with self.assertRaisesRegex(RuntimeError, "글자 인식 도구 없음"):
                d.page_texts(b"%PDF", "initiation", ocr=lambda data, ranges: ([], "글자 인식 도구 없음"))
            d.pdf_pages = lambda data, limit=d.MAX_PAGES: (2, ["x" * 500, "y" * 500])
            self.assertEqual(d.page_texts(b"%PDF", "findings", ocr=ocr)[2], False)                  # 글자 PDF는 글자 인식을 부르지 않는다
            self.assertEqual(len(calls), 2)
        finally:
            d.pdf_pages = orig

    def test_ocr_without_tools_and_budget(self):
        self.assertEqual(d.ocr_pages(b"x", [(1, 2)], which=lambda name: None), ([], "글자 인식 도구 없음"))

        class R:
            returncode, stdout = 0, "page text"
        clock = iter([0, 0, 200, 200, 200]).__next__
        texts, err = d.ocr_pages(b"x", [(1, 2)], run=lambda *a, **k: R(), which=lambda name: "/usr/bin/" + name, budget=120, clock=clock)
        self.assertEqual(texts, [])                                                                 # 쪽 그림이 없으면 읽은 것도 없다(시간 상한 표시는 다음 줄)
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
