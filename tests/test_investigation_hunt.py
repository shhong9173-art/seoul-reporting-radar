"""The senior's hunt: changes require identical named DART rows; no exclusives."""
import sys
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import investigation_hunt as hunt

KST=timezone(timedelta(hours=9))
R1="20260316000940"
R2="20260814003228"
R0="20250314002345"
NOW=datetime(2026,10,13,tzinfo=KST)


def tbl(name,period,cost,unit="백만원",detail="건물 外",purpose="생산능력확충"):
    return {"topic":"investment","unit":unit,"receiptNo":"unused",
            "context":"아. 설비의 신설ㆍ매입 계획 등 1) 진행중인 투자 (단위 : 백만원)",
            "rows":[[name,period,detail,purpose,cost,"20,000(3,000)","1,000"]]}


def datasets():
    projects=[
        ("청주 배전캠퍼스 신축(*)","'23.05~'26.06","118,473","'23.05~'26.12","116,563"),
        ("변압기 철심공장","'22.10~'26.01","35,091","'22.10~'26.11","35,056"),
        ("중저압차단기 자동화설비","'24.01~'26.05","21,453","'24.01~'26.10","19,602"),
    ]
    old_table=tbl(*projects[0][:3])
    old_table["rows"]=[]
    new_table=tbl(*projects[0][:3])
    new_table["rows"]=[]
    for n,old_time,old_cost,new_time,new_cost in projects:
        old_table["rows"].append(tbl(n,old_time,old_cost)["rows"][0])
        new_table["rows"].append(tbl(n,new_time,new_cost)["rows"][0])
    first=tbl("변압기 철심공장","'22.10~'25.04","33,719")
    first["rows"].append(tbl("중저압차단기 자동화설비","'24.01~'25.12","22,080")["rows"][0])
    annual_company={"company":"HD현대일렉트릭","periods":{
        "2024":{"status":"evidence_found","receiptNo":R0,"tables":[first]},
        "2025":{"status":"evidence_found","receiptNo":R1,"year":2025,
                "published":"20260316","tables":[old_table]}}}
    recent_company={"company":"HD현대일렉트릭",
        "current":{"status":"evidence_found","receiptNo":R2,
                   "year":2026,"period":"06","periodLabel":"반기","published":"20260814",
                   "tables":[new_table]}}
    return annual_company,recent_company


class HuntTests(unittest.TestCase):
    def test_three_realistic_plan_revisions_are_verified(self):
        old,new=datasets()
        out=hunt.check_company("HD현대일렉트릭",old,new)
        self.assertEqual(out["status"],"changed_in_official_reports")
        self.assertEqual(len(out["updates"]),3)
        changes={row["project"]:row for row in out["updates"]}
        self.assertEqual(changes["청주 배전캠퍼스 신축(*)"]["endMonthShift"],6)
        self.assertEqual(changes["변압기 철심공장"]["endMonthShift"],10)
        self.assertEqual(changes["중저압차단기 자동화설비"]["endMonthShift"],5)
        self.assertEqual(changes["청주 배전캠퍼스 신축(*)"]["budgetChangeMillionWon"],"-1910")

    def test_longitudinal_multiple_reporting_years(self):
        old,new=datasets()
        out=hunt.check_company("HD현대일렉트릭",old,new)
        changes={row["project"]:row for row in out["updates"]}
        self.assertEqual(changes["변압기 철심공장"]["history2024"]["plannedEnd"],"2025.04")
        self.assertEqual(changes["변압기 철심공장"]["history2024"]["firstToAnnualMonths"],9)

    def test_does_not_claim_construction_delay_or_unreported_exclusive(self):
        old,new=datasets()
        packet=hunt.desk_packet(hunt.check_company("HD현대일렉트릭",old,new),NOW)
        self.assertIn("확인되지",packet["angleConditional"])
        self.assertIn("실제 준공/가동",str(packet["deskChecks"]))
        self.assertIn("발제 미확정",packet["deskVerdict"])
        self.assertEqual(packet["reporterStatus"],"과거·날짜 미확인 원문 참고")
        self.assertFalse(packet["recentOfficialPublication"])
        self.assertEqual(len(packet["publicFactQuestions"]),3)
        self.assertTrue(all(q["sourceUrls"] for q in packet["publicFactQuestions"]))

    def test_freshness_requires_actual_publication_and_matching_receipt(self):
        old,new=datasets()
        group=hunt.check_company("HD현대일렉트릭",old,new)
        for row in group["updates"]:
            row["toPublished"]="20261012"
            row["currentReceipt"]="20261012000001"
        self.assertTrue(hunt.desk_packet(group,NOW)["recentOfficialPublication"])
        for invalid in (None,"20261014","20260230","20261011"):
            for row in group["updates"]:row["toPublished"]=invalid
            self.assertFalse(hunt.desk_packet(group,NOW)["recentOfficialPublication"])

    def test_different_project_scope_does_not_pair(self):
        old,new=datasets()
        new["current"]["tables"][0]["rows"][0][3]="연구개발 능력 향상"
        group=hunt.check_company("HD현대일렉트릭",old,new)
        self.assertEqual(len(group["updates"]),2)

    def test_no_prior_source_makes_no_claim(self):
        old,new=datasets()
        old["periods"]["2025"]["receiptNo"]=None
        group=hunt.check_company("HD현대일렉트릭",old,new)
        self.assertEqual(group["updates"],[])
        self.assertEqual(group["status"],"not_comparable")

    def test_mixed_currency_units_do_not_pair(self):
        old,new=datasets()
        new["current"]["tables"][0]["unit"]="천USD"
        group=hunt.check_company("HD현대일렉트릭",old,new)
        self.assertEqual(group["updates"],[])

    def test_shift_without_total_change_is_still_reported(self):
        old,new=datasets()
        new["current"]["tables"][0]["rows"][0][4]="118,473"
        result=hunt.check_company("HD현대일렉트릭",old,new)
        project=next(r for r in result["updates"] if r["project"]=="청주 배전캠퍼스 신축(*)")
        self.assertEqual(project["budgetChangeMillionWon"],"0")
        self.assertEqual(project["endMonthShift"],6)

    def test_same_name_repeated_in_different_rows_is_ambiguous(self):
        old,new=datasets()
        new["current"]["tables"][0]["rows"].append(
            new["current"]["tables"][0]["rows"][0][:])
        result=hunt.check_company("HD현대일렉트릭",old,new)
        self.assertEqual(len(result["updates"]),2)

    def test_source_date_revisions_are_not_new_building(self):
        self.assertEqual(hunt.investment_period("'23.05~'26.12")["endLabel"],"2026.12")
        self.assertIsNone(hunt.investment_period("2025년 7월~2028년 6월"))
        self.assertIsNone(hunt.investment_period("not a period"))

    def test_generic_factory_without_specific_project_rejected(self):
        generic=tbl("미국공장","'23.05~'26.12","6,114")
        self.assertEqual(hunt.by_project([generic]),{})

    def test_googlerss_fulltext_match_is_not_same_project_confirmation(self):
        xml=b'<rss><channel><item><title>HD Hyundai industry rally</title><link>https://news.google.com/rss/articles/abc</link><pubDate>Mon, 12 Oct 2026 06:00:00 GMT</pubDate></item></channel></rss>'
        result=hunt.targeted_press_search({"company":"HD현대일렉트릭",
                  "rowIdentity":["변압기 철심공장"]},fetch=lambda _:xml)
        self.assertEqual(result["titleMatchedCount"],0)
        self.assertFalse(result["articles"][0]["companyAndProjectInTitle"])
        self.assertIn("동일 사업명 제목 일치 미확인",result["status"])

    def test_company_and_named_factory_both_in_title_still_not_same_event_proof(self):
        xml=('<rss><channel><item><title>HD현대일렉트릭 변압기 철심공장 투자</title>'
             '<link>https://news.google.com/rss/articles/abc</link></item></channel></rss>').encode("utf-8")
        result=hunt.targeted_press_search({"company":"HD현대일렉트릭",
                   "rowIdentity":["변압기 철심공장"]},fetch=lambda _:xml)
        self.assertEqual(result["titleMatchedCount"],1)
        self.assertTrue(result["articles"][0]["companyAndProjectInTitle"])
        self.assertIn("변경 숫자는 미검증",result["articles"][0]["matchStatus"])

    def test_one_preexisting_press_article_is_not_exclusive_proof(self):
        old,new=datasets()
        annual={"reportYear":2025,"generatedAt":"old","companies":[old]}
        recent={"businessYear":2026,"generatedAt":"now","companies":[new]}
        calls=[]
        def news(query):
            calls.append(query)
            return {"status":"관련 보도 후보 발견: 동일 사건 여부 미확인",
                    "articles":[{"title":"관련 기사", "url":"https://news.google.com/rss/articles/abc"}]}
        result=hunt.build(annual,recent,now=NOW,fetch_news=news,news_limit=2)
        self.assertEqual(result["verifiedChangeCount"],3)
        self.assertEqual(result["investigationCount"],1)
        self.assertEqual(result["scoopConfirmed"],0)
        self.assertEqual(len(calls),2)
        self.assertIn("직접 확인",result["investigations"][0]["projects"][0]["coverage"]["decision"])

    def test_input_year_mismatch_must_fail(self):
        with self.assertRaises(ValueError):
            hunt.build({"reportYear":2024,"companies":[]},
                       {"businessYear":2026,"companies":[]},now=NOW)

    def test_wrong_corp_not_in_whitelist(self):
        old,new=datasets()
        old["company"]="삼성전기"
        annual={"reportYear":2025,"companies":[old]}
        recent={"businessYear":2026,"companies":[new]}
        result=hunt.build(annual,recent,now=NOW)
        self.assertEqual(result["investigationCount"],0)

    def test_an_unchanged_report_suppresses_the_project(self):
        old,new=datasets()
        new["current"]["tables"][0]["rows"]=[
            row.copy() for row in old["periods"]["2025"]["tables"][0]["rows"]]
        result=hunt.check_company("HD현대일렉트릭",old,new)
        self.assertEqual(result["updates"],[])
        self.assertEqual(result["status"],"no_supported_changes")


if __name__=="__main__":
    unittest.main()
