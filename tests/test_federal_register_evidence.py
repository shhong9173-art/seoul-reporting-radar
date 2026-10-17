import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import federal_register_evidence as f

ROW={'source':'US Federal Register','sourceId':'2026-20699','published':'2026-10-08',
     'sourceUrl':'https://www.federalregister.gov/documents/2026/10/08/2026-20699/steel'}
META={'document_number':ROW['sourceId'],'publication_date':ROW['published'],'html_url':ROW['sourceUrl'],
      'body_html_url':'https://www.federalregister.gov/documents/full_text/html/2026/10/08/2026-20699.html'}

def request(url):
    if url.endswith('.json'):return json.dumps(META).encode()
    return ('<p>Official notice with a sufficiently long introduction. This table identifies named respondents but does not prove the impact on sales.</p>'
            '<table><tr><td>Hyundai Steel Company</td><td>3.50</td></tr></table>').encode()

class Tests(unittest.TestCase):
    def test_original_row_is_retained_without_inferred_duties(self):
        d=f.inspect(ROW,request)
        self.assertEqual(d['companiesMentioned'],['현대제철'])
        self.assertIn('3.50',d['evidence'][0]['text'])
        self.assertFalse(d['confirmedScoop'])
        self.assertFalse(d['companyImpactVerified'])
    def test_mismatched_document_never_becomes_evidence(self):
        for key,value in [('document_number','2026-00000'),('publication_date','2026-10-09'),
                          ('body_html_url','https://evil.invalid/body'),('html_url','https://evil.invalid/')]:
            meta={**META,key:value}
            with self.assertRaises(ValueError):f.inspect(ROW,lambda u:json.dumps(meta).encode())
    def test_failure_is_unknown_not_zero(self):
        d=f.build({'generatedAt':'2026-10-17','documents':[ROW]},lambda u:(_ for _ in ()).throw(OSError()))
        self.assertEqual(d['status'],'incomplete')
        self.assertIsNone(d['companyMentionDocumentCount'])
        self.assertEqual(d['failedDocuments'],1)
    def test_company_identity_and_script_text(self):
        self.assertEqual(f.companies('Hyundai Motor North America'),[])
        self.assertEqual(f.companies('Hyundai Motor Company'),['현대자동차'])
        self.assertEqual(f.companies('POSCO Holdings and POSCO International'),['포스코홀딩스'])
        self.assertEqual(f.companies('POSCO Future M'),[])
        self.assertEqual(f.companies('POSCO and Hyundai Steel Company'),['현대제철','포스코'])
        p=f.Blocks();p.feed('<script>Hyundai Steel</script><p>normal text</p>');p.flush()
        self.assertNotIn('Hyundai',str(p.blocks))
    def test_duplicate_and_missing_source(self):
        d=f.build({'generatedAt':'2026-10-17','documents':[ROW,ROW]},request)
        self.assertEqual(len(d['items']),1)
        self.assertEqual(f.build({})['status'],'incomplete')
        self.assertEqual(f.build([])['status'],'incomplete')
        out=f.build({'generatedAt':'2026-10-17','documents':[ROW]},lambda u:b'[]')
        self.assertIsNone(out['companyMentionDocumentCount'])
    def test_budget_reports_unqueried(self):
        rows=[{**ROW,'sourceId':f'2026-{20000+i}'} for i in range(9)]
        d=f.build({'generatedAt':'2026-10-17','documents':rows},request)
        self.assertEqual(d['unqueriedDocuments'],1)
        self.assertIsNone(d['companyMentionDocumentCount'])

if __name__=='__main__':unittest.main()
