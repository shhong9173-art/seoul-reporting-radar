"""Regression for complete beat coverage, bounded DART paging and exact change proofs."""
import io
import json
import sys
import unittest
import zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import parse_qs,urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dart_beat_monitor as m
import dart_corp_registry as registry

NOW=datetime(2026,10,15,18,0,tzinfo=timezone(timedelta(hours=9)))

def item(name,code,receipt,kind="단일판매ㆍ공급계약체결"):
    return {"company":name,"beat":m.TARGETS[name],"corpCode":code,
        "receiptNo":receipt,"published":receipt[:8],"report":kind,
        "category":m.interesting(kind),"isCorrection":"정정" in kind,
        "sourceUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt,
        "sourceType":"official_list_receipt","scoopConfirmed":False}
def fake_list(key,company,code,start,end):
    return {"records":[item(company,code,"20261014800222")] if company=="현대자동차" else [],
            "pagesRead":1,"status":"checked","complete":True,"totalOfficialFilings":1}
def fake_detail(row,key):
    return {**row,"status":"official_document_read",
            "observedFields":{"contract_amount":"100,000,000"},
            "observedFieldEvidence":{"contract_amount":{"basis":"same_official_table_row"}},
            "scoopConfirmed":False}
def sparse_codes():
    return {"현대자동차":{"corp_code":"00164742"},
            "KG스틸":{"corp_code":"00112233"}}

class BeatCoverageTests(unittest.TestCase):
    def test_issuer_scope_contains_all_five_beats_and_missing_visible(self):
        self.assertGreaterEqual(len(m.TARGETS),45)
        for expected in ("현대자동차","KG스틸","LS전선","HD현대일렉트릭",
                         "고려아연","영풍","한국GM","르노코리아","GS칼텍스"):
            self.assertIn(expected,m.TARGETS)
        d=m.collect(sparse_codes(),"key",now=NOW,query=fake_list,detail=fake_detail)
        self.assertEqual(d["scopeCompanyCount"],len(m.TARGETS))
        self.assertEqual(d["companiesCodeVerified"],2)
        self.assertEqual(d["companiesUnresolved"],len(m.TARGETS)-2)
        self.assertFalse(d["sourceComplete"])
        self.assertTrue(any(c["status"]=="corp_code_unavailable" for c in d["sourceChecks"]))
        self.assertTrue(d["firstRunBaseline"])
        self.assertEqual(d["detailsAttempted"],1)
        signals=m.change_review(d,now=NOW)
        self.assertTrue(signals["baselineOnly"])
        self.assertEqual(signals["confirmedScoops"],0)
        self.assertIsNone(signals["signals"][0]["newObservation"])

    def test_public_list_pagination_works_without_fabricating_zero(self):
        called=[]
        def fetch(uri):
            q=parse_qs(urlsplit(uri).query)
            called.append(int(q["page_no"][0]))
            num=called[-1]
            return {"status":"000","total_page":2,"total_count":2,"list":[
              {"corp_code":"00164742","rcept_no":f"2026101{num}800111",
               "rcept_dt":f"2026101{num}","report_nm":"단일판매ㆍ공급계약체결"}
            ]}
        result=m.fetch_official_list("key","현대자동차","00164742",
                                    "20261001","20261015",get=fetch)
        self.assertEqual(called,[1,2])
        self.assertTrue(result["complete"])
        self.assertEqual(len(result["records"]),2)
        self.assertEqual(result["pagesRead"],2)

    def test_over_max_page_fails_closed_and_cannot_report_zero(self):
        def fetch(_):
            return {"status":"000","total_page":4,"total_count":401,"list":[]}
        result=m.fetch_official_list("key","현대자동차","00164742",
                                    "20261001","20261015",get=fetch)
        self.assertFalse(result["complete"])
        self.assertEqual(result["status"],"pagination_over_bound")
        self.assertEqual(result["totalOfficialFilings"],401)

    def test_provider_error_and_checked_zero_differ(self):
        def err(*a):
            raise RuntimeError("provider timeout")
        d=m.collect(sparse_codes(),"key",now=NOW,query=err,detail=fake_detail)
        self.assertEqual(d["companiesWithSourceErrors"],2)
        self.assertFalse(d["sourceComplete"])
        self.assertEqual(d["relevantFilings"],0)
        self.assertEqual(d["sourceChecks"][0]["status"],"source_error")
        def zero(*a):
            return {"records":[],"pagesRead":1,"complete":True,
                    "status":"checked_no_filings","totalOfficialFilings":0}
        z=m.collect(sparse_codes(),"key",now=NOW,query=zero,detail=fake_detail)
        self.assertEqual(z["companiesCodeVerified"],2)
        self.assertEqual(z["relevantFilings"],0)
        self.assertEqual(z["sourceChecks"][0]["status"],"checked")

    def test_first_seen_is_not_media_first_report_or_exclusivity(self):
        prev=m.collect(sparse_codes(),"key",now=NOW,query=fake_list,detail=fake_detail)
        fresh=m.collect(sparse_codes(),"key",now=NOW+timedelta(hours=2),
                        query=fake_list,detail=fake_detail,previous=prev)
        self.assertFalse(fresh["firstRunBaseline"])
        self.assertFalse(fresh["records"][0]["firstObservedThisRun"])
        self.assertEqual(fresh["detailsAttempted"],0)
        signals=m.change_review(fresh,previous=prev,now=NOW+timedelta(hours=2))
        self.assertEqual(signals["observedSignals"],0)

    def test_second_poll_drains_uninspected_old_receipts_without_false_company_change(self):
        ids={"현대자동차":"20261015800221","KG스틸":"20261014800222"}
        calls=[]
        def records(key,name,code,start,end):
            return {"records":[item(name,code,ids[name])],
                    "complete":True,"pagesRead":1,"totalOfficialFilings":1}
        def capture(row,key):
            calls.append(row["receiptNo"])
            return fake_detail(row,key)
        first=m.collect(sparse_codes(),"key",now=NOW,query=records,detail=capture,limit=1)
        self.assertEqual(first["detailsAttempted"],1)
        self.assertEqual(first["uninspectedRelevantDetails"],1)
        self.assertEqual(first["detailNotAttemptedThisRun"],1)
        second=m.collect(sparse_codes(),"key",now=NOW+timedelta(hours=1),
                         previous=first,query=records,detail=capture,limit=1)
        self.assertEqual(second["detailsAttempted"],1)
        self.assertEqual(second["uninspectedRelevantDetails"],0)
        self.assertEqual(len(calls),2)
        self.assertNotEqual(calls[0],calls[1])
        changes=m.change_review(second,first,now=NOW+timedelta(hours=1))
        self.assertEqual(changes["observedSignals"],1)
        self.assertEqual(changes["signals"][0]["status"],
                         "same_receipt_first_document_field_recovery")
        self.assertFalse(changes["signals"][0]["businessImpactVerified"])
        self.assertFalse(changes["signals"][0]["scoopConfirmed"])

    def test_retry_correction_source_error_instead_of_caching_failed_document_forever(self):
        code="00164742"
        record=item("현대자동차",code,"20261015800227",
                    "[기재정정]단일판매ㆍ공급계약체결")
        def records(key,name,corp,start,end):
            return {"records":[record] if name=="현대자동차" else [],
                    "complete":True,"pagesRead":1,"totalOfficialFilings":1}
        calls=[]
        def details(row,key):
            calls.append(row["receiptNo"])
            return {**row,"status":"original_not_verified",
                    "sourceError":len(calls)==1,
                    "issuerCorrectionTable":{"status":"not_examined","changes":[]}}
        prev=m.collect(sparse_codes(),"key",now=NOW,query=records,detail=details,limit=1)
        second=m.collect(sparse_codes(),"key",now=NOW+timedelta(hours=1),
                         query=records,detail=details,previous=prev,limit=1)
        self.assertEqual(len(calls),2)
        self.assertEqual(second["detailsAttempted"],1)
        self.assertFalse(second["records"][0]["sourceError"])

    def test_public_filed_issuer_terms_are_visible_but_affiliate_not_independent_award(self):
        proof=lambda label:{"basis":"same_official_table_row",
                            "sourceLabel":label,
                            "rowPattern":"two_cell_explicit_label",
                            "independentBusinessVerification":False}
        row=item("현대자동차","00164742","20261015800221")
        row.update(status="official_document_read",
                   observedFields={
                       "contract_amount":"116,810,902,865",
                       "counterparty":"TAIHAN ELECTRIC USA LTD.",
                       "counterparty_relationship":"자회사",
                       "unknown_custom":"injected",
                   },
                   observedFieldEvidence={
                       "contract_amount":proof("계약금액(원)"),
                       "counterparty":proof("계약상대"),
                       "counterparty_relationship":proof("- 회사와의 관계"),
                       "unknown_custom":proof("비지원"),
                   })
        extracted=m.verified_official_table_terms(row)
        self.assertEqual(extracted["contract_amount"]["value"],"116,810,902,865")
        self.assertNotIn("unknown_custom",extracted)
        self.assertFalse(extracted["contract_amount"]["businessEffectVerified"])
        def source(k,n,c,s,e):
            return {"records":[row] if n=="현대자동차" else [],
                    "complete":True,"pagesRead":1,"totalOfficialFilings":1}
        collected=m.collect(sparse_codes(),"key",now=NOW,query=source,
                            detail=lambda x,key:{**x,**{
                                k:v for k,v in row.items() if k in (
                                  "status","observedFields","observedFieldEvidence")}})
        signal=m.change_review(collected,now=NOW)["signals"][0]
        self.assertTrue(signal["reportedCounterpartyIsAffiliate"])
        self.assertFalse(signal["ultimateExternalCustomerVerified"])
        self.assertFalse(signal["actualShipmentVerified"])
        self.assertIn("외부 최종 고객",signal["nextCheck"])
        self.assertFalse(signal["scoopConfirmed"])

    def test_unproven_and_conflicting_value_is_withheld_from_reporter_card(self):
        row=item("현대자동차","00164742","20261015800221")
        row.update(status="official_document_read",
                   observedFields={"contract_amount":"20,000,000",
                                   "counterparty":"특정 고객"},
                   observedFieldEvidence={
                        "contract_amount":{"basis":"same_official_table_row",
                           "sourceLabel":"계약금액(원)","rowPattern":"two_cell_explicit_label",
                           "independentBusinessVerification":False},
                        "counterparty":{"basis":"inferred_news_story",
                           "sourceLabel":"계약상대방","rowPattern":"two_cell_explicit_label",
                           "independentBusinessVerification":False}},
                   conflictingDocumentFields=["contract_amount"])
        self.assertEqual(m.verified_official_table_terms(row),{})

    def test_newly_disclosed_company_code_does_not_make_old_public_filing_new_news(self):
        kg="20261015000414"
        def source(key,name,code,start,end):
            rows=([item(name,code,kg,"주요사항보고서(자기주식처분결정)")]
                  if name=="KG스틸" else [])
            return {"records":rows,"complete":True,
                    "totalOfficialFilings":len(rows),"pagesRead":1}
        prior=m.collect({"현대자동차":{"corp_code":"00164742"}},"key",
            now=NOW,query=source,detail=fake_detail)
        nowdata=m.collect(sparse_codes(),"key",now=NOW+timedelta(hours=1),
            previous=prior,query=source,detail=fake_detail)
        signal=m.change_review(nowdata,prior,now=NOW+timedelta(hours=1))["signals"][0]
        self.assertEqual(signal["company"],"KG스틸")
        self.assertEqual(signal["status"],"existing_public_filing_from_newly_resolved_issuer")
        self.assertTrue(signal["firstObservedBecauseIssuerBecameCollectable"])
        self.assertTrue(signal["newObservation"])
        self.assertFalse(signal["priorNewsFulltextChecked"])
        self.assertFalse(signal["businessImpactVerified"])
        self.assertFalse(signal["scoopConfirmed"])
        self.assertIn("기존 공개자료",signal["nextCheck"])

    def test_ordinary_new_filing_in_previously_checked_company_keeps_public_receipt_label(self):
        def zero(key,name,code,start,end):
            return {"records":[],"complete":True,"totalOfficialFilings":0,
                    "pagesRead":1}
        def new(key,name,code,start,end):
            return {"records":[item(name,code,"20261015800221")]
                    if name=="현대자동차" else [],
                    "complete":True,"totalOfficialFilings":1,"pagesRead":1}
        old=m.collect(sparse_codes(),"key",now=NOW,query=zero,detail=fake_detail)
        current=m.collect(sparse_codes(),"key",now=NOW+timedelta(hours=1),
                          previous=old,query=new,detail=fake_detail)
        result=m.change_review(current,old,now=NOW+timedelta(hours=1))
        self.assertEqual(result["signals"][0]["status"],"newly_observed_public_filing")
        self.assertFalse(result["signals"][0]["firstObservedBecauseIssuerBecameCollectable"])

    def test_issuer_declared_material_differentiated_from_two_verified_docs(self):
        def correction(row,key):
            return {**row,"status":"original_not_verified",
                "issuerCorrectionTable":{"status":"issuer_table_material_changes_for_review",
                    "changes":[{"fieldLabel":"계약금액","before":"100","after":"150",
                                "basis":"issuer_reported_amendment_table_only",
                                "commercialEffectVerified":False}]}}
        def records(key,name,code,start,end):
            return {"records":[item(name,code,"20261015800221" if name=="현대자동차" else "20261015800222","[기재정정]단일판매ㆍ공급계약체결")],
                    "complete":True,"pagesRead":1,"totalOfficialFilings":1}
        d=m.collect(sparse_codes(),"key",now=NOW,query=records,detail=correction)
        signals=m.change_review(d,now=NOW)["signals"]
        self.assertEqual(signals[0]["status"],"issuer_stated_correction_only")
        self.assertFalse(signals[0]["priorReceiptIndependentCompared"])
        self.assertFalse(signals[0]["businessImpactVerified"])
        self.assertFalse(signals[0]["scoopConfirmed"])

    def test_strict_independent_original_receipt_only(self):
        def correction(row,key):
            return {**row,"status":"original_verified",
                "originalReceiptNo":"20261001800304",
                "originalSourceUrl":"https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261001800304",
                "changes":[{"field":"contract_amount","before":"100",
                            "after":"200","basis":"independent_primary_documents",
                            "needsCompanyConfirmation":True}]}
        def records(key,name,code,start,end):
            return {"records":[item(name,code,"20261015800221" if name=="현대자동차" else "20261015800222","[기재정정]단일판매ㆍ공급계약체결")],
                    "complete":True,"pagesRead":1,"totalOfficialFilings":1}
        d=m.collect(sparse_codes(),"key",now=NOW,query=records,detail=correction)
        x=m.change_review(d,now=NOW)["signals"][0]
        self.assertEqual(x["status"],"two_official_documents_changed_terms")
        self.assertTrue(x["priorReceiptIndependentCompared"])
        self.assertEqual(x["changedTermsForReview"][0]["before"],"100")
        self.assertFalse(x["businessImpactVerified"])

    def test_same_receipt_reparse_discrepancy_not_real_business_change(self):
        first=m.collect(sparse_codes(),"key",now=NOW,query=fake_list,detail=fake_detail)
        later=m.collect(sparse_codes(),"key",now=NOW+timedelta(hours=1),
                        query=fake_list,detail=fake_detail,previous=first)
        later["records"][0]["observedFields"]={"contract_amount":"999,000,000"}
        signal=m.change_review(later,previous=first,now=NOW+timedelta(hours=1))["signals"][0]
        self.assertEqual(signal["status"],"same_receipt_data_reparse_discrepancy")
        self.assertFalse(signal["businessImpactVerified"])
        self.assertFalse(signal["scoopConfirmed"])

    def test_nonrelated_and_invalid_corp_name_rejected(self):
        with self.assertRaises(ValueError):
            m.fetch_official_list("key","삼성전기","00126371","20261001","20261015")
        with self.assertRaises(ValueError):
            m.fetch_official_list("key","현대자동차","WRONG","20261001","20261015")

class RegistryTests(unittest.TestCase):
    def sample_zip(self):
        entries=[("<list><corp_code>00164742</corp_code><corp_name>(주)현대자동차</corp_name></list>"),
                 ("<list><corp_code>00880099</corp_code><corp_name>주식회사 케이지스틸</corp_name></list>")]
        entries += [f"<list><corp_code>{i:08d}</corp_code><corp_name>기타기업{i}</corp_name></list>"
                    for i in range(1000,2000)]
        data=("<result>"+"".join(entries)+"</result>").encode()
        io_buffer=io.BytesIO()
        with zipfile.ZipFile(io_buffer,"w",zipfile.ZIP_DEFLATED) as z:
            z.writestr("CORPCODE.xml",data)
        return io_buffer.getvalue()

    def test_unique_official_match_populates_missing_only(self):
        idx,n=registry.official_index(self.sample_zip())
        self.assertGreaterEqual(n,1000)
        new,report=registry.resolve(sparse_codes(),idx,now=NOW,registry_count=n)
        self.assertEqual(new["KG스틸"]["corp_code"],"00112233")
        self.assertEqual(new["현대자동차"]["corp_code"],"00164742")
        self.assertEqual(report["manualConflicts"],1)
        self.assertTrue(any(x["status"]=="existing_code_official_name_mismatch_manual_review"
                            for x in report["companies"] if x["company"]=="KG스틸"))
        new,report=registry.resolve({"현대자동차":{"corp_code":"00164742"}},idx,now=NOW,registry_count=n)
        self.assertEqual(new["KG스틸"]["corp_code"],"00880099")
        self.assertGreaterEqual(report["newUniqueCodesAdded"],1)

    def test_existing_exact_official_code_survives_multiple_legal_name_candidates(self):
        existing={
          "KG스틸":{"corp_code":"00115676","stock_code":"016380"},
          "포스코홀딩스":{"corp_code":"00155319","stock_code":"005490"}
        }
        index={
          "kg스틸":{"00115676"},
          "케이지스틸":{"00115676","00999999"},
          "posco홀딩스":{"00155319"}
        }
        updated,report=registry.resolve(existing,index,now=NOW)
        self.assertEqual(updated,existing)
        self.assertEqual(report["manualConflicts"],0)
        by_name={x["company"]:x for x in report["companies"]}
        self.assertEqual(by_name["KG스틸"]["status"],
                         "existing_code_verified_in_official_registry")
        self.assertEqual(by_name["포스코홀딩스"]["status"],
                         "existing_code_verified_in_official_registry")

    def test_ambiguous_legal_name_is_not_resolved(self):
        new,report=registry.resolve({},{"케이지스틸":{"00111111","00222222"}},now=NOW)
        self.assertNotIn("KG스틸",new)
        self.assertGreaterEqual(report["manualConflicts"],1)

    def test_fake_xml_nonzip_never_claims_code(self):
        with self.assertRaises(ValueError):
            registry.official_index(b"<result><list><corp_code>12345678</corp_code></list></result>")

if __name__=="__main__":unittest.main()
