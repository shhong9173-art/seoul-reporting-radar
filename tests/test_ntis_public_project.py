import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ntis_public_project as n

NOW=datetime(2026,10,14,9,20,tzinfo=timezone(timedelta(hours=9)))
PUB="1020260147965"
MOCK_XML="""<?xml version="1.0" encoding="UTF-8"?>
<RESULT><TOTALHITS>3</TOTALHITS><RESULTSET><HIT>
<ProjectNumber>2024R1A00001</ProjectNumber>
<ProjectTitle><Korean>고정자 냉각 신기술</Korean></ProjectTitle>
<ResearchAgency><Name>기아</Name></ResearchAgency>
<ProjectYear>2024</ProjectYear>
<ProjectPeriod><Start>20240101</Start><End>20261231</End></ProjectPeriod>
<Abstract><Teaser>전기 모터의 냉각 연구</Teaser></Abstract>
<Keyword><Korean>고정자, 모터</Korean></Keyword>
</HIT></RESULTSET></RESULT>""".encode("utf-8")

def dossier():
    return {"status":"research_only","generatedAt":"2026-10-14T09:00:00+09:00",
            "dossiers":[{"publicationNumber":PUB,"publicationDate":"2026-10-12",
                         "title":"고정자 냉각 장치","recentPatentWithin3Days":True,
                         "pressLookupCompleted":True,
                         "ntisResearchQueries":[{"query":"기아 고정자"},
                                                {"query":"대학 고정자"}]}]}

class NTISTests(unittest.TestCase):
    def test_project_xml_retains_only_selected_public_metadata(self):
        a=n.parse_project_xml(MOCK_XML)
        self.assertEqual(a["totalHits"],3)
        self.assertEqual(len(a["records"]),1)
        self.assertTrue(a["firstPageOnly"])
        x=a["records"][0]
        self.assertEqual(x["projectNumber"],"2024R1A00001")
        self.assertEqual(x["performingAgency"],"기아")
        self.assertFalse(x["patentOutcomeConfirmed"])
        self.assertFalse(x["companyProjectParticipationConfirmed"])
        self.assertFalse(x["commercializationConfirmed"])
        self.assertNotIn("apprvKey",x["sourceSearchUrl"])

    def test_request_uses_authorized_params_but_result_never_leaks_secret(self):
        seen=[]
        def fake(url):
            parsed=urlsplit(url)
            q=parse_qs(parsed.query,keep_blank_values=True)
            seen.append(q)
            return MOCK_XML
        r=n.request_xml("기아 고정자","TEST-KEY-SECRET",fetch=fake)
        self.assertEqual(seen[0]["apprvKey"],["TEST-KEY-SECRET"])
        self.assertEqual(seen[0]["collection"],["project"])
        self.assertEqual(seen[0]["SRWR"],["기아 고정자"])
        self.assertNotIn("TEST-KEY-SECRET",str(r))
        self.assertEqual(len(r["records"]),1)

    def test_missing_key_is_explicit_not_zero_hit(self):
        a=n.collect(dossier(),None,now=NOW)
        self.assertEqual(a["status"],"missing_key")
        self.assertEqual(a["completedQueries"],0)
        self.assertEqual(a["remainingQueries"],2)
        self.assertEqual(a["checks"],[])

    def test_html_auth_response_is_not_false_zero(self):
        for content in [b"<html>403 Forbidden</html>",
                        b"<RESULT><ERROR>Invalid IP</ERROR></RESULT>",
                        b"<RESULT><TOTALHITS>0</TOTALHITS></RESULTSET></RESULT>",
                        b"<!DOCTYPE html><RESULT><TOTALHITS>0</TOTALHITS><RESULTSET/></RESULT>"]:
            with self.assertRaises(ValueError):
                n.parse_project_xml(content)
        err=n.collect(dossier(),"secret",now=NOW,max_queries=1,
                      search=lambda q,k:n.parse_project_xml(b"<html>access denied</html>"))
        self.assertEqual(err["status"],"partial_errors")
        self.assertEqual(err["failedQueries"],1)
        self.assertEqual(err["remainingQueries"],1)
        self.assertNotIn("secret",str(err))

    def test_valid_empty_xml_is_zero_only_for_confirmed_total_hits(self):
        xml=b"<RESULT><TOTALHITS>0</TOTALHITS><RESULTSET></RESULTSET></RESULT>"
        result=n.parse_project_xml(xml)
        self.assertEqual(result["totalHits"],0)
        self.assertEqual(result["records"],[])

    def test_disallow_unsafe_xml_and_unknown_schema_with_hits(self):
        with self.assertRaises(ValueError):
            n.parse_project_xml(b"<!DOCTYPE foo [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><RESULT/>")
        with self.assertRaises(ValueError):
            n.parse_project_xml(b"<RESULT><TOTALHITS>4</TOTALHITS><RESULTSET><HIT><Wrong/></HIT></RESULTSET></RESULT>")
        with self.assertRaises(ValueError):
            n.parse_project_xml(b"x"*(n.MAX_XML+1))

    def test_safe_caching_advances_to_unsearched_query(self):
        called=[]
        def fake(q,k):
            called.append(q)
            return {"totalHits":3,"firstPageOnly":True,"records":[{"projectNumber":"R-12","projectTitle":"가상 과제"}]}
        a=n.collect(dossier(),"secret",now=NOW,max_queries=1,search=fake)
        self.assertEqual(a["status"],"partial_not_yet_checked")
        b=n.collect(dossier(),"secret",previous=a,now=NOW+timedelta(hours=1),
                    max_queries=1,search=fake)
        self.assertEqual(called,["기아 고정자","대학 고정자"])
        self.assertEqual(b["completedQueries"],2)
        self.assertEqual(b["status"],"ready")
        self.assertEqual(b["projectPatentLinksConfirmed"],0)
        c=n.collect(dossier(),"secret",previous=b,now=NOW+timedelta(hours=21),
                    max_queries=1,search=fake)
        self.assertEqual(c["newQueriesThisRun"],1)

    def test_queries_not_speculative_or_unbounded(self):
        data=dossier()
        data["dossiers"][0]["ntisResearchQueries"] += [{"query":"추가 예제"}]
        self.assertEqual(len(n.plan_queries(data)),2)
        with self.assertRaises(ValueError):
            n.collect(data,"secret",max_queries=n.MAX_QUERIES+1)
        data["status"]="unknown"
        with self.assertRaises(ValueError):n.plan_queries(data)

    def test_network_error_not_exposed_with_api_key(self):
        from urllib.error import URLError
        def fail(q,k):raise URLError("https://url-with-secret/?apprvKey=SECRET")
        result=n.collect(dossier(),"SECRET",now=NOW,max_queries=1,search=fail)
        self.assertEqual(result["checks"][0]["errorClass"],"network_or_ip_allowlist")
        self.assertNotIn("SECRET",str(result))


if __name__=="__main__":unittest.main()
