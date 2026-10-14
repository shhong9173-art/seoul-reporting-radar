import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ntis_outcome_reconcile as x

NOW=datetime(2026,10,14,19,0,tzinfo=timezone(timedelta(hours=9)))
PUB="1020260145290"
APP="1020250039383"
PROJECT="2410019058"

def fixtures():
    dossier={"status":"research_only","generatedAt":"2026-10-14T10:18:52+09:00",
             "dossiers":[{"publicationNumber":PUB,"title":"케이블 부착식 부분방전 센서","publicationDate":"2026-10-07"}]}
    deep={"generatedAt":"2026-10-13T14:18:23+09:00",
          "investigations":[{"publicationNumber":PUB,"applicationNumber":APP},
                            {"publicationNumber":"1020260123000","applicationNumber":"1020250031234"}]}
    projects={"generatedAt":"2026-10-14T15:36:38+09:00",
              "dossierGeneratedAt":dossier["generatedAt"],
              "projectPatentLinksConfirmed":0,
              "checks":[{"status":"checked","records":[{"projectNumber":PROJECT,
                    "projectTitle":"AI 기반 전력설비 화재 예방 스파크 사전 감지 센서 시스템",
                    "performingAgency":"한빛이디에스","projectYear":"2026"}]}]}
    outcomes={"generatedAt":"2026-10-14T18:50:00+09:00",
              "status":"verified_official_patent_outcomes",
              "mappingProfile":x.OUTCOME_PROFILE,
              "projectSourceGeneratedAt":projects["generatedAt"],
              "records":[{"projectNumber":PROJECT,
                          "patentApplicationNumber":"10-2025-0039383",
                          "patentPublicationNumber":None,
                          "sourceOfficialRecordId":"NTIS-PTO-2026-123",
                          "sourceFieldMappingVerified":True}]}
    return dossier,deep,projects,outcomes


class OutcomeAuditTests(unittest.TestCase):
    def test_missing_outcome_schema_always_zero_confirmed(self):
        d,k,p,o=fixtures()
        r=x.build(d,k,p,None,now=NOW)
        self.assertEqual(r["status"],"missing_official_patent_outcome_schema")
        self.assertEqual(r["confirmedPatentProjectLinks"],0)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],0)
        self.assertEqual(r["patentsWithOfficialKiprisApplicationNumbers"],1)

    def test_same_project_and_application_number_creates_review_only_lead(self):
        d,k,p,o=fixtures()
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],1)
        hit=r["reviewOnlyMatches"][0]
        self.assertEqual(hit["projectNumber"],PROJECT)
        self.assertEqual(hit["identityEvidence"],["application_number_exact"])
        self.assertFalse(hit["samePatentAndProjectConfirmedForPublication"])
        self.assertFalse(hit["outcomeManuallyVerified"])
        self.assertEqual(r["confirmedPatentProjectLinks"],0)

    def test_number_spaces_and_hyphens_normalize_only_same_kind(self):
        self.assertEqual(x.number("10-2025-0039383"),APP)
        self.assertEqual(x.number("10-2026-0145290"),PUB)
        self.assertIsNone(x.number("10-2423733"))  # Registration: not 13 digits.
        d,k,p,o=fixtures()
        o["records"][0]["patentApplicationNumber"]=PUB  # publication cannot be substituted!
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],0)

    def test_publication_exact_match_is_a_separate_namespace(self):
        d,k,p,o=fixtures()
        o["records"][0]["patentApplicationNumber"]=None
        o["records"][0]["patentPublicationNumber"]="10-2026-0145290"
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["reviewOnlyMatches"][0]["identityEvidence"],["publication_number_exact"])

    def test_title_and_company_keyword_only_is_not_direct_outcome_match(self):
        d,k,p,o=fixtures()
        o["records"][0]["patentApplicationNumber"]=None
        o["records"][0]["patentPublicationNumber"]=None
        o["records"][0]["title"]="케이블 부착식 부분방전 센서"
        o["records"][0]["agency"]="한빛이디에스"
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],0)

    def test_missing_project_in_pc_export_blocks_link(self):
        d,k,p,o=fixtures()
        o["records"][0]["projectNumber"]="1234567890"
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],0)

    def test_stale_project_snapshot_blocks_link(self):
        d,k,p,o=fixtures()
        p["dossierGeneratedAt"]="2026-10-14T15:50:00+09:00"
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["status"],"source_snapshot_mismatch")
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],0)

    def test_uncorroborated_schema_and_record_block_link(self):
        d,k,p,o=fixtures()
        o["mappingProfile"]="unknown_fields_assumed"
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["status"],"outcome_schema_or_authorization_unverified")
        self.assertEqual(r["confirmedPatentProjectLinks"],0)
        o["mappingProfile"]=x.OUTCOME_PROFILE
        o["records"][0]["sourceFieldMappingVerified"]=False
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],0)

    def test_fresh_dossier_missing_kipris_application_number_is_not_filled_by_guess(self):
        d,k,p,o=fixtures()
        k["investigations"]=[]
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["patentsWithOfficialKiprisApplicationNumbers"],0)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],0)

    def test_duplicate_outcomes_deduplicated_but_not_confirmed(self):
        d,k,p,o=fixtures()
        o["records"].append(dict(o["records"][0]))
        r=x.build(d,k,p,o,now=NOW)
        self.assertEqual(r["potentialExactNumberPairsNeedingHumanReview"],1)
        self.assertEqual(r["confirmedPatentProjectLinks"],0)


if __name__=="__main__":
    unittest.main()
