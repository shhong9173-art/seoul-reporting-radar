"""Public Korea recall/press index must never raise editorial confidence."""
import sys,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from test_crossborder_source_gap_triage import sources
import domestic_recall_screen as screen
import crossborder_source_gap_triage as gap
NOW=datetime(2026,10,16,11,0,tzinfo=timezone(timedelta(hours=9)))
class DomesticDossier(unittest.TestCase):
    def test_visible_model_listing_does_not_change_any_pitch_gate(self):
        n,d=sources()
        current=screen.scan(n,now=NOW,fetch=lambda u:(
           ("<h1>리콜현황</h1><p>국토교통부</p>"
            "<a href='/ri/stat/view.do'>[현대] G80 - 시트 관련 리콜</a>").encode()
           if "car.go.kr" in u else b"<rss><channel></channel></rss>"))
        output=gap.build(n,d,now=NOW,domestic_screen=current)
        us=next(x for x in output["items"] if x["id"]=="usrecall:26V664000")
        self.assertEqual(us["domesticPublicScreen"]["status"],
                         "public_search_screen_manual_verification_required")
        self.assertTrue(us["domesticPublicScreen"]["officialQueries"][0]["titles"])
        self.assertFalse(us["domesticPublicScreen"]["domesticRecallAbsenceVerified"])
        self.assertFalse(us["pitchGate"]["domesticOfficialChecked"])
        self.assertFalse(us["pitchGate"]["exactComponentMatch"])
        self.assertFalse(us["pitchGate"]["sameAnglePriorPressChecked"])
        self.assertFalse(us["pitchGate"]["exclusiveConfirmed"])
        self.assertEqual(output["confirmedScoops"],0)
    def test_wrong_snapshot_or_forged_absence_is_rejected(self):
        n,d=sources()
        current=screen.scan(n,now=NOW,fetch=lambda u:(_ for _ in ()).throw(TimeoutError()))
        current["sourceUsSnapshot"]="wrong"
        result=gap.build(n,d,now=NOW,domestic_screen=current)
        self.assertEqual(result["items"][0]["domesticPublicScreen"]["status"],
                         "not_connected_or_snapshot_mismatch")
        current["sourceUsSnapshot"]=n["generatedAt"]
        current["items"][0]["domesticRecallAbsenceVerified"]=True
        result=gap.build(n,d,now=NOW,domestic_screen=current)
        self.assertEqual(result["items"][0]["domesticPublicScreen"]["status"],
                         "not_connected_or_snapshot_mismatch")
if __name__=="__main__":unittest.main()
