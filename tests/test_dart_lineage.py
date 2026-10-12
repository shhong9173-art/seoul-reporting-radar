"""Origin receipt linkage is opt-in to evidence, never infer from issuer+date."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import dart_lineage as lineage
import review_engine as review

ORIGINAL="20260901000321"
AMENDED="20261012000123"
COMPANY="현대제철"
CODE="00145880"


def html_document(amount, counterparty="주식회사 A", reference=False, date=False):
    head=("<p>원공시 접수번호 : "+ORIGINAL+"</p>" if reference else "")
    head+=("<table><tr><td>최초제출일</td><td>2026-09-01</td></tr></table>"
           if date else "")
    return (head+"<table>"
            "<tr><td>계약상대방</td><td>"+counterparty+"</td></tr>"
            "<tr><td>계약금액(원)</td><td>"+amount+"</td></tr>"
            "<tr><td>계약종료일</td><td>2028-12-31</td></tr>"
            "</table>")


class LineageTests(unittest.TestCase):
    def row(self, report="[기재정정]단일판매ㆍ공급계약체결"):
        return {"receiptNo": AMENDED,"company": COMPANY,"report": report,
                "published":"20261012","tag":"★수주"}

    def listing(self, apikey,corp,date):
        self.assertEqual(corp,CODE)
        self.assertEqual(date,"20260901")
        return [{"rcept_no":ORIGINAL,"corp_code":CODE,"report_nm":"단일판매ㆍ공급계약체결",
                 "rcept_dt":"20260901"}]

    def orig(self, apikey,receipt):
        if receipt==AMENDED:
            return [html_document("1,500,000",reference=True)]
        if receipt==ORIGINAL:
            return [html_document("1,000,000")]
        self.fail("unexpected receipt")

    def test_verified_explicit_receipt_and_original_documents(self):
        out=lineage.review_lineage(self.row(),{COMPANY:{"corp_code":CODE}},
                                  api_key="fake",fetch_documents=self.orig,fetch_list=self.listing)
        self.assertTrue(out["originalDocumentVerified"])
        self.assertEqual(out["originReceiptNo"],ORIGINAL)
        self.assertEqual(out["status"],"original_verified_changes")
        self.assertEqual(out["changes"][0]["before"],"1,000,000")
        self.assertEqual(out["changes"][0]["after"],"1,500,000")
        self.assertIsNone(out["changes"][0]["numericDelta"])

    def test_same_day_and_type_do_not_authorize_link_without_reference(self):
        def docs(key,receipt):
            self.assertEqual(receipt, AMENDED)
            return [html_document("1,500,000",date=True)]
        out=lineage.review_lineage(self.row(),{COMPANY:{"corp_code":CODE}},
                                  api_key="fake",fetch_documents=docs,fetch_list=self.listing)
        self.assertFalse(out["originalDocumentVerified"])
        self.assertIsNone(out["originReceiptNo"])
        self.assertEqual(out["candidateOrigins"][0]["receiptNo"],ORIGINAL)
        self.assertEqual(out["status"],"original_unverified")

    def test_wrong_issuer_reference_stays_unverified(self):
        def listing(key,corp,date):
            return [{"rcept_no":ORIGINAL,"corp_code":"00000001","report_nm":"단일판매ㆍ공급계약체결"}]
        out=lineage.review_lineage(self.row(),{COMPANY:{"corp_code":CODE}},
                                  api_key="fake",fetch_documents=self.orig,fetch_list=listing)
        self.assertFalse(out["originalDocumentVerified"])

    def test_different_contract_counterparty_hard_stops(self):
        def docs(key,receipt):
            return [html_document("1,500,000",counterparty="주식회사 B",reference=True)] if receipt==AMENDED else [html_document("1,000,000")]
        out=lineage.review_lineage(self.row(),{COMPANY:{"corp_code":CODE}},
                                  api_key="fake",fetch_documents=docs,fetch_list=self.listing)
        self.assertEqual(out["status"],"identity_mismatch")
        self.assertFalse(out["originalDocumentVerified"])
        self.assertEqual(out["changes"],[])

    def test_ambiguous_explicit_origins_not_guessed(self):
        text="원공시 접수번호 "+ORIGINAL+" 원공시 접수번호 20260802000110"
        out=lineage.explicit_origin_id([text],AMENDED)
        self.assertEqual(out["status"],"ambiguous_explicit_references")

    def test_default_issuer_lookup_reads_official_list_without_required_callback(self):
        payload={"status":"000","total_page":1,
                 "list":[{"rcept_no":ORIGINAL,"corp_code":CODE,
                          "report_nm":"단일판매ㆍ공급계약체결"}]}
        with patch.object(lineage,"urlopen",return_value=io.BytesIO(
                json.dumps(payload).encode("utf-8"))) as mocked:
            items=lineage.issuer_list("fake",CODE,"20260901")
        self.assertEqual(items[0]["rcept_no"],ORIGINAL)
        self.assertEqual(mocked.call_count,1)

    def test_live_default_list_adapter_allows_verified_amendment(self):
        payload={"status":"000","total_page":1,
                 "list":[{"rcept_no":ORIGINAL,"corp_code":CODE,
                          "report_nm":"단일판매ㆍ공급계약체결"}]}
        with patch.object(lineage,"urlopen",return_value=io.BytesIO(
                json.dumps(payload).encode("utf-8"))):
            out=lineage.review_lineage(
                self.row(),{COMPANY:{"corp_code":CODE}},api_key="fake",
                fetch_documents=self.orig)
        self.assertTrue(out["originalDocumentVerified"])
        self.assertEqual(out["status"],"original_verified_changes")
        self.assertEqual(out["changes"][0]["before"],"1,000,000")

    def test_no_key_does_not_invoke_network(self):
        def never(*a,**kw):
            self.fail("must not make network requests")
        out=lineage.review_lineage(self.row(),{COMPANY:{"corp_code":CODE}},
                                   api_key="",fetch_documents=never,fetch_list=never)
        self.assertEqual(out["status"],"original_unverified")
        self.assertIn("API_KEY",out["reason"])

    def test_original_missing_field_never_computes_a_delta(self):
        old={"counterparty":"A"}
        new={"counterparty":"A","contract_amount":"9,999"}
        self.assertEqual(lineage.comparable_differences(old,new),[])

    def test_duplicate_field_conflict_discarded(self):
        html=("<table><tr><td>계약금액(원)</td><td>100</td></tr>"
              "<tr><td>계약금액(원)</td><td>500</td></tr></table>")
        self.assertNotIn("contract_amount",lineage.tabular_fields([html]))

    def test_original_correction_must_be_same_report_category(self):
        def listing(k,c,d):
            return [{"rcept_no":ORIGINAL,"corp_code":CODE,"report_nm":"생산중단"}]
        out=lineage.review_lineage(self.row(),{COMPANY:{"corp_code":CODE}},
                                   api_key="fake",fetch_documents=self.orig,fetch_list=listing)
        self.assertFalse(out["originalDocumentVerified"])

    def test_daily_coverage_limited_and_explicit(self):
        digest={"generatedAt":"2026-10-12T23:55:00+09:00",
                "items":[self.row(),{**self.row(),"receiptNo":"20261012000124"}]}
        output=lineage.build_lineage(digest,{COMPANY:{"corp_code":CODE}},"",
                                     fetch_documents=lambda *a:self.fail("network"),
                                     limit=1)
        self.assertEqual(output["correctionCount"],2)
        self.assertEqual(output["processedCount"],1)
        self.assertFalse(output["collectionComplete"])

    def test_review_engine_does_not_consume_stale_lineage(self):
        digest={"generatedAt":"new","items":[self.row()]}
        lineage_data={"digestGeneratedAt":"old","items":[{
            "receiptNo":AMENDED,"company":COMPANY,"originalDocumentVerified":True,
            "changes":[{"field":"contract_amount","before":"1","after":"2"}],
            "originReceiptNo":ORIGINAL
        }]}
        result=review.build_review(digest,{"items":[]},lineage=lineage_data)
        self.assertEqual(result["items"][0]["lane"],"원문·변경 사실 확인")
        self.assertFalse(result["items"][0]["originalDocumentVerified"])

    def test_direct_cli_invocation_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            digest_path = root/"digest.json"
            output = root/"lineage.json"
            digest_path.write_text(
                json.dumps({"generatedAt":"2026-10-13T00:00:00+09:00",
                            "items":[self.row()]}), encoding="utf-8")
            env = dict(os.environ, DART_API_KEY="")
            done = subprocess.run([
                sys.executable,
                str(Path(__file__).resolve().parents[1]/"scripts"/"dart_lineage.py"),
                "--digest",str(digest_path),
                "--corp-codes",str(root/"absent.json"),
                "--output",str(output),
            ],cwd=directory,env=env,capture_output=True,text=True,timeout=20)
            self.assertEqual(done.returncode,0,done.stderr)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["processedCount"],1)
            self.assertEqual(result["items"][0]["status"],"original_unverified")

    def test_review_shows_verified_but_does_not_promote_to_exclusive(self):
        row=self.row()
        digest={"generatedAt":"now","items":[row]}
        line={"digestGeneratedAt":"now","items":[{
            "receiptNo":AMENDED,"company":COMPANY,"originalDocumentVerified":True,
            "changes":[{"field":"contract_amount","before":"100","after":"150"}],
            "originReceiptNo":ORIGINAL,
            "originSourceUrl":lineage.source_link(ORIGINAL)
        }]}
        result=review.build_review(digest,{"items":[]},lineage=line)
        item=result["items"][0]
        self.assertEqual(item["lane"],"원공시 독립 대조 확인")
        self.assertTrue(item["originalDocumentVerified"])
        self.assertIn("판정 보류",item["exclusiveStatus"])


if __name__=="__main__":
    unittest.main()
