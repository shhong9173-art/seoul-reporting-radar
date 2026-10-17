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
    def test_old_opening_recent_closure_and_invalid_calendar(self):
        row=rec("DP24001",opened="20240101").split("\t")
        row[7]="20261010"
        invalid=rec("PE26001",opened="20260931")
        out=n.parse_tab_data(("\t".join(row)+"\n"+invalid).encode(),NOW,lookback=7)
        self.assertEqual(len(out["items"]),1)
        self.assertEqual(out["items"][0]["officialEventDate"],"20261010")
        self.assertEqual(out["items"][0]["discoveryType"],"official_us_investigation_closed")

    def test_all_models_preserved_duplicates_and_order_do_not_change_fingerprint(self):
        a=rec("PE26001")
        b=a.replace("TUCSON","SANTA FE")
        first=n.parse_tab_data((a+"\n"+b).encode(),NOW)
        other=n.parse_tab_data((b+"\n"+a+"\n"+b).encode(),NOW)
        self.assertEqual(len(first["items"]),1)
        self.assertEqual(len(first["items"][0]["vehicles"]),2)
        self.assertEqual(first["items"][0]["sourceFingerprint"],other["items"][0]["sourceFingerprint"])

    def test_full_summary_changes_beyond_display_excerpt_are_detected(self):
        a=rec("PE26001").replace("Review ongoing","a"*1000+"original")
        b=a.replace("original","revised")
        first=n.parse_tab_data(a.encode(),NOW)
        first["generatedAt"]="2026-10-13"
        n.recent_changes(first,{})
        second=n.parse_tab_data(b.encode(),NOW)
        second["generatedAt"]="2026-10-14"
        n.recent_changes(second,first)
        self.assertEqual(second["changedObserved"],1)
        self.assertEqual(second["newlyObserved"],0)
        self.assertFalse(second["items"][0]["changeIsNewPublicationVerified"])
        self.assertEqual(first["items"][0]["summary"],second["items"][0]["summary"])

    def test_legacy_snapshot_is_baseline_not_new_content(self):
        current=n.parse_tab_data(rec("PE26001").encode(),NOW)
        current["generatedAt"]="2026-10-13"
        n.recent_changes(current,{"items":[{"actionNumber":"PE26001","firstSeenInRadar":"2026-10-01"}]})
        self.assertIsNone(current["items"][0]["sourceContentChanged"])
        self.assertEqual(current["changedObserved"],0)
        self.assertEqual(current["newlyObserved"],0)

    def test_conflicting_event_dates_are_not_single_new_date(self):
        a=rec("PE26001")
        b=a.replace("20261012","20261011")
        out=n.parse_tab_data((a+"\n"+b).encode(),NOW)["items"][0]
        self.assertTrue(out["eventDateConflict"])
        self.assertIsNone(out["officialEventDate"])

    def test_real_layout_year_and_make(self):
        contents="\n".join([rec("PE26-100"),rec("PE26-101","KIA"),
           rec("PE26-102","FORD","20261012","FORD"),rec("PE26-103","NOKIAN","20261012","NOKIAN"),
           rec("PE25-001","HYUNDAI","20250101")])
        d=n.parse_tab_data(contents.encode(),NOW)
        self.assertEqual(d["scannedRecords"],5)
        self.assertEqual(len(d["items"]),2)
        self.assertTrue(all(x["caution"].find("결함 확정")>=0 for x in d["items"]))
    def test_zip_streaming_uses_identical_tab_schema_without_extracting_archive(self):
        import io,zipfile
        holder=io.BytesIO()
        with zipfile.ZipFile(holder,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("FLAT_INV.txt","\n".join([
                rec("PE26-100"),rec("PE26-101","KIA")]))
        parsed=n.parse_zip_data(holder.getvalue(),now=NOW)
        self.assertEqual(parsed["scannedRecords"],2)
        self.assertEqual(len(parsed["items"]),2)

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
