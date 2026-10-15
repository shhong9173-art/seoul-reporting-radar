"""Official Slovak attachment hash, exact entity, exact IFRS report and safe PDF notes."""
import hashlib,json,sys,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import slovak_ifrs_primary_pages as m

NOW=datetime(2026,10,16,6,0,tzinfo=timezone(timedelta(hours=9)))
PDF=b"%PDF-1.4\n"+(b"evidence only"*110)
SHA=hashlib.sha256(PDF).hexdigest()

def source():
    return {"status":"official_slovak_registry_identity_and_filing_metadata",
        "generatedAt":"2026-10-16T05:30:00+09:00",
        "ico":"35876832","companyIdentityVerified":True,
        "officialEntityId":244945,
        "statements":[{
          "financialYear":y,"statementId":statement,
          "reportIds":[report],"sameIcoAndLegalNameConfirmed":True,
          "profitOrDividendAmountsParsed":False,
          "officialIfrsReportDetailUrl":"https://www.registeruz.sk/cruz-public/domain/financialreport/show/"+str(report)
        } for y,(statement,report) in m.IFRS.items()]}
def mock_source(url,limit):
    if url.startswith(m.API):
        report=int(url.removeprefix(m.API))
        year=next(y for y,(_,x) in m.IFRS.items() if x==report)
        statement,_=m.IFRS[year]
        return json.dumps({
            "id":report,"idUctovnejZavierky":statement,
            "pristupnostDat":"Verejné prílohy",
            "prilohy":[{"id":report+10000,"digest":SHA,
                        "mimeType":"application/pdf",
                        "velkostPrilohy":len(PDF),"pocetStran":4}]
        }).encode()
    if url.startswith(m.ATTACHMENTS):
        return PDF
    raise AssertionError("nonallowlisted external download URL")

def mock_pages(pdf):
    assert pdf==PDF
    return ["Notes on distributions", "The Board proposed a dividend for the year 2024.",
            "Retained earnings are presented with comparative periods."]

class PrimaryPDF(unittest.TestCase):
    def test_official_pdf_verified_by_exact_checksum_and_only_page_context(self):
        result=m.analyze(source(),now=NOW,fetch=mock_source,pdf_text=mock_pages)
        self.assertEqual(result["verifiedPdfCount"],2)
        self.assertEqual(result["reportCount"],2)
        self.assertGreater(result["verifiedPageExcerpts"],1)
        for row in result["reports"]:
            self.assertTrue(row["pdfReadAndOfficialHashVerified"])
            self.assertEqual(row["sha256"],SHA)
            self.assertTrue(row["attachmentUrl"].startswith(m.ATTACHMENTS))
            self.assertEqual(row["status"],"official_pdf_text_passages_for_manual_review")
            self.assertFalse(row["dividendCashRemittanceVerified"])
            for passage in row["pageClues"]:
                self.assertGreaterEqual(passage["page"],1)
                self.assertFalse(passage["containsFinancialAmountValidated"])
                self.assertFalse(passage["cashPaidOrRetainedProfitValidated"])
        self.assertFalse(result["dividendPaymentToParentVerified"])
        self.assertFalse(result["financialFiguresInterpreted"])
        self.assertFalse(result["exclusiveConfirmed"])

    def test_checksum_mismatch_suppresses_all_excerpts(self):
        def wrong(url,limit):
            if url.startswith(m.ATTACHMENTS):return b"%PDF-1.4\n"+b"not correct"*120
            return mock_source(url,limit)
        result=m.analyze(source(),now=NOW,fetch=wrong,pdf_text=mock_pages)
        self.assertEqual(result["verifiedPdfCount"],0)
        self.assertEqual(result["verifiedPageExcerpts"],0)
        self.assertEqual(result["sourceQueriesFailed"],2)
        self.assertTrue(all(x["status"]=="official_metadata_or_attachment_error"
                            for x in result["reports"]))
        self.assertFalse(result["dividendPaymentToParentVerified"])

    def test_wrong_ifrs_parent_id_never_download_pdf(self):
        called=[]
        def fake(url,n):
            called.append(url)
            if url.startswith(m.API):
                return json.dumps({"id":int(url.removeprefix(m.API)),
                         "idUctovnejZavierky":9999,"pristupnostDat":"Verejné",
                         "prilohy":[]}).encode()
            raise AssertionError("unverified pdf accessed")
        d=m.analyze(source(),now=NOW,fetch=fake,pdf_text=mock_pages)
        self.assertEqual(d["verifiedPdfCount"],0)
        self.assertEqual(len(called),2)

    def test_missing_or_nonpublic_attachment_is_unverified_not_no_profit(self):
        def empty(url,limit):
            if url.startswith(m.API):
                return json.dumps({"id":int(url.removeprefix(m.API)),
                   "idUctovnejZavierky":m.IFRS[2024][0]
                     if url.endswith(str(m.IFRS[2024][1])) else m.IFRS[2025][0],
                   "pristupnostDat":"Verejné prílohy","prilohy":[
                     {"id":456789,"mimeType":"application/pdf",
                      "velkostPrilohy":1220}]}).encode()
            raise AssertionError("attachment has no government hash; cannot fetch")
        d=m.analyze(source(),now=NOW,fetch=empty)
        self.assertTrue(all(x["status"]=="official_pdf_attachment_missing_or_hash_unavailable"
                            for x in d["reports"]))
        self.assertFalse(d["dividendPaymentToParentVerified"])

    def test_wrong_slovak_sales_company_and_mismatched_report_do_not_enter(self):
        for field,value in (("ico","35942894"),("officialEntityId",12345),
                            ("companyIdentityVerified",False)):
            obj=source();obj[field]=value
            with self.assertRaises(ValueError):
                m.analyze(obj,now=NOW,fetch=mock_source,pdf_text=mock_pages)
        obj=source()
        obj["statements"][0]["reportIds"]=[12345]
        d=m.analyze(obj,now=NOW,fetch=mock_source,pdf_text=mock_pages)
        self.assertEqual(d["reportCount"],1)

    def test_scanned_pdf_no_searchable_text_is_not_no_dividends(self):
        d=m.analyze(source(),now=NOW,fetch=mock_source,pdf_text=lambda pdf:[""," \n"])
        self.assertEqual(d["verifiedPdfCount"],2)
        self.assertEqual(d["verifiedPageExcerpts"],0)
        self.assertEqual(d["reports"][0]["status"],
                         "verified_pdf_no_indexed_words_not_proof_of_no_dividend")

    def test_download_url_not_user_constructible(self):
        for url in ("https://evil.example/attachment/1000",
                    "https://registeruz.sk/cruz-public/api/uctovny-vykaz?id=../../etc/passwd",
                    m.ATTACHMENTS+"../../private"):
            with self.assertRaises(ValueError):
                m.get_data(url,1000)

if __name__=="__main__":unittest.main()
