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
