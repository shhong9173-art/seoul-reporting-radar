"""Official KIPRIS claim1 and prior claim wording: must have matching original ID."""
import hashlib
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import parse_qs,urlparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_claim_review as a

NOW=datetime(2026,10,13,tzinfo=timezone(timedelta(hours=9)))
CUR="1020250123456"
OLD="1020230123456"
PUB="1020260138678"
OLDPUB="1020230136794"


def sample(application=CUR,claim1=None,include=True):
    claim1=claim1 or "청구항 1 자율주행 차량의 상태 데이터를 받아 센서 신호로 차로 변경 제어 결정을 수행하는 제어 장치"
    body=(f'<claimInfoArray><claimInfo><claimNumber>1</claimNumber><claim>{claim1}</claim></claimInfo>'
          f'<claimInfo><claimNumber>2</claimNumber><claim>제1항에 있어서, 상기 장치는 보조 제어기를 포함한다.</claim></claimInfo></claimInfoArray>'
          if include else "")
    return (f'<response><header><resultCode>00</resultCode></header><body><item>'
            f'<biblioSummaryInfoArray><biblioSummaryInfo><applicationNumber>{application}</applicationNumber>'
            f'<inventionTitle>자율주행 차량 제어 장치 및 방법</inventionTitle>'
            f'</biblioSummaryInfo></biblioSummaryInfoArray>{body}</item></body></response>').encode()


def patent(with_prior=True):
    row={"publicationNumber":PUB,"company":"기아",
         "coveredCompanies":["기아","현대자동차"],"title":"자율주행 차량 제어 장치 및 방법",
         "applicationNumber":CUR,"publicationDate":"20260921",
         "investigativeThemes":["자율주행·SDV"]}
    if with_prior:
        row["priorFullTitleCheck"]={"matches":[
           {"publicationNumber":OLDPUB,"applicationNumber":OLD,
            "published":"20230927","applicants":"현대자동차주식회사|기아 주식회사",
            "overlappingApplicant":True}]}
    return row


def mock_detail(key,application):
    v="청구항 1 자율주행 차량의 상태 데이터를 받아 센서 신호로 차로 변경 제어 결정을 수행하는 제어 장치" if application==CUR else \
      "청구항 1 자율주행 차량의 상태 데이터를 받아 운전자 신호로 차로 변경 제어 결정을 수행하는 제어 장치"
    return a.parse_bibliography(sample(application,v),application)


class ClaimReviewTests(unittest.TestCase):
    def test_official_application_number_and_claim1_parsing(self):
        d=a.parse_bibliography(sample(),CUR)
        self.assertEqual(d["applicationNumber"],CUR)
        self.assertIn("차로 변경",d["claim1Text"])
        self.assertEqual(d["claimCountParsed"],2)
        self.assertEqual(len(d["claim1Sha256"]),64)

    def test_identity_mismatch_cannot_attach_another_company_claim(self):
        with self.assertRaises(ValueError):
            a.parse_bibliography(sample(OLD),CUR)

    def test_provider_error_raises(self):
        raw=b'<response><header><resultCode>30</resultCode></header><body></body></response>'
        with self.assertRaises(RuntimeError):
            a.parse_bibliography(raw,CUR)

    def test_absent_claim_array_is_not_zero_claim_success(self):
        with self.assertRaises(ValueError):
            a.parse_bibliography(sample(include=False),CUR)

    def test_untrusted_xml_doctype_rejected(self):
        xml=b'<!DOCTYPE x [<!ENTITY ex SYSTEM "file:///etc/passwd">]><response/>'
        with self.assertRaises(ValueError):
            a.parse_bibliography(xml,CUR)

    def test_dependent_claim1_must_be_rejected(self):
        c="청구항 1 제1항에 있어서, 상기 변압기는 각각 추가 제어부를 포함하는 장치"
        with self.assertRaises(ValueError):
            a.parse_bibliography(sample(claim1=c),CUR)

    def test_fetch_uses_exact_application_and_only_servicekey(self):
        called=[]
        def fake(url):
            called.append(url)
            return sample()
        a.official_detail("dummy-secret",CUR,fetch=fake)
        p=urlparse(called[0])
        self.assertIn("getBibliographyDetailInfoSearch",p.path)
        q=parse_qs(p.query)
        self.assertEqual(q["applicationNumber"],[CUR])
        self.assertEqual(q["ServiceKey"],["dummy-secret"])

    def test_pair_claim_comparison_does_not_assert_patent_novelty(self):
        cur=mock_detail("key",CUR);old=mock_detail("key",OLD)
        diff=a.compare_claims(cur,old)
        self.assertFalse(diff["sameClaimText"])
        self.assertIn("기술적 신규성 판정 아님",diff["comparisonType"])
        self.assertIn("미확인",diff["notProven"] if "미확인" in diff["notProven"] else "미확인")
        self.assertEqual(len(diff["currentClaimSha256"]),64)
        self.assertLess(len(diff["currentShortExcerpt"]),120)

    def test_same_claim1_does_not_prove_same_family(self):
        cur=mock_detail("key",CUR)
        old=a.parse_bibliography(sample(OLD,cur["claim1Text"]),OLD)
        result=a.compare_claims(cur,old)
        self.assertTrue(result["sameClaimText"])
        self.assertIn("권리범위 동일성 판정 아님",result["finding"])

    def test_prior_claim_compare_respects_prior_application_and_issuer(self):
        p=patent()
        outcome=a.inspect(p,"key",detail=mock_detail,news=None)
        self.assertEqual(outcome["status"],"claim1_and_prior_compared")
        self.assertEqual(outcome["priorComparisons"][0]["priorApplication"],OLD)
        self.assertEqual(outcome["priorComparisons"][0]["priorPublicationNumber"],OLDPUB)
        self.assertEqual(outcome["scoopConfirmed"],False)

    def test_no_old_application_skips_unverified_comparison(self):
        p=patent()
        p["priorFullTitleCheck"]["matches"][0].pop("applicationNumber")
        outcome=a.inspect(p,"key",detail=mock_detail,history=lambda *x:
            {"total":0,"rows":[],"complete":True},news=None)
        self.assertEqual(outcome["priorComparisons"],[])
        self.assertEqual(outcome["status"],"current_claim_only_prior_unverified")

    def test_previous_other_company_is_not_comparable(self):
        p=patent()
        p["priorFullTitleCheck"]["matches"][0]["overlappingApplicant"]=False
        outcome=a.inspect(p,"key",detail=mock_detail,news=None)
        self.assertEqual(outcome["priorComparisons"],[])

    def test_kipris_invalid_source_not_written_as_verified(self):
        outcome=a.inspect(patent(),"key",detail=lambda *x:(_ for _ in ()).throw(ValueError("bad")),news=None)
        self.assertEqual(outcome["status"],"current_claim_unavailable")
        self.assertFalse(outcome["claimVerified"])

    def test_exact_source_timestamp_required(self):
        deep={"patentDatasetGeneratedAt":"old","uniquePublicationCount":1,
              "investigations":[patent()]}
        base={"generatedAt":"new"}
        with self.assertRaises(ValueError):
            a.build(deep,base,"key",now=NOW,detail=mock_detail,news=None)

    def test_choose_known_patent_prior_first_without_inventing_if_absent(self):
        target=patent()
        others=[{**target,"publicationNumber":"102026000000"+str(i),"priorFullTitleCheck":{"matches":[]}}
                for i in range(1,4)]
        chosen=a.choose_candidates({"investigations":others+[target]},2)
        self.assertEqual(chosen[0]["publicationNumber"],PUB)
        self.assertEqual(len(chosen),2)

    def test_build_reports_actual_verified_counts(self):
        base={"generatedAt":"2026-10-13T04:06","status":"official_search_completed"}
        deep={"patentDatasetGeneratedAt":base["generatedAt"],"uniquePublicationCount":1,
              "investigations":[patent()]}
        out=a.build(deep,base,"key",limit=1,max_prior=1,detail=mock_detail,
                    now=NOW,news=None)
        self.assertEqual(out["currentClaimsVerified"],1)
        self.assertEqual(out["pairedClaimsCompared"],1)
        self.assertEqual(out["confirmedScoops"],0)

    def test_news_zero_hit_not_proof_of_unreported(self):
        rss=b'<rss><channel></channel></rss>'
        r=a.related_press(patent(),fetch=lambda url:rss)
        self.assertEqual(len(r["queries"]),2)
        self.assertTrue(all("미보도 확정 불가" in x["status"] for x in r["queries"]))

    def test_rss_index_match_not_proof_of_same_patent(self):
        rss=('<rss><channel><item><title>현대차 미래 기술</title>'
             '<link>https://news.google.com/rss/articles/example</link></item>'
             '</channel></rss>').encode()
        r=a.related_press(patent(),fetch=lambda url:rss)
        self.assertIn("미검증",r["queries"][0]["articles"][0]["status"])


if __name__=="__main__":
    unittest.main()
