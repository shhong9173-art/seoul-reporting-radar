"""NHTSA Part573 exact campaign validation and paper's U.S. scope boundaries."""
import sys,unittest,hashlib
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import nhtsa_part573_primary as m
NOW=datetime(2026,10,16,5,35,tzinfo=timezone(timedelta(hours=9)))
PDF=b"%PDF-1.4\n"+b"0"*2300
def campaign():
    return {
      "status":"official_us_recalls_to_review","confirmedScoops":0,
      "generatedAt":"2026-10-16T05:00:00+09:00",
      "leads":[{"id":"26V664000","usRecallExists":True,
                "koreanRecallChecked":False,"exclusiveConfirmed":False},
               {"id":"26V588000","usRecallExists":True,
                "koreanRecallChecked":False,"exclusiveConfirmed":False}]
    }
def convert(blob):
    return ["NHTSA Part 573 Safety Recall Report 26V664" if b"664" in blob
            else "Part 573 Safety Recall Report 26V588",
            "Chronology of Principal Events: The manufacturer reported power seat motor overheat."]

def get(uri):
    if "26V664" in uri:return b"%PDF-1.4\n664"+b"0"*2300
    if "26V588" in uri:return b"%PDF-1.4\n588"+b"0"*2300
    raise ValueError("not recognized")
class NHTSAReport(unittest.TestCase):
    def test_official_report_exact_campaign_and_text_page_without_domestic_recall_conclusion(self):
        data=m.scan(campaign(),now=NOW,get=get,convert=convert)
        self.assertEqual(data["documentsAttempted"],3)
        self.assertEqual(data["documentsRead"],3)
        self.assertEqual(data["documentsWithErrors"],0)
        self.assertEqual(data["confirmedScoops"],0)
        self.assertFalse(data["koreanRecallAbsenceVerified"])
        for x in data["reports"]:
            self.assertTrue(x["campaignNumberFoundInPdf"])
            self.assertTrue(x["officialPdfDownloaded"])
            self.assertEqual(len(x["pdfContentSHA256"]),64)
            self.assertFalse(x["exactKoreanVehiclePartMatched"])
            self.assertFalse(x["domesticRecallAbsenceVerified"])
            self.assertTrue(all(p["koreanRecallAbsenceVerified"] is False for p in x["sourcePassages"]))

    def test_substantive_defect_on_page_two_and_chronology_not_crowded_by_page_one(self):
        pages=[
           "Part 573 Safety Recall Report 26V664. Total number of potentially involved: 94,622. "
           "Production Dates: Mar 17, 2016 - Nov 07, 2019. "
           "Description of safety risk, including crash, fire, death, injury:",
           "Description of the defect or noncompliance: The front seat slider and "
           "height adjustment control switch may become dislodged and the motor may overheat.",
           "Chronology of Principal Events: Hyundai reviewed reports and supplier records.",
           "Description of remedy program: Dealers inspect and replace the control switch."
        ]
        entries=m.passages(pages)
        tags={x["section"] for x in entries}
        self.assertIn("defect_description",tags)
        self.assertIn("chronology",tags)
        self.assertIn("remedy",tags)
        self.assertIn("production_dates",tags)
        self.assertIn("us_population",tags)
        defect=next(x for x in entries if x["section"]=="defect_description")
        self.assertEqual(defect["page"],2)
        self.assertIn("control switch",defect["literalPdfExcerpt"])
        self.assertFalse(any(x["keyword"].lower()=="fire" for x in entries))
        total=m.US_POPULATION.findall(pages[0])
        self.assertEqual(total,["94,622"])

    def test_us_reported_population_is_not_domestic_affected_vehicle_count(self):
        def mock_pdf(url):return b"%PDF-1.4\n664"+b"0"*2300 if "664" in url else b"%PDF-1.4\n588"+b"0"*2300
        def text_pdf(data):
            campaign="26V664" if b"664" in data else "26V588"
            count="94,622" if campaign=="26V664" else "5,360"
            return ["Part 573 Safety Recall Report "+campaign+
                " Total number of potentially involved: "+count]
        r=m.scan(campaign(),now=NOW,get=mock_pdf,convert=text_pdf)
        for x in r["reports"]:
            self.assertEqual(x["usVehicleCountScope"],
                "us_market_manufacturer_part573_not_korea_sales")
            self.assertEqual(x["usManufacturerReportedPotentiallyAffectedVehicles"],
                94622 if x["campaign"]=="26V664000" else 5360)
            self.assertFalse(x["exactKoreanVehiclePartMatched"])

    def test_campaign_id_missing_from_first_pages_discard_document_evidence(self):
        d=m.scan(campaign(),now=NOW,get=get,convert=lambda b:["Wrong file 26V777","Description of defect"])
        self.assertEqual(d["documentsRead"],0)
        self.assertEqual(d["documentsWithErrors"],3)
        self.assertTrue(all(not x["sourcePassages"] for x in d["reports"]))

    def test_bad_official_campaign_source_does_not_make_no_recall_evidence(self):
        s=campaign();s["confirmedScoops"]=1
        with self.assertRaises(ValueError):m.scan(s,now=NOW,get=get,convert=convert)
        s=campaign();s["leads"][0]["koreanRecallChecked"]=True
        result=m.scan(s,now=NOW,get=get,convert=convert)
        self.assertEqual(result["documentsAttempted"],2)

    def test_only_approved_static_nhtsa_exact_url_and_checked_document_bytes(self):
        for path in ["https://evil.example/odi/rcl/2026/RCLRPT-26V664-0680.pdf",
                     m.ROOT+"RCLRPT-26V999-7777.pdf"]:
            with self.assertRaises(ValueError):m.fetch_pdf(path)
        result=m.scan(campaign(),now=NOW,get=lambda u:b"not pdf",convert=convert)
        self.assertEqual(result["documentsRead"],0)

    def test_part573_form_labels_do_not_prove_park_outside_flag(self):
        hints=m.passages(["☐ Park Outside ☐ Do Not Drive Description of Defect: motor"])
        self.assertTrue(hints)
        self.assertTrue(all(x["koreanRecallAbsenceVerified"] is False for x in hints))
        self.assertNotIn("parkOutsideConfirmed",hints[0])

if __name__=="__main__":unittest.main()
