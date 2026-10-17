"""DART legal name collisions may be resolved ONLY by stock code in same official registry row."""
import io,sys,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import dart_corp_registry as r

def xml(name,code,stock=""):
    return ("<list><corp_name>"+name+"</corp_name><corp_code>"+code+
            "</corp_code><stock_code>"+stock+"</stock_code></list>")

def sample(second_stock="",first_stock="016380",fake_alias_stock=None):
    # Registry parser refuses truncated body; model official >1000 issuers.
    rows=[xml("테스트법인"+str(i),str(i+10000000)) for i in range(1001)]
    rows += [xml("케이지스틸(주)","00115676",first_stock),
             xml("케이지스틸(주)","00999999",second_stock)]
    if fake_alias_stock is not None:
        rows.append(xml("이름무관 타법인","00777777",fake_alias_stock))
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        z.writestr("CORPCODE.xml","<result>"+"".join(rows)+"</result>")
    return out.getvalue()

class ListedStockEvidence(unittest.TestCase):
    def test_two_name_candidates_official_ticker_proves_only_listed_company(self):
        idx,total=r.official_index(sample())
        self.assertGreaterEqual(total,1000)
        self.assertEqual(idx["케이지스틸"],{"00115676","00999999"})
        key=r.STOCK_KEY_PREFIX+"KG스틸:016380"
        self.assertEqual(idx[key],{"00115676"})
        codes,diag=r.resolve({},idx,registry_count=total)
        self.assertEqual(codes["KG스틸"],
                         {"corp_code":"00115676","stock_code":"016380"})
        row=next(x for x in diag["companies"] if x["company"]=="KG스틸")
        self.assertEqual(row["status"],"resolved_unique_official_stock_and_legal_name")
        self.assertEqual(row["officialListedStockCodeProof"],"016380")
        self.assertEqual(row["officialMatchCount"],2)
        self.assertEqual(diag["listedTickerNameAmbiguitiesResolved"],1)
        self.assertEqual(diag["newUniqueCodesAdded"],1)

    def test_same_ticker_in_both_official_name_records_stays_ambiguous(self):
        idx,_=r.official_index(sample(second_stock="016380"))
        codes,report=r.resolve({},idx)
        self.assertNotIn("KG스틸",codes)
        row=next(x for x in report["companies"] if x["company"]=="KG스틸")
        self.assertEqual(row["status"],"ambiguous_official_legal_name")
        self.assertIsNone(row["officialListedStockCodeProof"])

    def test_false_stock_in_different_corporation_name_does_not_join(self):
        idx,_=r.official_index(sample(first_stock="",fake_alias_stock="016380"))
        codes,report=r.resolve({},idx)
        self.assertNotIn("KG스틸",codes)
        self.assertEqual(report["listedTickerNameAmbiguitiesResolved"],0)

    def test_no_matching_official_ticker_does_not_use_external_guess(self):
        idx,_=r.official_index(sample(first_stock="016381"))
        codes,report=r.resolve({},idx)
        self.assertNotIn("KG스틸",codes)
        self.assertEqual(report["listedTickerNameAmbiguitiesResolved"],0)

    def test_verified_existing_dart_code_is_never_replaced(self):
        idx,_=r.official_index(sample())
        old={"KG스틸":{"corp_code":"00999999","stock_code":"016380"}}
        codes,report=r.resolve(old,idx)
        self.assertEqual(codes,old)
        row=next(x for x in report["companies"] if x["company"]=="KG스틸")
        self.assertEqual(row["status"],"existing_code_verified_in_official_registry")
        # Explicit existing mismatches require human review and no overwrite.
        old={"KG스틸":{"corp_code":"00888888","stock_code":"016380"}}
        codes,report=r.resolve(old,idx)
        self.assertEqual(codes,old)
        row=next(x for x in report["companies"] if x["company"]=="KG스틸")
        self.assertEqual(row["status"],"existing_code_official_name_mismatch_manual_review")

if __name__=="__main__":unittest.main()
