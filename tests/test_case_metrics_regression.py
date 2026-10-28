"""2026-10-28 운영 오분류: 실제 DART 표 발췌와 별개 소송 회귀 검증."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import business_content as b
import recent_metric_hunt as m
import recent_business_scout as r
import scoop_screen as s


class Regression(unittest.TestCase):
    def test_real_ls_tables_ignore_previous_company_footnote(self):
        docs=[]
        for year,receipt in [(2025,"20250814001952"),(2026,"20260814003088")]:
            text=(Path(__file__).parent/"fixtures"/f"ls-ev-relay-{year}.html").read_text(encoding="utf-8")
            tables=b.evidence_tables(text,receipt)
            self.assertEqual([t["topic"] for t in tables],["productionCapacity","productionActual"])
            self.assertTrue(all(t["reportingEntity"]=="LS이모빌리티솔루션" for t in tables))
            docs.append(dict(status="evidence_found",year=year,period="06",receiptNo=receipt,tables=tables))
        result=m.evaluate({"companies":[dict(company="엘에스일렉트릭",status="official_sections_retrieved",priorSamePeriod=docs[0],current=docs[1])]})
        self.assertEqual({x["topic"]:x["percentChange"] for x in result["items"]},{"productionCapacity":49.07,"productionActual":42.37})
        self.assertTrue(all(x["unit"]=="백만원" for x in result["items"]))
        self.assertEqual(result["scoopConfirmed"],0)

    def test_different_subsidiaries_never_share_row_identity(self):
        table={"topic":"productionCapacity","unit":"대","rows":[["제품","현재","전기","전전기"],["부품","100","90","80"]]}
        self.assertNotEqual(set(m.rows([{**table,"reportingEntity":"A"}])),set(m.rows([{**table,"reportingEntity":"B"}])))

    def test_ambiguous_heading_and_footnote_are_not_topics(self):
        table='<TABLE><TR><TD>제품</TD><TD>100</TD></TR></TABLE>'
        self.assertEqual(b.evidence_tables('<P>주) 생산실적/회수율</P>'+table,'x'),[])
        self.assertEqual(b.evidence_tables('<P>생산능력 및 생산실적</P>'+table,'x'),[])

    def test_old_parser_cache_must_refetch_same_receipts(self):
        current=dict(receiptNo="20260814003088",period="06",year=2026,status="evidence_found",published="20260814")
        prior=dict(receiptNo="20250814001952",period="06",year=2025,status="evidence_found",published="20250814")
        cache=dict(corpCode="00105873",status="official_sections_retrieved",current=current,priorSamePeriod=prior)
        calls=[]
        def fetch(key,receipt):
            calls.append(receipt)
            return dict(status="found",section="",document="x")
        out=r.scan_company("엘에스일렉트릭","00105873","test",2026,list_fetch=lambda k,c,y:[current if y==2026 else prior],doc_fetch=fetch,cache_record=cache)
        self.assertEqual(len(calls),2)
        self.assertFalse(out.get("cacheHit"))

    def candidate(self):
        return dict(company="고려아연",title="소송등의판결",terms=["주주대표소송","기각"],numbers=[],filing=dict(type="소송판결",facts=[["사건번호","2025가합10683"],["원고ㆍ신청인","원고: 주식회사 한국기업투자홀딩스 원고공동소송참가인: 주식회사 엠제이파트너스"]]))

    def judge(self,title,c=None):
        channels={k:dict(status="ok",items=[dict(title=title,date="2026-10-22",url="https://example.org/article")]) for k in ["naver","bing","google"]}
        return s.judge(c or self.candidate(),channels,now=dt.datetime(2026,10,28,tzinfo=s.KST))

    def test_different_case_number_is_not_matching_evidence(self):
        verdict,ev=self.judge("고려아연 2024가합107981 주주대표소송 기각")
        self.assertEqual(ev,[])

    def test_generic_same_day_lawsuit_remains_unknown(self):
        self.assertEqual(self.judge("고려아연 영풍 6732억 주주대표소송 기각"),("미확인",[]))

    def test_matching_case_and_multi_case_article(self):
        for title in ["고려아연 2025 가합 10683 판결", "고려아연 2024가합107981 및 2025가합10683 판결", "고려아연 한국기업투자홀딩스 지분 매각 소송 기각"]:
            self.assertEqual(self.judge(title)[0],"관련 보도 있음")

    def test_no_identity_or_source_failure_cannot_certify_absence(self):
        c=self.candidate()
        c["filing"]["error"]="원문 조회 실패"
        self.assertEqual(self.judge("무관한 기사",c),("미확인",[]))
        c["filing"]={}
        self.assertEqual(self.judge("무관한 기사",c),("미확인",[]))

    def test_queries_use_verified_case_and_plaintiff(self):
        self.assertEqual(s.queries(self.candidate()),["고려아연 2025가합10683","고려아연 한국기업투자홀딩스 소송"])

    def test_calendar_dates_are_not_case_numbers(self):
        self.assertEqual(s.case_numbers("2026년 10월 22일"),set())


if __name__=="__main__":unittest.main()
