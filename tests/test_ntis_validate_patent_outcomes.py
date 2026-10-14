import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ntis_validate_patent_outcomes import validate, PROFILE

PUB="1020260145290"
APP="1020250039383"
PID="2410019058"

def fixtures():
    dossier={"generatedAt":"2026-10-14T16:00:58+09:00",
             "dossiers":[{"publicationNumber":PUB}]}
    deep={"generatedAt":"2026-10-13T14:18:23+09:00",
          "investigations":[{"publicationNumber":PUB,"applicationNumber":APP}]}
    projects={"generatedAt":"2026-10-14T15:36:38+09:00",
              "dossierGeneratedAt":"2026-10-14T10:18:52+09:00",
              "checks":[{"status":"checked","records":[{"projectNumber":PID,"projectTitle":"전력설비 감지 연구"}]}]}
    row={
        "publicationNumber":PUB,"patentApplicationNumber":APP,
        "patentPublicationNumber":None,"projectNumber":PID,
        "sourceOfficialRecordId":"PTO-2026-005",
        "sourceFieldMappingVerified":True,"registType":"출원",
        "registTypeCode":"01","registNumberRaw":"10-2025-0039383",
        "resultTitle":"케이블 부착식 부분방전 센서",
        "projectTitle":"전력설비 감지 연구",
        "performAgency":"한빛이디에스","resultYear":"2026"
    }
    export={
        "generatedAt":"2026-10-14T17:22:00+09:00",
        "dossierGeneratedAt":dossier["generatedAt"],
        "projectSourceGeneratedAt":projects["generatedAt"],
        "projectDossierGeneratedAt":projects["dossierGeneratedAt"],
        "kiprisDeepGeneratedAt":deep["generatedAt"],
        "status":"verified_official_patent_outcomes",
        "mappingProfile":PROFILE,
        "collectionMethod":"approved_pc_rpatent_official_manual",
        "targetCount":1,"completedTargets":1,"errorTargets":0,
        "matchingOutcomeRows":1,"sampleOutcomeRowsObserved":1,
        "projectNumbersInKeywordSnapshot":1,
        "records":[row],
        "checks":[{"publicationNumber":PUB,"applicationNumber":APP,"status":"checked",
                   "totalHits":1,"rowsObserved":1,
                   "exactApplicationRows":1,"numberProjectMatches":1}],
        "confirmedPatentProjectLinks":0,"commercializationConfirmed":0,
        "exclusiveConfirmed":0,"warning":"Number match is only a review lead."
    }
    return export,dossier,deep,projects

class OutcomeValidator(unittest.TestCase):
    def test_valid_typed_match_is_review_only(self):
        a,b,c,d=fixtures()
        r=validate(a,b,c,d)
        self.assertEqual(r["verified_number_pairs_for_manual_review"],1)
        self.assertTrue(r["project_snapshot_age_mismatch"])
        self.assertEqual(a["confirmedPatentProjectLinks"],0)

    def test_registered_not_application(self):
        a,b,c,d=fixtures()
        a["records"][0]["registType"]="등록"
        a["records"][0]["registTypeCode"]="02"
        with self.assertRaisesRegex(ValueError,"registered_patent"):validate(a,b,c,d)

    def test_registnumber_not_app(self):
        a,b,c,d=fixtures()
        a["records"][0]["registNumberRaw"]="10-2026-0145290"
        with self.assertRaisesRegex(ValueError,"ntis_number"):validate(a,b,c,d)

    def test_publication_is_never_NTIS_registnumber(self):
        a,b,c,d=fixtures()
        a["records"][0]["patentPublicationNumber"]=PUB
        with self.assertRaisesRegex(ValueError,"not_publication"):validate(a,b,c,d)

    def test_unknown_project_fails(self):
        a,b,c,d=fixtures()
        a["records"][0]["projectNumber"]="1111111111"
        with self.assertRaisesRegex(ValueError,"not_an_official_project"):validate(a,b,c,d)

    def test_wrong_KIPRIS_application_fails(self):
        a,b,c,d=fixtures()
        a["records"][0]["patentApplicationNumber"]=PUB
        with self.assertRaisesRegex(ValueError,"not_an_exact"):validate(a,b,c,d)

    def test_changed_snapshots_fail_closed(self):
        a,b,c,d=fixtures()
        b["generatedAt"]="2026-10-14T18:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"timestamps_changed"):validate(a,b,c,d)

    def test_flags_cannot_be_elevated(self):
        a,b,c,d=fixtures()
        a["confirmedPatentProjectLinks"]=1
        with self.assertRaisesRegex(ValueError,"unsupported_reporting_claim"):validate(a,b,c,d)

    def test_secret_value_in_json_refused(self):
        a,b,c,d=fixtures()
        a["warning"]="apprvKey=ABCD"
        with self.assertRaisesRegex(ValueError,"possible_credentials"):validate(a,b,c,d)

    def test_invalid_html_tag_in_title_refused(self):
        a,b,c,d=fixtures()
        a["records"][0]["resultTitle"]="<span>부분방전</span>"
        with self.assertRaisesRegex(ValueError,"unsafe_outcome_text"):validate(a,b,c,d)

    def test_false_success_with_error_query_refused(self):
        a,b,c,d=fixtures()
        a["checks"][0]["status"]="source_error"
        a["checks"][0]["errorClass"]="OUTCOME_HTTP_403"
        a["completedTargets"]=0;a["errorTargets"]=1
        with self.assertRaisesRegex(ValueError,"false_full_success"):validate(a,b,c,d)

    def test_duplicate_result_refused(self):
        a,b,c,d=fixtures()
        a["records"].append(copy.deepcopy(a["records"][0]))
        a["matchingOutcomeRows"]=2
        with self.assertRaisesRegex(ValueError,"duplicate_outcome"):validate(a,b,c,d)

if __name__=="__main__":unittest.main()
