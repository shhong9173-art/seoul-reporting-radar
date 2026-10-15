"""DART contracts: explicit original lineage, issuer fields, news-index uncertainty."""
import copy
import json
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import dart_contract_followup as m

NOW=datetime(2026,10,15,13,0,tzinfo=timezone(timedelta(hours=9)))
NEW="20261013800054"
AMEND="20261014800022"
ORIG="20260930800022"

def item(receipt=NEW,corrected=False):
    return dict(company="엘에스일렉트릭",corpCode="00105855",receiptNo=receipt,
                published=receipt[:8],report=("[기재정정]" if corrected else "")+"단일판매ㆍ공급계약체결",
                category="공급계약",isCorrection=corrected,
                sourceUrl="https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+receipt,
                status="original_not_verified" if corrected else "official_document_read",
                observedFields={} if not corrected else None)
def fixture():
    return dict(generatedAt="2026-10-15T10:27:02+09:00",
        sourceChecks=[dict(company="엘에스일렉트릭",status="checked")],
        items=[item(),item(AMEND,True)],uninspectedListCount=0)

def rss(title="LS일렉트릭 공급계약 관련 가능 기사",link="https://news.google.com/rss/articles/TEST?x=1",
        when="Wed, 14 Oct 2026 09:00:00 GMT"):
    return ('<rss version="2.0"><channel><title>Search results</title><item>'
            '<title>'+title+'</title><link>'+link+'</link><pubDate>'+when+
            '</pubDate></item></channel></rss>').encode()

def feed_empty(_):
    return b'<rss version="2.0"><channel><title>No results</title></channel></rss>'

class FollowupReview(unittest.TestCase):
    def test_affiliate_counterparty_not_promoted_to_external_award(self):
        row=item()
        row["observedFields"]={
            "contract_amount":"185,257,183,992",
            "recent_sales":"4,965,798,552,980",
            "sales_ratio":"3.73",
            "counterparty":"LS ELECTRIC AMERICA Inc.",
            "counterparty_relationship":"자회사",
            "contract_subject":"펜실베니아 연료전지 전력설비 공급 PJT"
        }
        row["status"]="official_document_read"
        out=m.review_one(row,search=False,now=NOW)
        self.assertEqual(out["unambiguousCurrentDocumentFields"]["sales_ratio"],"3.73")
        self.assertIn("외부 최종 고객",out["nextChecks"][0])
        self.assertFalse(out["companyImpactVerified"])
        self.assertFalse(out["exclusiveConfirmed"])

    def test_empty_press_index_does_not_certify_unreported(self):
        out=m.build(fixture(),now=NOW,fetch=feed_empty)
        self.assertEqual(out["reviewedEvents"],2)
        self.assertEqual(out["confirmedScoops"],0)
        self.assertEqual(out["approvedArticles"],0)
        self.assertEqual(out["independentlyComparedMaterialFields"],0)
        self.assertEqual(out["correctionsWithoutVerifiedOriginal"],1)
        for v in out["items"]:
            self.assertEqual(v["pressIndexStatus"],"index_no_hits_not_proof_unreported")
            self.assertFalse(v["priorCoverageOfSameContractVerified"])
            self.assertFalse(v["exclusiveConfirmed"])
            self.assertFalse(v["actualShipmentChangeVerified"])
            self.assertFalse(v["companyImpactVerified"])
    def test_verified_original_compares_only_official_same_document_values(self):
        x=item(AMEND,True)
        x.update(status="original_verified",originalReceiptNo=ORIG,
                 originalSourceUrl="https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+ORIG,
                 changes=[dict(field="contract_amount",before="100,000,000",
                               after="120,000,000",basis="independent_primary_documents",
                               numericDelta=None,needsCompanyConfirmation=True)])
        reviewed=m.review_one(x,rss_fetch=feed_empty,now=NOW)
        self.assertEqual(reviewed["comparisonStatus"],"original_verified_changes_needs_reporting")
        changes=reviewed["materialFieldChanges"]
        self.assertEqual(len(changes),1)
        self.assertEqual(changes[0]["sourceBefore"],x["originalSourceUrl"])
        self.assertEqual(changes[0]["sourceAfter"],x["sourceUrl"])
        self.assertIsNone(changes[0]["numericDifference"])
        self.assertFalse(changes[0]["businessImpactVerified"])
        self.assertEqual(reviewed["originalReceiptNo"],ORIG)
    def test_unverified_correction_remains_without_change_values(self):
        x=item(AMEND,True)
        x.update(status="original_not_verified",originalReceiptNo=ORIG,
                 originalSourceUrl="https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+ORIG,
                 changes=[dict(field="contract_amount",before="1",after="9")])
        reviewed=m.review_one(x,rss_fetch=feed_empty,now=NOW)
        self.assertEqual(reviewed["comparisonStatus"],"original_unverified_no_comparison")
        self.assertFalse(reviewed["materialFieldChanges"])
        self.assertIsNone(reviewed["originalReceiptNo"])
    def test_poorly_proven_changed_fields_cannot_be_displayed(self):
        x=item(AMEND,True)
        x.update(status="original_verified",originalReceiptNo=ORIG,
                 originalSourceUrl="https://dart.fss.or.kr/dsaf001/main.do?rcpNo="+ORIG,
                 changes=[dict(field="contract_amount",before="100",after="999",basis="guessed")])
        reviewed=m.review_one(x,rss_fetch=feed_empty,now=NOW)
        self.assertEqual(reviewed["comparisonStatus"],"invalid_independent_comparison")
        self.assertFalse(reviewed["materialFieldChanges"])
        self.assertIsNone(reviewed["originalReceiptNo"])
    def test_wrong_original_link_is_rejected(self):
        x=item(AMEND,True)
        x.update(status="original_verified",originalReceiptNo=ORIG,
                 originalSourceUrl="https://malicious.example/?rcpNo="+ORIG,changes=[])
        self.assertEqual(m.review_one(x,rss_fetch=feed_empty,now=NOW)["comparisonStatus"],
                         "original_unverified_no_comparison")
    def test_noncorrection_unambiguous_fields_labelled_not_confirmed_contract(self):
        x=item();x["observedFields"]={"contract_amount":"120,000,000",
                                     "contract_end":"2029-01-01","custom":"unsupported"}
        reviewed=m.review_one(x,rss_fetch=feed_empty,now=NOW)
        self.assertEqual(reviewed["unambiguousCurrentDocumentFields"],
                         {"contract_amount":"120,000,000","contract_end":"2029-01-01"})
        self.assertTrue(reviewed["fieldValuesAreIssuerTextNotIndependentCommercialProof"])
        self.assertFalse(reviewed["contractTermsVerified"] if "contractTermsVerified" in reviewed else False)
    def test_rss_search_hit_is_not_definite_prior_coverage(self):
        a=m.review_one(item(),rss_fetch=lambda url:rss(),now=NOW)
        self.assertEqual(a["pressIndexStatus"],"indexed_possible_articles_require_fulltext")
        self.assertEqual(a["indexedArticleCount"],2)
        self.assertFalse(a["priorCoverageOfSameContractVerified"])
        self.assertFalse(a["exclusiveConfirmed"])
        self.assertTrue(a["exactReceiptNumberIndexLead"])
        self.assertEqual(a["possiblePreOrSameFilingDayIndexedCount"],0)
    def test_rss_earlier_date_still_not_same_contract_proof(self):
        r=m.rss_index('"20261013800054"',fetch=lambda u:rss(when="Mon, 12 Oct 2026 08:00:00 GMT"),now=NOW)
        self.assertEqual(r["articles"][0]["publishedAt"][:10],"2026-10-12")
        out=m.review_one(item(),rss_fetch=lambda u:rss(when="Mon, 12 Oct 2026 08:00:00 GMT"),now=NOW)
        self.assertGreater(out["possiblePreOrSameFilingDayIndexedCount"],0)
        self.assertFalse(out["priorCoverageOfSameContractVerified"])
    def test_xml_attack_or_timeout_is_not_zero_press(self):
        for fetch in (lambda u:b'<!DOCTYPE evil><rss><channel/></rss>',
                      lambda u:(_ for _ in ()).throw(TimeoutError("too slow"))):
            x=m.review_one(item(),rss_fetch=fetch,now=NOW)
            self.assertEqual(x["pressIndexStatus"],"press_index_partial_failure")
            self.assertFalse(x["pressSearchCompleted"])
            self.assertEqual(x["indexedArticleCount"],0)
    def test_news_feed_discards_untrusted_external_urls(self):
        a=m.rss_index("sample",fetch=lambda u:rss(link="https://attacker.example/redirect"),now=NOW)
        self.assertEqual(a["status"],"no_index_hits")
        self.assertEqual(a["articles"],[])
    def test_source_receipt_identity_and_duplication(self):
        f=fixture()
        f["items"].append(copy.deepcopy(f["items"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate_receipt"):
            m.build(f,now=NOW,fetch=feed_empty)
        f=fixture()
        f["items"][0]["published"]="20261014"
        with self.assertRaisesRegex(ValueError,"unsafe_filing_identity"):
            m.build(f,now=NOW,fetch=feed_empty)
    def test_network_disabled_is_unknown_not_zero(self):
        out=m.build(fixture(),now=NOW,search=False)
        self.assertEqual(out["mediaLookupFailedEvents"],2)
        self.assertTrue(all(x["pressIndexStatus"]=="press_not_searched" for x in out["items"]))
    def test_saved_oct15_official_ledger_is_supported_without_network(self):
        source=json.loads((ROOT/"digests/recent_contracts_latest.json").read_text(encoding="utf-8"))
        out=m.build(source,now=NOW,search=False)
        self.assertEqual(out["reviewedEvents"],7)
        self.assertEqual(out["correctionsWithoutVerifiedOriginal"],4)
        self.assertEqual(out["independentlyComparedMaterialFields"],0)
        self.assertEqual(out["confirmedScoops"],0)
        self.assertEqual(out["unreviewedDartItems"],0)
        self.assertFalse(any(x["priorCoverageOfSameContractVerified"] for x in out["items"]))

if __name__=="__main__":unittest.main()
