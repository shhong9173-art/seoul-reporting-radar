import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ntis_validate_local_export import validate


def fixtures():
    pub="1020260148086"
    dossier={"status":"research_only","generatedAt":"2026-10-14T10:18:52+09:00",
             "dossiers":[{"publicationNumber":pub,"publicationDate":"2026-10-12",
                          "ntisResearchQueries":[{"query":"기아 고정자"}]}]}
    record={
        "projectNumber":"1234567890","projectTitle":"고정자 냉각 연구",
        "performingAgency":"기아","projectYear":"2025",
        "periodStart":"20250101","periodEnd":"20261231",
        "researchSummary":"개발연구","keyword":"전동기",
        "sourceSearchUrl":"https://www.ntis.go.kr/ThSearchProjectList.do?dbt=project&searchWord=1234567890",
        "researchLinkConfirmed":False,"patentOutcomeConfirmed":False,
        "companyProjectParticipationConfirmed":False,"commercializationConfirmed":False}
    row={
        "publicationNumber":pub,"publicationDate":"2026-10-12",
        "patentTitle":"고정자 냉각 장치","query":"기아 고정자",
        "checkedAt":"2026-10-14T14:30:00+09:00","status":"checked",
        "totalHits":1,"firstPageOnly":False,"records":[record],
        "sourceEndpointPath":"/rndopen/openApi/public_project"}
    export={
        "generatedAt":"2026-10-14T14:30:00+09:00",
        "dossierGeneratedAt":dossier["generatedAt"],"status":"ready",
        "source":"NTIS public_project OpenAPI - public project metadata",
        "requestProfile":"ntis_2025_pdf_page11_rest_example",
        "collectionMethod":"approved_pc_local_manual_review",
        "scope":"First search page of selected patent research queries only",
        "totalResearchQueries":1,"completedQueries":1,"failedQueries":0,
        "remainingQueries":0,"newQueriesThisRun":1,"sourceRecords":1,
        "projectPatentLinksConfirmed":0,"actualApplicationConfirmed":0,
        "checks":[row],
        "warning":"Keyword matches are not verified project/patent links, corporate participation, commercialization, or exclusives."}
    return dossier, export


class ValidatorTests(unittest.TestCase):
    def test_valid_public_record_passes_without_promoting_patent_link(self):
        dossier,export=fixtures()
        output=validate(export,dossier)
        self.assertEqual(output["projects"],1)
        self.assertEqual(export["projectPatentLinksConfirmed"],0)

    def test_reject_timestamp_mismatch(self):
        d,e=fixtures();e["dossierGeneratedAt"]="2026-10-14T00:00:00+09:00"
        with self.assertRaisesRegex(ValueError,"timestamp_mismatch"):validate(e,d)

    def test_reject_unknown_patent_or_query(self):
        d,e=fixtures();e["checks"][0]["query"]="임의 특허 관련"
        with self.assertRaisesRegex(ValueError,"query_does_not_match"):validate(e,d)

    def test_reject_credential_field(self):
        d,e=fixtures();e["checks"][0]["records"][0]["apprvKey"]="leak"
        with self.assertRaisesRegex(ValueError,"unexpected_public_project_fields"):validate(e,d)

    def test_reject_credential_in_title_or_warning(self):
        d,e=fixtures();e["warning"]="Do not expose apprvKey=test"
        with self.assertRaisesRegex(ValueError,"possible_credential"):validate(e,d)

    def test_reject_non_ntis_link(self):
        d,e=fixtures()
        e["checks"][0]["records"][0]["sourceSearchUrl"]="https://www.ntis.go.kr.evil.test/a?searchWord=1234567890"
        with self.assertRaisesRegex(ValueError,"non_ntis"):validate(e,d)

    def test_reject_unsupported_project_patent_identity_claim(self):
        d,e=fixtures();e["projectPatentLinksConfirmed"]=1
        with self.assertRaisesRegex(ValueError,"unsupported_project_patent"):validate(e,d)

    def test_reject_unsupported_result_claim(self):
        d,e=fixtures();e["checks"][0]["records"][0]["patentOutcomeConfirmed"]=True
        with self.assertRaisesRegex(ValueError,"unsupported_confirmation_flag"):validate(e,d)

    def test_reject_fake_zero_or_record_count(self):
        d,e=fixtures();e["sourceRecords"]=0
        with self.assertRaisesRegex(ValueError,"inconsistent_counts"):validate(e,d)

    def test_reject_success_with_hidden_failures(self):
        d,e=fixtures();e["remainingQueries"]=1
        with self.assertRaisesRegex(ValueError,"inconsistent_plan_count"):validate(e,d)
        e["totalResearchQueries"]=2
        with self.assertRaisesRegex(ValueError,"falsely_claimed_ready"):validate(e,d)


if __name__=="__main__":
    unittest.main()
