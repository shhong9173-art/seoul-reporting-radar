import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import parse_qs,urlparse

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import patent_deep_hunt as d
import patent_hunt as p

KST=timezone(timedelta(hours=9))
NOW=datetime(2026,10,13,tzinfo=KST)


def patent(company="현대자동차",number="1020260148128",
           title="하이브리드 차량 제어 장치 및 방법, 및 이를 포함하는 하이브리드 차량"):
    return {"company":company,"title":title,"publicationNumber":number,
            "publicationDate":"20261012","abstract":"하이브리드 차량의 모터 구동 제어를 수행하도록 장치가 구성된다. "*5,
            "applicationNumber":"1020250100000","applicationDate":"20250412",
            "registerStatus":"공개","themes":[{"theme":"자율주행·SDV","titleHits":["차량제어"],"abstractHits":[]}],
            "applicants":["현대자동차주식회사","기아 주식회사"],
            "previouslyObserved":True,"initialBaseline":False}


class PatentDeepTests(unittest.TestCase):
    def test_three_company_cross_sector_joint_patent_exposes_outside_partner(self):
        first=patent(title="폐차 플라스틱 효소 해중합 및 재생 원료 제조 방법")
        first["applicants"]=["현대자동차주식회사","기아 주식회사","씨제이제일제당 주식회사"]
        first["themes"]=[{"theme":"순환소재·폐차재활용","titleHits":["플라스틱"],"abstractHits":["효소"]}]
        other={**first,"company":"기아"}
        output=d.build({"items":[first,other],"generatedAt":"2026-10-13"},search_limit=0,now=NOW)
        self.assertEqual(output["uniquePublicationCount"],1)
        self.assertEqual(output["jointApplications"],1)
        self.assertEqual(output["outsideBeatJointPublications"],1)
        lead=output["partnerInvestigations"][0]
        self.assertEqual(lead["outsideBeatCoApplicants"],["씨제이제일제당 주식회사"])
        self.assertEqual(lead["officialApplicantCount"],3)
        self.assertIn("순환소재·폐차재활용",lead["investigativeThemes"])
        self.assertIn("미확인",lead["partnerStatus"])
        self.assertEqual(output["confirmedScoops"],0)


    def test_all_external_joint_patents_are_preserved_in_investigation_data(self):
        originals=[]
        for i in range(45):
            row=patent(number="10"+str(20260140000+i).zfill(11))
            row["applicants"]=["현대자동차주식회사","기아 주식회사","부산대학교 산학협력단"]
            originals.append(row)
        result=d.build({"items":originals,"generatedAt":"2026-10-13T08:00:00+09:00"},search_limit=0,now=NOW)
        self.assertEqual(result["outsideBeatJointPublications"],45)
        self.assertEqual(len(result["partnerInvestigations"]),45)
        self.assertEqual(result["confirmedScoops"],0)

    def test_same_group_hyundai_and_kia_not_outside_collaboration(self):
        base=patent()
        output=d.build({"items":[base],"generatedAt":"2026-10-13"},search_limit=0,now=NOW)
        self.assertEqual(output["outsideBeatJointPublications"],0)
        self.assertEqual(output["partnerInvestigations"],[])
        self.assertEqual(output["jointApplications"],1)

    def test_outside_partner_does_not_mistake_covered_corporate_alias(self):
        self.assertEqual(d.outside_beat_applicants(
            ["현대자동차 주식회사","기아주식회사","인천대학교 산학협력단"]),
            ["인천대학교 산학협력단"])

    def test_joint_patent_is_one_document_not_two_exclusives(self):
        source={"items":[patent(),patent(company="기아")],"generatedAt":"2026-10-13T03:39"}
        results=d.build(source,search_limit=0,now=NOW)
        self.assertEqual(results["inputPatents"],2)
        self.assertEqual(results["uniquePublicationCount"],1)
        self.assertEqual(results["jointApplications"],1)
        self.assertEqual(results["investigations"][0]["coveredCompanies"],["기아","현대자동차"])
        self.assertEqual(results["confirmedScoops"],0)

    def test_different_titles_for_same_pub_number_fail_closed(self):
        src={"items":[patent(),patent(company="기아",title="완전 다른 특허 발명")]}
        rows,invalid=d.merge_publications(src)
        self.assertEqual(rows,[])
        self.assertEqual(invalid,["1020260148128"])

    def test_car_hybrid_not_sd_vehicle_and_not_hvdc(self):
        row=patent()
        row["themes"].append({"theme":"전력망·HVDC","titleHits":[],"abstractHits":["dc/dc"]})
        tags=d.accurate_topics(row)
        self.assertIn("차량 제어·파워트레인(자율주행 미확정)",tags)
        self.assertFalse(any("HVDC" in t for t in tags))
        self.assertNotIn("자율주행·SDV",tags)

    def test_actual_autonomous_title_signaled(self):
        row=patent(title="자율 주행 차량을 위한 라이다 센서융합 방법")
        self.assertIn("자율주행·SDV",d.accurate_topics(row))

    def test_transformer_is_power_industrial_not_auto(self):
        row=patent(company="HD현대일렉트릭",
              title="선박 축발전기용 몰드변압기 냉각 에어가이드")
        self.assertIn("전력망·전력기기(용도 검증 필요)",d.accurate_topics(row))

    def test_similar_recent_patents_are_related_not_a_patent_family(self):
        a=patent(title="전기자동차 배터리 팩 제어 장치")
        b=patent(number="1020260148129",title="전기자동차 배터리 팩 제어 방법")
        rows,_=d.merge_publications({"items":[a,b]})
        d.relate(rows,threshold=0.35)
        self.assertGreater(len(rows[0]["relatedRecent"]),0)
        self.assertNotIn("familyId",rows[0])
        self.assertIn("청구항",rows[0]["techNoveltyStatus"])

    def test_actual_older_same_title_is_only_title_match(self):
        current=patent()
        response={"rows":[{"openNumber":"1020240123456",
                           "openDate":"20240611",
                           "inventionTitle":current["title"],
                           "applicantName":"기아주식회사"}],
                 "total":1,"complete":True,
                 "queryFields":{"title":current["title"]}}
        result=d.historical_summary({**current,"coveredCompanies":["기아","현대자동차"]},response)
        self.assertEqual(len(result["matches"]),1)
        self.assertTrue(result["matches"][0]["overlappingApplicant"])
        self.assertIn("청구항",result["status"])
        self.assertEqual(result["claimComparison"].startswith("미조회"),True)

    def test_zero_same_title_not_first_of_kind(self):
        result=d.historical_summary({**patent(),"coveredCompanies":["현대자동차"]},
                                    {"rows":[],"total":0,"complete":True})
        self.assertIn("다른 명칭의 선행기술은 검증 전",result["status"])

    def test_historical_api_key_last_and_dates_limited(self):
        urls=[]
        def fake(url):
            urls.append(url)
            return b"<response><header><resultCode>00</resultCode></header><body><count><totalCount>0</totalCount></count><items /></body></response>"
        out=d.historical_title_search("fake-key","변압기 냉각 에어가이드","20261011",fetch=fake)
        query=parse_qs(urlparse(urls[0]).query)
        self.assertEqual(query["inventionTitle"],["변압기 냉각 에어가이드"])
        self.assertEqual(query["openDate"],["20230101~20261011"])
        self.assertEqual(query["ServiceKey"],["fake-key"])
        self.assertTrue(out["complete"])

    def test_hist_error_not_misreported_as_unique_invention(self):
        row=patent()
        def bad(*a):raise ValueError("provider down")
        result=d.build({"items":[row],"generatedAt":"time"},key="key",
                       historical=bad,search_limit=1,now=NOW)
        item=result["investigations"][0]
        self.assertIn("오류",item["priorFullTitleCheck"]["status"])
        self.assertIn("미검증",item["priorFullTitleCheck"]["claimComparison"])
        self.assertEqual(result["confirmedScoops"],0)

    def test_historical_search_only_top_limit(self):
        rows=[patent(number=f"1020260148{i:03d}",title=f"자율 주행 제어 방법 제{i}형") for i in range(6)]
        calls=[]
        def fake(key,title,cutoff):
            calls.append(title)
            return {"rows":[],"total":0,"complete":True}
        result=d.build({"items":rows,"generatedAt":"time"},key="key",historical=fake,
                       search_limit=2,now=NOW)
        self.assertEqual(len(calls),2)
        self.assertEqual(result["historicalQueriesAttempted"],2)

    def test_research_budget_diversified_across_issuer_groups(self):
        items=[]
        for index in range(8):
            a=patent(number=f"1020260123{index:03d}",
                      title=f"자율주행 차량 센서 AI 제어 시스템 제{index}형")
            a["newsroomScore"]=70
            a["coveredCompanies"]=["기아","현대자동차"]
            items.append(a)
        power=patent(company="HD현대일렉트릭",number="1020260147348",
                     title="선박 축발전기용 몰드변압기 냉각 에어가이드")
        power["newsroomScore"]=55
        power["coveredCompanies"]=["HD현대일렉트릭"]
        items.append(power)
        ordered=d.balance_issuers(items)
        self.assertEqual(ordered[0]["coveredCompanies"],["기아","현대자동차"])
        self.assertEqual(ordered[1]["coveredCompanies"],["HD현대일렉트릭"])
        self.assertEqual(len(ordered),len(items))

    def test_historical_lookups_reach_power_and_auto_not_just_joint_filers(self):
        items=[]
        for index in range(8):
            a=patent(number=f"1020260123{index:03d}",
                     title=f"자율주행 차량 센서 AI 제어 시스템 제{index}형")
            items.append(a)
        items.append(patent(company="HD현대일렉트릭",number="1020260147348",
                            title="선박 축발전기용 몰드변압기 냉각 에어가이드"))
        calls=[]
        def fake(key,title,cutoff):
            calls.append(title)
            return {"rows":[],"total":0,"complete":True}
        report=d.build({"items":items,"generatedAt":"test"},key="key",
                       historical=fake,search_limit=2,now=NOW)
        self.assertEqual(len(calls),2)
        self.assertTrue(any("변압기" in x for x in calls))

    def test_empty_or_bad_source_fails(self):
        with self.assertRaises(ValueError):
            d.build({"items":None},now=NOW)

    def test_no_key_does_not_claim_historical_novelty(self):
        result=d.build({"items":[patent()],"generatedAt":"test"},now=NOW)
        self.assertEqual(result["historicalQueriesAttempted"],0)
        self.assertEqual(result["investigations"][0]["priorFullTitleCheck"]["status"],"미검색")


if __name__=="__main__":
    unittest.main()
