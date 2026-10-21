import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.primary_document_dossiers import (
    dossier, checked_registry, safe_url, normalized, STATUS, ROOT as APP_ROOT
)

NOW=datetime(2026,10,21,4,22,tzinfo=timezone.utc)
REG=json.loads((APP_ROOT/"data/primary_research_targets.json").read_text(encoding="utf-8"))

PAGES={
 "svd-september":"""<html><h1>Supernal asset auction</h1>
    Auction Dates: Sep 21–23, 2026
    Address: 1030 Flightline, Hangar 200 & 201, Mojave</html>""",
 "svd-october":"""<html><h1>Surplus Assets to Supernal #2</h1>
    Auction Dates: Oct 12–14, 2026 Address: Hangar 200 & 201,
    Mojave, CA. Checkout: Oct 19–20, 2026
    Contact Daniel Juliano: djuliano@svdisposition.com</html>""",
 "ipgate-statement":"""<html><h1>IPGATE press release</h1>
    2026-10-19 IPGATE filed patent suit against
    Hyundai Motor Europe and Hyundai Motor Deutschland before Munich
    EP 3 145 771 B1. Offered Hyundai Mobis a license since September 2021.
    </html>""",
 "scotus-docket":"""<html><h1>26A342 Hyundai Motor America</h1>
    Sep 14 2026 granted Justice Kagan. September 14, 2026
    Oct 07 2026 application for further extension.
    </html>""",
 "ses-q4-2025-letter":"""<html><h2>SES AI Q4</h2>
    We completed our EV development work with Honda and Hyundai
    with the final contributions from services agreements.
    </html>""",
 "ses-q1-2025-filing":"""<html><h2>SES AI quarterly</h2>
    JDA with Hyundai Motor Company to develop B-sample Li-Metal
    batteries until December 2025.
    </html>""",
 "hcuk-filing-history":"""<html><h1>HYUNDAI CAPITAL UK LIMITED</h1>
    06 Oct 2025 Group of companies' accounts made up to
    31 December 2024 View PDF, 53 pages.
    </html>""",
}
IDS={doc["url"]:doc["id"] for c in REG["cases"] for doc in c["documents"]}

def fake_fetch(url):
    return normalized(PAGES[IDS[url]])

class ReporterFirstPartyDocumentDossiers(unittest.TestCase):
    def test_all_five_source_specific_cases_match_exact_public_source_text(self):
        result=dossier(REG,now=NOW,fetcher=fake_fetch)
        self.assertEqual(result["status"],STATUS)
        self.assertEqual(result["caseCount"],5)
        self.assertEqual(result["documentPagesMatched"],7)
        self.assertEqual(result["documentPagesFailedOrUnmatched"],0)
        self.assertEqual(result["confirmedScoops"],0)
        self.assertFalse(result["allDomesticPressChecked"])
        self.assertTrue(result["registryIsManuallyCuratedNotAutomatedDiscovery"])
        cases={x["id"]:x for x in result["cases"]}
        self.assertEqual(cases["supernal-mojave-assets"]["originalDocumentsVerified"],2)
        self.assertEqual(cases["ipgate-munich-brake"]["originalDocumentsVerified"],1)
        self.assertEqual(cases["bluelink-scotus-26a342"]["originalDocumentsVerified"],1)
        self.assertEqual(cases["ses-hyundai-bsample"]["originalDocumentsVerified"],2)
        self.assertEqual(cases["hcuk-uk-redress"]["originalDocumentsVerified"],1)
        self.assertTrue(all(not x["exclusiveConfirmed"] and not x["noPriorPressProved"]
                            for x in cases.values()))
        for c in cases.values():
            self.assertTrue(c["questionsForPublicConfirmation"])
            self.assertTrue(c["factsFromMatchedPrimaryPages"])
            self.assertEqual(c["priorPressIndexStatus"],"not_provided")
        self.assertIn("PDF",cases["hcuk-uk-redress"]["unresolved"][0])

    def test_inaccessible_source_not_backfilled_with_cached_facts(self):
        valid=dossier(REG,now=NOW,fetcher=fake_fetch)
        def failing(url):
            if IDS[url]=="ipgate-statement":
                raise TimeoutError("source down")
            return fake_fetch(url)
        later=dossier(REG,previous=valid,
                      now=NOW.replace(hour=5),fetcher=failing)
        lawsuit=next(x for x in later["cases"] if x["id"]=="ipgate-munich-brake")
        self.assertEqual(lawsuit["status"],"originals_not_currently_verified")
        self.assertEqual(lawsuit["factsFromMatchedPrimaryPages"],[])
        doc=lawsuit["originalDocuments"][0]
        self.assertEqual(doc["status"],"source_unavailable")
        self.assertEqual(doc["errorType"],"TimeoutError")
        self.assertEqual(doc["lastSuccessfulObservationAt"],valid["generatedAt"])
        self.assertEqual(later["confirmedScoops"],0)

    def test_missing_critical_phrase_is_not_factual_proof(self):
        def tampered(url):
            return fake_fetch(url).replace("September 2021","September 2022")
        result=dossier(REG,now=NOW,fetcher=tampered)
        ip=next(x for x in result["cases"] if x["id"]=="ipgate-munich-brake")
        self.assertEqual(ip["originalDocumentsVerified"],1)
        self.assertEqual(len(ip["factsFromMatchedPrimaryPages"]),1)
        self.assertNotIn("2021년 9월",json.dumps(ip["factsFromMatchedPrimaryPages"],ensure_ascii=False))
        self.assertFalse(ip["exclusiveConfirmed"])

    def test_observation_not_new_publication_and_failed_registry_does_not_erase(self):
        initial=dossier(REG,now=NOW,fetcher=fake_fetch)
        later=dossier(REG,previous=initial,
                      now=NOW.replace(hour=7),fetcher=fake_fetch)
        ip=next(x for x in later["cases"] if x["id"]=="ipgate-munich-brake")
        original=ip["originalDocuments"][0]
        self.assertEqual(original["firstObservedAt"],initial["generatedAt"])
        self.assertFalse(original["baselineOnly"])
        self.assertFalse(original["contentChangedSincePriorCheck"])
        self.assertTrue(ip["sourceDateFromRegistryNotMachineVerified"])
        broken={**initial,"status":"bogus"}
        with self.assertRaises(ValueError):
            dossier(REG,previous=broken,now=NOW,fetcher=fake_fetch)

    def test_press_candidates_are_positive_only_never_unreported_proof(self):
        posts=[{"title":"현대차·IPGATE 독일 소송 보도","url":"https://news.example/x"},
               {"title":"슈퍼널 모하비 격납고 경매 확인","url":"https://news.example/y"}]
        x=dossier(REG,now=NOW,fetcher=fake_fetch,prior_press=posts)
        ip=next(c for c in x["cases"] if c["id"]=="ipgate-munich-brake")
        self.assertEqual(len(ip["possiblePriorPressTitles"]),1)
        self.assertEqual(ip["priorPressIndexStatus"],"partial_index_not_fulltext_checked")
        self.assertFalse(ip["noPriorPressProved"])
        self.assertTrue(all(not c["exclusiveConfirmed"] for c in x["cases"]))

    def test_registry_domain_safety_and_manual_review(self):
        self.assertFalse(safe_url("http://www.ipgate.ch/blog/hyundai-legal-action"))
        self.assertFalse(safe_url("https://127.0.0.1/private"))
        self.assertFalse(safe_url("https://www.ipgate.ch.attacker.com/"))
        self.assertFalse(safe_url("https://user:pw@www.ipgate.ch/a"))
        self.assertTrue(safe_url("https://www.ipgate.ch/blog/hyundai-legal-action"))
        broken=json.loads(json.dumps(REG))
        broken["cases"][0]["documents"][0]["url"]="https://attacker.example/secret"
        with self.assertRaises(ValueError):
            checked_registry(broken)

    def test_html_script_cannot_inject_false_evidence(self):
        source="<html><script>EP 3 145 771 B1</script><p>Public notice</p></html>"
        self.assertNotIn("EP 3",normalized(source))
        self.assertIn("Public notice",normalized(source))

if __name__=="__main__":
    unittest.main()
