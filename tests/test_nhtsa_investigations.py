import sys
import unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nhtsa_investigations as n
NOW=datetime(2026,10,13,tzinfo=timezone(timedelta(hours=9)))

def rec(action,make="HYUNDAI",opened="20261012",mfr="HYUNDAI MOTOR COMPANY"):
    return "\t".join([action,make,"TUCSON","2026","ELECTRICAL SYSTEM",mfr,
                      opened,"","","Possible electrical issue","Review ongoing"])
class Tests(unittest.TestCase):
    def test_real_layout_year_and_make(self):
        contents="\n".join([rec("PE26-100"),rec("PE26-101","KIA"),
           rec("PE26-102","FORD","20261012","FORD"),rec("PE26-103","NOKIAN","20261012","NOKIAN"),
           rec("PE25-001","HYUNDAI","20250101")])
        d=n.parse_tab_data(contents.encode(),NOW)
        self.assertEqual(d["scannedRecords"],5)
        self.assertEqual(len(d["items"]),2)
        self.assertTrue(all(x["caution"].find("결함 확정")>=0 for x in d["items"]))
    def test_first_seen_is_not_first_published(self):
        d={"generatedAt":"2026-10-13T12:00:00+09:00",
           "items":[{"actionNumber":"PE26-100","openedDate":"20261001"}]}
        n.recent_changes(d,{})
        self.assertEqual(d["newlyObserved"],1)
        self.assertEqual(d["items"][0]["observationState"],"first_observed_in_this_radar")
        nxt={"generatedAt":"2026-10-14T12:00:00+09:00",
             "items":[{"actionNumber":"PE26-100","openedDate":"20261001"}]}
        n.recent_changes(nxt,d)
        self.assertEqual(nxt["newlyObserved"],0)
        self.assertEqual(nxt["items"][0]["firstSeenInRadar"],"2026-10-13T12:00:00+09:00")
    def test_malformed_and_future_not_new_discoveries(self):
        d=n.parse_tab_data(("\n".join([rec("PE26-110","HYUNDAI","20261020"),
          "not a valid row",rec("PE26-111","BMW","20261012","BMW")])).encode(),NOW)
        self.assertEqual(len(d["items"]),1)
        self.assertIn("BMW코리아",d["items"][0]["coveredIssuerRelation"])
    def test_no_generic_mfr_false_positive(self):
        self.assertIsNone(n.direct_make("NOKIAN","NOKIAN TIRES"))
        self.assertIsNone(n.direct_make("GENERAL","KIAH COMPANY"))
        self.assertEqual(n.direct_make("KIA","KIA"),"기아")
if __name__=="__main__":unittest.main()
