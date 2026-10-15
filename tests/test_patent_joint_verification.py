import copy
import sys
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_joint_verification as v
KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,15,11,0,tzinfo=KST)
def sources():
    stamp="2026-10-15T10:30:00+09:00"
    official=dict(status="official_search_completed",sourceWindowComplete=True,generatedAt=stamp)
    lead=dict(publicationNumber="1020260149999",applicationNumber="1020250039383",
        publicationDate="20261014",title="폐차 플라스틱 효소 재활용 방법",
        applicants=["현대자동차주식회사","기아 주식회사","씨제이제일제당 주식회사"],
        coveredCompanies=["현대자동차","기아"],
        outsideBeatCoApplicants=["씨제이제일제당 주식회사"],
        crossOrganizationLead=True,jointApplicantGroup=True,previouslyObserved=False,
        priorFullTitleCheck=dict(complete=True,matches=[],status="동일 제목 공보 미확인"))
    past=copy.deepcopy(lead)
    past["publicationNumber"]="1020260149998"
    past["publicationDate"]="20261010"
    deep=dict(generatedAt=stamp,patentDatasetGeneratedAt=stamp,
        sourceCoverageComplete=True,confirmedScoops=0,
        outsideBeatJointPublications=2,partnerInvestigations=[lead,past])
    story=dict(generatedAt=stamp,officialSourceGeneratedAt=stamp,
        deepSourceGeneratedAt=stamp,investigations=[
          dict(publicationNumber=lead["publicationNumber"],publicationDate=lead["publicationDate"],
            title=lead["title"],pressCheckedAt=stamp,
            pressCoverage=dict(completeSearch=True,possibleEarlierCoverage=False,
              queries=[dict(query='"1020260149999"',status="no_hits",articles=[])]))])
    claims=dict(generatedAt=stamp,patentDatasetGeneratedAt=stamp,
        deepDatasetGeneratedAt=stamp,confirmedScoops=0,reviews=[
          dict(publicationNumber=lead["publicationNumber"],
            currentApplication=lead["applicationNumber"],claimVerified=True,
            claimSourceVerified=True,claim1Excerpt="가상의 청구항 1",priorComparisons=[])])
    return [official,deep,story,claims]
class JointVerification(unittest.TestCase):
    def test_recent_three_days_and_old_separate_with_coverage(self):
        r=v.build(*sources(),now=NOW)
        self.assertEqual(r["windowStart"],"20261013")
        self.assertEqual(r["recentJointInRepresentedSample"],1)
        self.assertTrue(r["recentCoverageComplete"])
        self.assertEqual(len(r["olderReferenceQueue"]),1)
        lead=r["recentResearchQueue"][0]
        self.assertEqual(lead["claim1Status"],"official_claim1_verified_text_only_no_novelty_certification")
        self.assertEqual(lead["pressIndexStatus"],"index_no_hits_not_proof_unreported")
        self.assertFalse(lead["scoopConfirmed"])
        self.assertFalse(lead["companyApplicationVerified"])
        self.assertFalse(lead["approvedForPitch"])
    def test_not_surveyed_joint_patents_not_zero(self):
        a=sources()
        a[1]["outsideBeatJointPublications"]=8
        r=v.build(*a,now=NOW)
        self.assertEqual(r["unrepresentedOfficialJointRecords"],6)
        self.assertFalse(r["recentCoverageComplete"])
    def test_stale_source_must_not_be_current_zero(self):
        a=sources()
        old="2026-10-13T10:00:00+09:00"
        a[0]["generatedAt"]=old
        a[1]["patentDatasetGeneratedAt"]=old
        a[2]["officialSourceGeneratedAt"]=old
        a[3]["patentDatasetGeneratedAt"]=old
        r=v.build(*a,now=NOW)
        self.assertTrue(r["officialSourceStale"])
        self.assertEqual(r["status"],"historical_source_stale_recollect_before_current_pitch")
        self.assertFalse(r["recentCoverageComplete"])
    def test_bad_claim_application_must_fail(self):
        a=sources()
        a[3]["reviews"][0]["currentApplication"]="1020250011111"
        with self.assertRaisesRegex(ValueError,"claim_of_different_application"):
            v.build(*a,now=NOW)
    def test_unchecked_media_not_index_no_hits(self):
        a=sources()
        del a[2]["investigations"][0]["pressCheckedAt"]
        r=v.build(*a,now=NOW)
        self.assertEqual(r["recentResearchQueue"][0]["pressIndexStatus"],"not_searched_no_zero_claim")
    def test_repeated_publication_is_a_source_error(self):
        a=sources()
        a[1]["outsideBeatJointPublications"]=3
        a[1]["partnerInvestigations"].append(copy.deepcopy(a[1]["partnerInvestigations"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_cofiled_publication"):
            v.build(*a,now=NOW)
    def test_no_unauthorized_partner(self):
        a=sources()
        a[1]["partnerInvestigations"][0]["outsideBeatCoApplicants"]=["출원인에 없는 업체"]
        with self.assertRaisesRegex(ValueError,"unproven_partner_identity"):
            v.build(*a,now=NOW)
    def test_future_publication_rejected(self):
        a=sources()
        a[1]["partnerInvestigations"][0]["publicationDate"]="20261016"
        with self.assertRaisesRegex(ValueError,"future_official_publication"):
            v.build(*a,now=NOW)
    def test_replayed_known_publication_not_fresh_exclusive(self):
        a=sources()
        a[1]["partnerInvestigations"][0]["previouslyObserved"]=True
        r=v.build(*a,now=NOW)
        self.assertTrue(r["recentResearchQueue"][0]["observedInCurrentSource"])
        self.assertEqual(r["confirmedScoops"],0)
    def test_inconsistent_snapshot_fails_closed(self):
        a=sources()
        a[2]["deepSourceGeneratedAt"]="2026-10-14T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"official_patent_snapshot_inconsistent"):
            v.build(*a,now=NOW)
if __name__=="__main__":unittest.main()
