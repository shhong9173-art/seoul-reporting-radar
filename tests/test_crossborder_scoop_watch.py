import io
import sys
import unittest
import zipfile
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import crossborder_scoop_watch as n
import dart_foreign_dividend_watch as d

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,16,9,tzinfo=KST)


def rcl(campaign,make,model,year,reported="20261008",defect="The power seat switch may overheat and cause a fire."):
    cols=[""]*29
    cols[1]=campaign;cols[2]=make;cols[3]=model;cols[4]=str(year)
    cols[6]="SEATS";cols[7]=("Ford Motor Company" if make=="FORD" else "Hyundai Motor America");cols[10]="V"
    cols[15]=reported;cols[16]=reported
    cols[19]=defect;cols[20]="Fire risk when parked";cols[21]="Remedy under development"
    cols[28]="Y"
    return "\t".join(cols)


def nhtsa_zip(lines):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("FLAT_RCL_POST_2010.txt","\n".join(lines)+"\n")
    return out.getvalue()


def dart_zip(markup):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("document.xml",markup)
    return out.getvalue()


class SafetyCases(unittest.TestCase):
    def test_older_genesis_recall_no_longer_missed(self):
        data=n.scan_archive(nhtsa_zip([
            rcl("26V664000","GENESIS","G80",2017),
            rcl("26V664000","HYUNDAI","GENESIS",2015),
            rcl("26V123000","FORD","F-150",2026)]),now=NOW)
        self.assertEqual(data["campaignCount"],1)
        x=data["leads"][0]
        self.assertEqual(x["id"],"26V664000")
        self.assertEqual(x["modelCount"],2)
        self.assertIn("fire_or_thermal_word_in_us_summary",x["flags"])
        self.assertFalse(x["koreanIncidentVerified"])
        self.assertFalse(x["koreanRecallChecked"])
        self.assertFalse(x["exclusiveConfirmed"])
        self.assertEqual(data["domesticSourceStatus"],"not_connected")
        self.assertEqual(data["archiveLatestReceived"],"2026-10-08")

    def test_old_and_future_records_filtered(self):
        data=n.scan_archive(nhtsa_zip([
            rcl("26V123000","HYUNDAI","G80",2018,reported="20260801"),
            rcl("26V664000","KIA","SORENTO",2024,reported="20261015")]),now=NOW)
        self.assertEqual(data["campaignCount"],1)
        self.assertEqual(data["leads"][0]["id"],"26V664000")

    def test_stale_archive_is_not_empty_success(self):
        with self.assertRaises(ValueError):
            n.scan_archive(nhtsa_zip([
                rcl("26V123000","GENESIS","G80",2019,reported="20260901")]),now=NOW)

    def test_bad_zip_fails_closed(self):
        with self.assertRaises(ValueError):
            n.scan_archive(b"not a zip",now=NOW)

class ForeignDividend(unittest.TestCase):
    def test_subsidiary_and_dividend_same_table(self):
        xml="<SECTION-1><TITLE>III. 재무에 관한 사항</TITLE>"
        xml+="<P>종속회사로부터 배당금수익</P><TABLE><TR><TD>법인</TD><TD>배당금수익</TD></TR>"
        xml+="<TR><TD>Kia Slovakia s.r.o.</TD><TD>1,610,500</TD></TR></TABLE></SECTION-1>"
        result=d.extract_tables(xml,"기아","20260916000427")
        self.assertEqual(len(result),1)
        self.assertFalse(result[0]["cashReceiptVerified"])
        self.assertFalse(result[0]["historicalNetIncomeCompared"])
        self.assertIn("Kia Slovakia",result[0]["tableExcerpt"])

    def test_unrelated_table_does_not_cross_join(self):
        xml="<P>Kia Slovakia dividend</P><TABLE><TR><TD>Hyundai Czech</TD><TD>150</TD></TR></TABLE>"
        self.assertEqual(d.extract_tables(xml,"기아","20260916000427"),[])
        xml="<TABLE><TR><TD>Kia Slovakia</TD><TD>150</TD></TR></TABLE>"
        self.assertEqual(d.extract_tables(xml,"기아","20260916000427"),[])

    def test_document_zip_and_status(self):
        xml="<P>배당금</P><TABLE><TR><TD>Kia Slovakia</TD><TD>배당금수익</TD><TD>42</TD></TR></TABLE>"
        rows=d.document_tables("test","20260916000427","기아",fetch=lambda u:dart_zip(xml))
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]["scoopConfirmed"])

    def test_missing_key_not_reported_as_zero(self):
        sample={"companies":[{"company":"기아","current":{"receiptNo":"20260916000427"}}]}
        result=d.build(sample,"",now=NOW)
        self.assertEqual(result["sourceChecks"][2]["status"],"dart_api_key_unset")
        self.assertEqual(result["leads"],[])
        self.assertEqual(result["foreignRegistryStatus"],"not_connected")

if __name__=="__main__":
    unittest.main()
