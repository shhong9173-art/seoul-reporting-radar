import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from ntis_project_field_control_validate import validate,MODES

def fixture():
    modes=[]
    for name in MODES:
        present=name in ("project_bi","project_unscoped","ti03_seed")
        n=1 if present else 0
        modes.append({
            "mode":name,"status":"checked","totalHits":n,
            "rowsInspected":n,"exactReferenceProjectRows":n,
            "exactReferenceOutcomeRows":n,
            "additionalPagesNotChecked":False,"errorClass":None,
        })
    return {
        "generatedAt":"2026-10-15T10:40:00+09:00",
        "profile":"ntis_rpatent_project_id_index_control_v1",
        "collectionMethod":"approved_pc_official_rpatent_field_control",
        "status":"some_project_search_paths_work",
        "controlSeedTerm":"부분방전","controlSeedTotalHits":197,
        "controlSeedRowsInspected":2,
        "officialReferenceProjectAndOutcomeSeenInSeed":True,
        "controlProjectIdExported":False,"controlResultIdExported":False,
        "plannedAdditionalControlQueries":5,
        "completedAdditionalControlQueries":5,
        "failedAdditionalControlQueries":0,
        "exactReferenceOutcomeRecoveredInAnyMode":True,
        "searchModes":modes,
        "verifiedPatentProjectOutcomeLinks":0,
        "commercializationConfirmed":0,
        "exclusiveConfirmed":0,
        "warning":"The seed from an official rpatent HIT was retrievable through BI in a synthetic test; no real project-outcome linkage.",
    }

class ProbeTests(unittest.TestCase):
    def test_healthy_control_reports_paths_separately(self):
        data=fixture()
        out=validate(data)
        self.assertEqual(out["retrievedReferencePaths"],3)
        self.assertEqual(out["baselineHits"],197)
        self.assertEqual(data["searchModes"][0]["totalHits"],0)

    def test_all_zero_project_id_queries_are_not_classified_as_absent_patents(self):
        data=fixture()
        for case in data["searchModes"]:
            case["totalHits"]=0;case["rowsInspected"]=0
            case["exactReferenceProjectRows"]=0;case["exactReferenceOutcomeRows"]=0
        data["status"]="project_id_retrieval_not_verified"
        data["exactReferenceOutcomeRecoveredInAnyMode"]=False
        self.assertEqual(validate(data)["retrievedReferencePaths"],0)

    def test_project_control_must_come_from_official_hit(self):
        data=fixture()
        data["officialReferenceProjectAndOutcomeSeenInSeed"]=False
        with self.assertRaisesRegex(ValueError,"no_reference"):
            validate(data)

    def test_invalid_positive_reference_is_clearly_unavailable(self):
        data=fixture()
        data["status"]="control_unavailable"
        data["officialReferenceProjectAndOutcomeSeenInSeed"]=False
        data["searchModes"]=[];data["completedAdditionalControlQueries"]=0
        data["exactReferenceOutcomeRecoveredInAnyMode"]=False
        self.assertEqual(validate(data)["status"],"control_unavailable")

    def test_totalhits_positive_without_same_reference_is_not_conclusive(self):
        data=fixture()
        for c in data["searchModes"]:
            c["exactReferenceOutcomeRows"]=0
        data["status"]="project_id_retrieval_not_verified"
        data["exactReferenceOutcomeRecoveredInAnyMode"]=False
        self.assertEqual(validate(data)["retrievedReferencePaths"],0)

    def test_impossible_reference_match_without_scanned_row_fails(self):
        data=fixture()
        data["searchModes"][0]["exactReferenceOutcomeRows"]=1
        with self.assertRaisesRegex(ValueError,"impossible_project"):
            validate(data)

    def test_no_unrelated_full_project_identifier_leaked(self):
        data=fixture()
        data["warning"]+=" 1415076898"
        with self.assertRaisesRegex(ValueError,"unrelated_project_identifier_leaked"):
            validate(data)

    def test_no_unrelated_result_id_exported(self):
        data=fixture()
        data["ResultID"]="CONTROL12345"
        with self.assertRaisesRegex(ValueError,"unexpected_index_control_output"):
            validate(data)

    def test_no_private_key_in_export(self):
        data=fixture()
        data["warning"]="apprvKey=ANY_VALUE"
        with self.assertRaisesRegex(ValueError,"possible_ntis_secret_export"):
            validate(data)

    def test_no_claim_of_confirmed_outcome_or_scoop(self):
        data=fixture()
        data["verifiedPatentProjectOutcomeLinks"]=1
        with self.assertRaisesRegex(ValueError,"unauthorized_patent"):
            validate(data)

    def test_error_not_silently_called_success(self):
        data=fixture()
        check=data["searchModes"][-1]
        check.update(status="source_error",totalHits=None,rowsInspected=0,
                     exactReferenceProjectRows=0,exactReferenceOutcomeRows=0,
                     additionalPagesNotChecked=True,errorClass="NTIS_HTTP_403")
        data["completedAdditionalControlQueries"]=4
        data["failedAdditionalControlQueries"]=1
        with self.assertRaisesRegex(ValueError,"source_errors_are_not_success"):
            validate(data)
        data["status"]="partial_errors"
        self.assertEqual(validate(data)["errors"],1)

    def test_partial_pages_cannot_be_mislabeled_exhaustive(self):
        data=fixture()
        check=data["searchModes"][1]
        check["totalHits"]=197
        with self.assertRaisesRegex(ValueError,"wrong_pagination"):
            validate(data)

if __name__=="__main__":unittest.main()
