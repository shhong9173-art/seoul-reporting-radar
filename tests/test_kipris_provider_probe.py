import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from kipris_provider_probe import probe


class ProviderProbe(unittest.TestCase):
    def test_spaced_message_is_classified_without_assuming_reset_date(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            return b'<response><header><resultCode>22</resultCode><resultMsg>Limited Number Of Service Requests Exceeds Error</resultMsg></header></response>'
        result=probe("SECRET",fetch=fetch)
        self.assertEqual(len(calls),1)
        self.assertEqual(parse_qs(urlparse(calls[0]).query)["numOfRows"],["1"])
        self.assertEqual(result["providerMessageCategory"],"request_limit_reported")
        self.assertEqual(result["status"],"provider_rejected")
        self.assertFalse(result["collectionRecovered"])
        self.assertFalse(result["accountUsageVerified"])
        self.assertNotIn("SECRET",json.dumps(result))

    def test_missing_key_does_not_call(self):
        result=probe("",fetch=lambda _:self.fail("network called"))
        self.assertEqual(result["requestsAttempted"],0)
        self.assertEqual(result["status"],"api_key_missing")

    def test_zero_response_is_only_one_query_not_complete_collection(self):
        result=probe("SECRET",fetch=lambda _:b'<response><header><resultCode>00</resultCode></header><body><totalCount>0</totalCount><items/></body></response>')
        self.assertEqual(result["reportedTotal"],0)
        self.assertEqual(result["status"],"single_query_responded")
        self.assertFalse(result["collectionRecovered"])

    def test_error_code_alone_does_not_prove_request_limit(self):
        result=probe("SECRET",fetch=lambda _:b'<response><header><resultCode>22</resultCode></header></response>')
        self.assertEqual(result["providerMessageCategory"],"unrecognized_provider_message")
        self.assertNotIn("reportedTotal",result)

    def test_invalid_response_and_secret_echo_are_not_exported(self):
        for data in (b'<html>SECRET</html>',b'broken SECRET',
                     b'<response><header><resultCode>22</resultCode><resultMsg>SECRET</resultMsg></header></response>'):
            with self.subTest(data=data):
                result=probe("SECRET",fetch=lambda _:data)
                self.assertNotIn("SECRET",json.dumps(result))
                self.assertNotIn("reportedTotal",result)

    def test_transport_error_does_not_publish_key_url(self):
        def fetch(url):raise HTTPError(url,403,"SECRET",{},None)
        result=probe("SECRET",fetch=fetch)
        self.assertEqual(result["status"],"http_error")
        self.assertEqual(result["httpStatus"],403)
        self.assertNotIn("SECRET",json.dumps(result))


if __name__=="__main__":unittest.main()
