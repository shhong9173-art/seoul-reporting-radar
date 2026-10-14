import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ntis_validate_patent_discovery import validate,PROFILE

PUB="1020260145290"
APP="1020250039383"
PROJECT="2410019058"

def fixture():
    d={"generatedAt":"2026-10-14T19:00:00+09:00","dossiers":[
        {"publicationNumber":PUB,"title":"케이블 부착식 부분방전 센서 및 이를 포함하는 부분방전 검출 시스템"}]}
    deep={"generatedAt":"2026-10-13T14:18:23+09:00","investigations":[
        {"publicationNumber":PUB,"applicationNumber":APP,
         "applicants":["엘에스전선 주식회사","한빛이디에스(주)","홍길동"]}]}
    projects={"generatedAt":"2026-10-14T15:36:38+09:00",
              "dossierGeneratedAt":"2026-10-14T10:18:52+09:00",
              "checks":[{"status":"checked","records":[{"projectNumber":PROJECT}]}]}
    row={
        "publicationNumber":PUB,
        "patentApplicationNumber":APP,
        "patentPublicationNumber":None,
        "projectNumber":PROJECT,
        "sourceOfficialRecordId":"PTO-2026-0001",
        "sourceFieldMappingVerified":True,
        "registType":"출원","registTypeCode":"01",
        "registNumberRaw":"10-2025-0039383",
        "resultTitle":"부분방전 센서",
        "projectTitle":"전력설비 센서","performAgency":"한빛이디에스",
        "resultYear":"",
        "matchType":"official_application_and_project_id_in_same_hit",
        "sourceQueryMode":"technology",
    }
    ch={
        "publicationNumber":PUB,"applicationNumber":APP,
        "mode":"technology","query":"부분방전","status":"checked",
        "totalHits":3,"pagesChecked":1,"rowsExamined":3,
        "exactApplicationRows":1,
        "exactApplicationRowsWithProjectOutsidePriorSample":0,
        "registrationTypeRowsExcluded":1,
        "unrelatedApplicationRowsExcluded":1,
        "truncated":False,
    }
    payload={
        "generatedAt":"2026-10-14T20:00:00+09:00",
        "dossierGeneratedAt":d["generatedAt"],
        "kiprisDeepGeneratedAt":deep["generatedAt"],
        "ntisProjectsGeneratedAt":projects["generatedAt"],
        "ntisProjectDossierGeneratedAt":projects["dossierGeneratedAt"],
        "status":"ready",
        "mappingProfile":PROFILE,
        "collectionMethod":"approved_pc_rpatent_keyword_discovery",
        "targetCount":1,"plannedQueries":1,
        "completedQueries":1,"failedQueries":0,"pagesPerQueryMax":1,
        "totalSearchHitsAcrossQueries":3,"scannedOutcomeRows":3,
        "exactPatentAndPriorProjectNumberPairs":1,
        "verifiedDirectPatentProjectLinks":0,
        "commercializationConfirmed":0,
        "exclusiveConfirmed":0,
        "records":[row],"checks":[ch],
        "warning":"Keyword match is not a confirmed national R&D patent outcome.",
    }
    return payload,d,deep,projects

class DiscoveryValidatorTests(unittest.TestCase):
    def test_valid_number_pair_remains_review_not_confirmed(self):
        a,d,k,p=fixture()
        r=validate(a,d,k,p)
        self.assertEqual(r["exactAppProjectPairs"],1)
        self.assertFalse(r["snapshotAligned"])
        self.assertEqual(a["verifiedDirectPatentProjectLinks"],0)

    def test_no_results_is_not_a_project_nonexistence_claim(self):
        a,d,k,p=fixture()
        a["records"]=[];a["exactPatentAndPriorProjectNumberPairs"]=0
        a["checks"][0].update(totalHits=0,rowsExamined=0,exactApplicationRows=0,
                              unrelatedApplicationRowsExcluded=0,
                              registrationTypeRowsExcluded=0)
        a["scannedOutcomeRows"]=0;a["totalSearchHitsAcrossQueries"]=0
        self.assertEqual(validate(a,d,k,p)["exactAppProjectPairs"],0)

    def test_applicant_requires_corporate_kipris_applicant(self):
        a,d,k,p=fixture()
        a["checks"][0]["mode"]="applicant"
        a["checks"][0]["query"]="홍길동"
        a["records"][0]["sourceQueryMode"]="applicant"
        with self.assertRaisesRegex(ValueError,"query_not_grounded"):validate(a,d,k,p)
        a["checks"][0]["query"]="엘에스전선"
        self.assertEqual(validate(a,d,k,p)["exactAppProjectPairs"],1)

    def test_title_query_must_come_from_kipris_title(self):
        a,d,k,p=fixture()
        a["checks"][0]["mode"]="title"
        a["checks"][0]["query"]="케이블 부착식 부분방전 센서"
        a["records"][0]["sourceQueryMode"]="title"
        self.assertEqual(validate(a,d,k,p)["exactAppProjectPairs"],1)
        a["checks"][0]["query"]="근거없는 전고체 배터리 신기술"
        with self.assertRaisesRegex(ValueError,"query_not_grounded"):validate(a,d,k,p)

    def test_registered_number_can_never_be_promoted(self):
        a,d,k,p=fixture()
        a["records"][0]["registType"]="등록"
        a["records"][0]["registTypeCode"]="02"
        with self.assertRaisesRegex(ValueError,"registration_number"):validate(a,d,k,p)

    def test_application_must_match_same_hit(self):
        a,d,k,p=fixture()
        a["records"][0]["registNumberRaw"]="10-2020-0000012"
        with self.assertRaisesRegex(ValueError,"regist_number"):validate(a,d,k,p)

    def test_publication_cannot_be_substituted(self):
        a,d,k,p=fixture()
        a["records"][0]["patentPublicationNumber"]=PUB
        with self.assertRaisesRegex(ValueError,"publication_number"):validate(a,d,k,p)

    def test_project_outside_prior_sample_not_a_confirmed_match(self):
        a,d,k,p=fixture()
        a["records"][0]["projectNumber"]="1234567890"
        with self.assertRaisesRegex(ValueError,"project_not_in_prior"):validate(a,d,k,p)

    def test_wrong_snapshots_fail_closed(self):
        a,d,k,p=fixture()
        a["ntisProjectsGeneratedAt"]="2026-10-14T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"source_snapshot_mismatch"):validate(a,d,k,p)

    def test_errors_must_not_be_called_ready(self):
        a,d,k,p=fixture()
        a["checks"][0]={"publicationNumber":PUB,"applicationNumber":APP,
                        "mode":"technology","query":"부분방전","status":"source_error",
                        "errorClass":"NTIS_HTTP_403"}
        a["completedQueries"]=0;a["failedQueries"]=1
        a["totalSearchHitsAcrossQueries"]=0;a["scannedOutcomeRows"]=0
        a["records"]=[];a["exactPatentAndPriorProjectNumberPairs"]=0
        with self.assertRaisesRegex(ValueError,"false_success"):validate(a,d,k,p)

    def test_secrets_and_html_cannot_be_imported(self):
        a,d,k,p=fixture()
        a["warning"]="apprvKey=SECRET"
        with self.assertRaisesRegex(ValueError,"potential_api_key"):validate(a,d,k,p)
        a,d,k,p=fixture()
        a["records"][0]["resultTitle"]="<span>부분방전</span>"
        with self.assertRaisesRegex(ValueError,"unsafe_public"):validate(a,d,k,p)

    def test_partial_first_page_is_not_exhaustive(self):
        a,d,k,p=fixture()
        a["checks"][0]["totalHits"]=197
        a["checks"][0]["truncated"]=True
        a["totalSearchHitsAcrossQueries"]=197
        self.assertEqual(validate(a,d,k,p)["scannedRows"],3)
        a["checks"][0]["truncated"]=False
        with self.assertRaisesRegex(ValueError,"false_pagination"):validate(a,d,k,p)

    def test_duplicate_exact_hit_is_blocked(self):
        a,d,k,p=fixture()
        a["records"].append(copy.deepcopy(a["records"][0]))
        a["exactPatentAndPriorProjectNumberPairs"]=2
        with self.assertRaisesRegex(ValueError,"duplicate_exact"):validate(a,d,k,p)

if __name__=="__main__":
    unittest.main()
