import json
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path

from scripts.primary_original_discovery import (
    discover,valid_targets,named,ROOT,STATUS
)

CFG=json.loads((ROOT/"data/primary_site_listing_watches.json").read_text("utf-8"))
T0=datetime(2026,10,21,5,0,tzinfo=timezone.utc)

def listing_first(url):
    if "svdisposition.com/past" in url:
        return ('<html><h1>Official past auctions</h1>'+
             '<a href="/auction-detail/884">Surplus Supernal Mojave Sep 21</a>'+
             '<a href="/auction-detail/891">Supernal 2nd sale October</a>'+
             '<a href="https://evil.example/auction-detail/222">Supernal fake</a>'+
             '</html>')
    if "svdisposition.com/upcoming" in url:
        return ('<html><h1>Upcoming original auctions</h1><p>No named recent OEM lot in first page. '
            'Independent company equipment liquidation listing includes anonymous industrial machinery '
            'and does not establish ownership of any tracked automotive firm.</p></html>')
    return ('<html><h1>Official IPGATE insights</h1>'+
            '<a href="/blog/hyundai-legal-action">IPGATE files against Hyundai</a>'+
            '<a href="/blog/opinion-on-patents">licensing general commentary</a></html>')

def detail(url):
    if "auction-detail" in url:
        return "Official Silicon Valley Disposition Supernal equipment and aircraft research surplus, Mojave California, hangar 200 and 201"
    if "/blog/" in url:
        return "IPGATE official announcement filed legal action against Hyundai Motor Europe and Hyundai Motor Deutschland in Munich patent court"
    raise AssertionError(url)

class OfficialListingDiscovery(unittest.TestCase):
    def test_real_auction_card_company_name_is_sibling_of_generic_details_link(self):
        def auction_listing(url):
            if url.endswith("past-auctions"):
                return (
                    '<html><main><section>'
                    '<div class="auction-card"><h3>EXTREMELY SHORT NOTICE SALE: '
                    'Surplus Assets to the Ongoing Operations of Supernal #2</h3>'
                    '<p>Oct 12-14 2026 Mojave CA</p>'
                    '<a href="/auction-detail/891">View Auction Details</a></div>'
                    '<div class="auction-card"><h3>Unrelated Solar Equipment</h3>'
                    '<a href="/auction-detail/900">View Auction Details</a></div>'
                    '</section></main></html>')
            return listing_first(url)
        result=discover(CFG,now=T0,listing_fetcher=auction_listing,
                        detail_fetcher=detail)
        links={x["url"] for x in result["candidates"]}
        self.assertIn("https://svdisposition.com/auction-detail/891",links)
        self.assertNotIn("https://svdisposition.com/auction-detail/900",links)
        self.assertEqual(result["sourcesChecked"],3)
        self.assertEqual(result["newlyObservedAfterBaseline"],0)

    def test_parent_page_company_name_must_not_bleed_to_unrelated_cards(self):
        def listing(url):
            if url.endswith("past-auctions"):
                return (
                    '<html><h1>Supernal auctions archive</h1>'
                    '<div><h3>Unrelated battery research laboratory</h3>'
                    '<a href="/auction-detail/100">View Auction Details</a></div>'
                    '<div><h3>Generic equipment in storage</h3>'
                    '<a href="/auction-detail/101">View Auction Details</a></div>'
                    '</html>')
            return listing_first(url)
        rows=discover(CFG,now=T0,listing_fetcher=listing,
                      detail_fetcher=detail)["candidates"]
        self.assertFalse(any(x["sourceId"]=="svd-past" for x in rows))

    def test_real_nvidia_tesla_gpu_auction_is_not_tesla_vehicle_business(self):
        exact=("Bay Area Tech Co #29 Sep 22–24, 2026 Santa Clara CA "
               "Featuring New-In-Box Dell S3248T PowerSwitches, "
               "Nvidia Tesla GPU's, Cisco Mount Servers")
        self.assertEqual(named(exact,["Tesla"]),[])
        self.assertEqual(named("Nvidia Tesla V100 GPU sale",["Tesla"]),[])
        self.assertEqual(named("Tesla Inc factory assets",["Tesla"]),["Tesla"])
        def gpu_listing(url):
            markup=listing_first(url)
            if "past-auctions" in url:
                markup=markup.replace("</html>",
                    '<div class="auction-card"><h3>'+exact+'</h3>'
                    '<a href="/auction-detail/999">View Auction Details</a></div>'
                    '</html>')
            return markup
        def gpu_details(url):
            if url.endswith("/999"):
                return ("Nvidia Tesla GPU V100 semiconductor compute accelerator "
                        "rack surplus laboratory auction, Santa Clara")
            return detail(url)
        observed=discover(CFG,now=T0,listing_fetcher=gpu_listing,
                          detail_fetcher=gpu_details)
        self.assertEqual(observed["candidateCount"],3)
        self.assertFalse(any("/999" in x["url"] for x in observed["candidates"]))
        # The old live false-positive must be purged from a previous digest,
        # not cached with notRecheckedThisRun for another fortnight.
        bad={**observed["candidates"][0],
             "url":"https://svdisposition.com/auction-detail/999",
             "title":exact,"sourceId":"svd-past"}
        previous=json.loads(json.dumps(observed))
        previous["candidates"].append(bad)
        previous["candidateCount"]=4
        again=discover(CFG,previous,now=T0+timedelta(minutes=30),
                       listing_fetcher=listing_first,detail_fetcher=detail)
        self.assertEqual(again["priorRowsRejectedByCurrentIdentityRules"],1)
        self.assertFalse(any("/999" in x["url"] for x in again["candidates"]))
        self.assertEqual(again["confirmedScoops"],0)

    def test_baseline_is_not_synthetic_new_exclusive(self):
        o=discover(CFG,now=T0,listing_fetcher=listing_first,detail_fetcher=detail)
        self.assertEqual(o["status"],STATUS)
        self.assertEqual(o["sourcesChecked"],3)
        self.assertEqual(o["candidateCount"],3)
        self.assertEqual(o["newlyObservedAfterBaseline"],0)
        self.assertTrue(all(x["originalPageRead"] for x in o["candidates"]))
        self.assertTrue(all(not x["publishedAtVerified"] for x in o["candidates"]))
        self.assertTrue(all(not x["confirmedExclusive"] for x in o["candidates"]))
        self.assertFalse(o["sourceCoverageExhaustive"])

    def test_second_fetch_new_named_link_is_first_observed_not_first_published(self):
        first=discover(CFG,now=T0,listing_fetcher=listing_first,detail_fetcher=detail)
        def second(url):
            html=listing_first(url)
            if url.endswith("/blog"):
                return html.replace("</html>",'<a href="/blog/hyundai-new-filing">Hyundai new filing announcement</a></html>')
            return html
        later=discover(CFG,first,now=T0+timedelta(hours=4),
                       listing_fetcher=second,detail_fetcher=detail)
        self.assertEqual(later["candidateCount"],4)
        self.assertEqual(later["newlyObservedAfterBaseline"],1)
        row=next(x for x in later["candidates"] if x["newlyObservedAfterCleanBaseline"])
        self.assertIn("hyundai-new-filing",row["url"])
        self.assertFalse(row["publishedAtVerified"])
        self.assertFalse(row["domesticPriorCoverageChecked"])
        self.assertEqual(later["confirmedScoops"],0)
        self.assertTrue(all(not x["baselineOnly"] for x in later["sources"]))

    def test_source_outage_preserves_observed_row_and_does_not_report_zero(self):
        first=discover(CFG,now=T0,listing_fetcher=listing_first,detail_fetcher=detail)
        def failing(url):
            if "past-auctions" in url:
                raise TimeoutError("outage")
            return listing_first(url)
        later=discover(CFG,first,now=T0+timedelta(minutes=30),
                       listing_fetcher=failing,detail_fetcher=detail)
        self.assertEqual(later["sourcesUnavailable"],1)
        self.assertEqual(later["candidateCount"],3)
        stale=[r for r in later["candidates"] if "auction-detail" in r["url"]]
        self.assertEqual(len(stale),2)
        self.assertTrue(all(r["notRecheckedThisRun"] for r in stale))
        self.assertFalse(later["domesticNoPriorCoverageProved"])
        self.assertEqual(later["newlyObservedAfterBaseline"],0)

    def test_detail_company_must_match_listing_named_subject(self):
        def bad(url):
            return "A different unrelated anonymous manufacturing operation has offered spare tables and containers at auction"
        out=discover(CFG,now=T0,listing_fetcher=listing_first,detail_fetcher=bad)
        self.assertEqual(out["candidateCount"],0)
        self.assertEqual(out["newlyObservedAfterBaseline"],0)
        self.assertGreater(out["sourcesChecked"],0)
        self.assertFalse(out["sourceCoverageExhaustive"])

    def test_registry_and_link_security(self):
        bad=json.loads(json.dumps(CFG))
        bad["watch"][0]["url"]="https://private.example/internal"
        with self.assertRaises(ValueError):valid_targets(bad)
        bad=json.loads(json.dumps(CFG))
        bad["watch"][0]["pathPrefix"]="/anything/"
        with self.assertRaises(ValueError):valid_targets(bad)
        out=discover(CFG,now=T0,listing_fetcher=listing_first,detail_fetcher=detail)
        self.assertFalse(any("evil.example" in z["url"] for z in out["candidates"]))

    def test_invalid_previous_is_not_silently_reset(self):
        with self.assertRaises(ValueError):
            discover(CFG,{"status":"broken"},now=T0,
                     listing_fetcher=listing_first,detail_fetcher=detail)

if __name__=="__main__":unittest.main()
