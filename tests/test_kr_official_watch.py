"""Domestic official watch: factory registry parsing (real XML layout), affiliate filtering, change events, paging,
gazette legislative notice filtering, failures kept as failures."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_official_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 8, 10, tzinfo=KST)
CFG = {"companies": [
    {"company": "포스코", "queries": ["포스코"], "accept": "^포스코(?:\\S{0,8}(?:제철소|공장|사업장|연구소))?$"},
    {"company": "현대차", "queries": ["현대자동차"], "accept": "^현대자동차(?!써비스|정비|판매|부품)"},
]}


def fac(no, name, addr="경상북도 포항시 남구 동해안로 6261", emp="9000", reg="19730703", product="열연강판", induty="제철업"):
    return {"fctryManageNo": no, "cmpnyNm": name, "rnAdres": addr, "rprsntvNm": "대표", "cvplChrgOrgnztNm": "경상북도 포항시",
            "allEmplyCo": emp, "frstFctryRegistDe": reg, "indutyNm": induty, "mainProductCn": product, "rprsntvIndutyCode": "24111", "irsttNm": ""}


def xml(items, total=None, code="00"):
    # Same element names and order as the live response on 2026-10-26 (XML even with type=json).
    body = "".join("<item>" + "".join(f"<{k}>{v}</{k}>" for k, v in it.items()) + "</item>" for it in items)
    return (f"<response><header><resultCode>{code}</resultCode><resultMsg>NORMAL_SERVICE</resultMsg></header><body><items>{body}</items>"
            f"<numOfRows>100</numOfRows><pageNo>1</pageNo><totalCount>{len(items) if total is None else total}</totalCount></body></response>")


POSCO = [fac("1", "(주)포스코 포항제철소"), fac("2", "주식회사 포스코퓨처엠", product="양극재"), fac("3", "포스코인터내셔널(주)"),
         fac("4", "(주)포스코 광양제철소", addr="전라남도 광양시 폭포사랑길 20-26", emp="7000")]
HYUNDAI = [fac("10", "현대자동차(주)아산공장", addr="충청남도 아산시 인주면 현대로 1077", emp="4000", product="승용차", induty="승용차 제조업"),
           fac("11", "현대자동차써비스(주)", product="정비")]
GAZETTE = {"response": {"pageNo": "1", "resultCode": "0", "pageSize": "100", "totalCount": "3", "items": {"item": [
    {"pdfFilePath": "/ezpdf/customLayout.jsp?contentId=A&tocId=B&isTocOrder=N", "rvsnRsnMainCn": "", "crtnYn": "아니오", "hopePblictDt": "2026.10.26",
     "cmplatSeNm": "공고", "cntntSeqNo": "I1", "pblcnInstNm": "교육부", "basisLawNm": "행정절차법 제42조", "ofcttBookNm": "정호", "themaSe": "01",
     "cntntSj": "교육부공고제2026-402호(「법학전문대학원 설치 운영에 관한 법률 시행령」일부개정령안 입법예고)"},
    {"pdfFilePath": "/ezpdf/customLayout.jsp?contentId=C&tocId=D&isTocOrder=N", "rvsnRsnMainCn": "", "crtnYn": "아니오", "hopePblictDt": "2026.10.24",
     "cmplatSeNm": "공고", "cntntSeqNo": "I2", "pblcnInstNm": "국토교통부", "basisLawNm": "행정절차법 제42조", "ofcttBookNm": "정호", "themaSe": "01",
     "cntntSj": "국토교통부공고제2026-1500호(「자동차관리법 시행규칙」일부개정령안 입법예고)"},
    {"pdfFilePath": "/ezpdf/customLayout.jsp?contentId=E&tocId=F&isTocOrder=N", "rvsnRsnMainCn": "전력망 확충을 위해 송전선로 인허가 절차를 개선함",
     "crtnYn": "아니오", "hopePblictDt": "2026.10.23", "cmplatSeNm": "공고", "cntntSeqNo": "I3", "pblcnInstNm": "기후에너지환경부",
     "basisLawNm": "행정절차법 제42조", "ofcttBookNm": "정호", "themaSe": "01", "cntntSj": "기후에너지환경부공고제2026-77호(「국가기간 전력망 확충 특별법 시행령」 제정령안 입법예고)"},
]}}}


class R:
    def __init__(self, code=200, text=""):
        self.status_code, self.text = code, text


def fake(posco=POSCO, hyundai=HYUNDAI, factory_code=200, gazette_code=200, calls=None):
    def get(url, params=None, headers=None, timeout=None):
        if calls is not None:
            calls.append((url, dict(params)))
        if url == w.FACTORY_API:
            if factory_code != 200:
                return R(factory_code)
            rows = posco if params["cmpnyNm"] == "포스코" else hyundai
            return R(text=xml(rows))
        if url == w.GAZETTE_API:
            return R(gazette_code, json.dumps(GAZETTE, ensure_ascii=False))
        return R(404)
    return get


def run(previous=None, now=NOW, **k):
    return w.run(CFG, "k", now=now, previous=previous, get=fake(**k), sleep=lambda s: None)


class Factory(unittest.TestCase):
    def test_parse_and_affiliate_filter(self):
        code, total, items = w.parse_factories(xml(POSCO))
        self.assertEqual((code, total, len(items)), ("00", 4, 4))
        doc = run()
        names = sorted(f["cmpnyNm"] for f in doc["factories"])
        self.assertEqual(names, ["(주)포스코 광양제철소", "(주)포스코 포항제철소", "현대자동차(주)아산공장"])
        self.assertEqual(doc["ruleCounts"]["포스코"], {"kept": 2, "dropped": 2})
        self.assertFalse(any("이름 규칙" in c["source"] for c in doc["checks"]))  # checks are real queries only
        self.assertEqual(doc["baselineSince"], NOW.isoformat(timespec="seconds"))
        f = next(x for x in doc["factories"] if x["id"] == "fac:10")
        self.assertEqual((f["employees"], f["registeredOn"]), (4000, "1973-07-03"))
        self.assertEqual(doc["events"], [])  # first run is a baseline

    def test_recent_registration_is_tagged_even_on_first_run(self):
        doc = run(hyundai=[fac("12", "현대자동차(주)울산EV공장", reg="20260915", product="전기자동차")])
        f = next(x for x in doc["factories"] if x["id"] == "fac:12")
        self.assertIn("[최근 등록 2026-09-15]", f["tags"])

    def test_changes_new_and_gone(self):
        first = run()
        changed = [fac("1", "(주)포스코 포항제철소", emp="8000", product="열연강판, 전기강판"), fac("5", "(주)포스코 포항 수소환원제철 공장", reg="20251001")]
        doc = run(previous=first, posco=changed, now=NOW + dt.timedelta(days=1))
        kinds = {(e["kind"], e["factoryId"]) for e in doc["events"]}
        self.assertIn(("새 공장", "fac:5"), kinds)
        self.assertIn(("목록에서 빠짐", "fac:4"), kinds)
        ch = next(e for e in doc["events"] if e["kind"] == "등록 내용 변경")
        self.assertIn("고용 9,000→8,000명", ch["text"])
        self.assertIn("주생산품 '열연강판'→'열연강판, 전기강판'", ch["text"])
        self.assertNotIn("fac:10", {e["factoryId"] for e in doc["events"]})

    def test_failed_query_keeps_records_and_does_not_report_gone(self):
        first = run()
        doc = run(previous=first, factory_code=500, now=NOW + dt.timedelta(days=1))
        self.assertTrue(all(f.get("stale") for f in doc["factories"]))
        self.assertFalse(any(e["kind"] == "목록에서 빠짐" for e in doc["events"]))
        self.assertEqual(doc["status"], "partial")

    def test_paging(self):
        calls = []
        many = [fac(str(100 + i), f"(주)포스코 제{i}공장") for i in range(100)]
        def get(url, params=None, headers=None, timeout=None):
            calls.append((url, dict(params)))
            if url == w.FACTORY_API and params["cmpnyNm"] == "포스코":
                return R(text=xml(many if params["pageNo"] == 1 else [fac("999", "(주)포스코 끝공장")], total=101))
            return fake()(url, params, headers, timeout)
        doc = w.run(CFG, "k", now=NOW, get=get, sleep=lambda s: None)
        self.assertIn("fac:999", {f["id"] for f in doc["factories"]})
        self.assertEqual([c[1]["pageNo"] for c in calls if c[1].get("cmpnyNm") == "포스코"], [1, 2])


class CommonNames(unittest.TestCase):
    def test_industry_rule_narrows_common_names(self):
        cfg = {"companies": [{"company": "태광", "queries": ["태광산업"], "accept": "^태광산업", "industryAccept": "화학|섬유",
                              "nameCheck": "주소로 확인"}]}
        rows = [fac("20", "태광산업(주) 울산공장", product="아크릴섬유", induty="합성섬유 제조업"),
                fac("21", "태광산업", product="금형", induty="금속 가공제품 제조업")]
        def get(url, params=None, headers=None, timeout=None):
            if url == w.FACTORY_API:
                return R(text=xml(rows))
            return fake()(url, params, headers, timeout)
        doc = w.run(cfg, "k", now=NOW, get=get, sleep=lambda s: None)
        self.assertEqual([f["id"] for f in doc["factories"]], ["fac:20"])
        self.assertEqual(doc["factories"][0]["nameCheck"], "주소로 확인")

    def test_changed_name_rule_is_a_new_baseline_not_gone_events(self):
        first = run()
        cfg2 = {"companies": [dict(CFG["companies"][0], industryAccept="화학"), CFG["companies"][1]]}  # 포스코 rule narrowed
        doc = w.run(cfg2, "k", now=NOW + dt.timedelta(days=1), previous=first, get=fake(), sleep=lambda s: None)
        self.assertFalse(any(e["company"] == "포스코" for e in doc["events"]))
        self.assertFalse(any(f["company"] == "포스코" for f in doc["factories"]))  # dropped by the new rule, not kept as stale
        self.assertNotEqual(doc["ruleSigs"]["포스코"], first["ruleSigs"]["포스코"])
        self.assertEqual(doc["ruleSigs"]["현대차"], first["ruleSigs"]["현대차"])

    def test_timeout_is_retried_once_with_longer_wait(self):
        seen = []
        class ReadTimeout(Exception):
            pass
        def get(url, params=None, headers=None, timeout=None):
            if url == w.GAZETTE_API:
                seen.append(timeout)
                if len(seen) == 1:
                    raise ReadTimeout()
            return fake()(url, params, headers, timeout)
        doc = w.run(CFG, "k", now=NOW, get=get, sleep=lambda s: None)
        self.assertEqual(seen, [40, 60])
        self.assertEqual(next(c for c in doc["checks"] if c["source"] == "관보 입법예고")["status"], "ok")


class GazetteSubject(unittest.TestCase):
    def test_issuing_body_name_does_not_match_beat_words(self):
        # Both matched on 2026-10-27 only through the issuer's name (산업통상부 → 통상, 원자력안전위원회 → 원자력).
        self.assertEqual(w.teams_of(w.subject_of("산업통상부공고제2026-656호(「산업통상부와 그 소속기관 직제 시행규칙」 일부개정령안 입법예고)")), [])
        self.assertEqual(w.teams_of(w.subject_of("원자력안전위원회공고제2026-096호(생활주변방사선 안전관리법 시행규칙 일부개정령안 입법예고)")), [])
        self.assertEqual(w.subject_of("국토교통부공고제2026-1500호(「자동차관리법 시행규칙」일부개정령안 입법예고)"), "「자동차관리법 시행규칙」일부개정령안 입법예고")
        self.assertEqual(w.teams_of(w.subject_of("국토교통부공고제2026-1500호(「자동차관리법 시행규칙」일부개정령안 입법예고)")), ["자동차"])
        self.assertEqual(w.teams_of(w.subject_of("기후에너지환경부공고제2026-77호(「국가기간 전력망 확충 특별법 시행령」 제정령안 입법예고)")), ["전력·에너지"])
        self.assertEqual(w.subject_of("제목에 공고번호가 없는 경우"), "제목에 공고번호가 없는 경우")

    def test_previously_kept_false_matches_are_dropped(self):
        first = run()
        first["gazette"].append({"id": "gz:old-fp", "date": NOW.date().isoformat(), "org": "산업통상부", "teams": ["공통"], "summary": "",
                                 "title": "산업통상부공고제2026-656호(「산업통상부와 그 소속기관 직제 시행규칙」 일부개정령안 입법예고)"})
        doc = run(previous=first)
        self.assertNotIn("gz:old-fp", {g["id"] for g in doc["gazette"]})
        self.assertEqual(sorted(g["id"] for g in doc["gazette"]), ["gz:I2", "gz:I3"])


class Gazette(unittest.TestCase):
    def test_keeps_beat_notices_only(self):
        doc = run()
        g = {x["id"]: x for x in doc["gazette"]}
        self.assertEqual(sorted(g), ["gz:I2", "gz:I3"])
        self.assertEqual(g["gz:I2"]["teams"], ["자동차"])
        self.assertEqual(g["gz:I2"]["laws"], ["자동차관리법 시행규칙"])
        self.assertEqual(g["gz:I2"]["date"], "2026-10-24")
        self.assertEqual(g["gz:I2"]["url"], "https://gwanbo.go.kr/ezpdf/customLayout.jsp?contentId=C&tocId=D&isTocOrder=N")
        self.assertEqual(g["gz:I3"]["teams"], ["전력·에너지"])
        self.assertFalse(any(x["isNew"] for x in doc["gazette"]))

    def test_failure_is_failed_and_keeps_previous(self):
        first = run()
        doc = run(previous=first, gazette_code=500)
        c = next(c for c in doc["checks"] if c["source"] == "관보 입법예고")
        self.assertEqual((c["status"], c["error"]), ("failed", "HTTP 500"))
        self.assertEqual(len(doc["gazette"]), 2)


EIA_HTML = """<h4 class="conH1 allPage">환경영향평가</h4>
<table class="tbl01 disPc"><caption>게시판 리스트</caption><thead><tr><th scope="col">사업코드</th></tr></thead>
<tbody>
<tr>
<td data-cell-header="사업코드 : ">ND2026O009</td>
<td data-cell-header="사업구분 : " title="폐기물처리시설">폐기물처리시</td>
<td data-cell-header="사업명 : " class="title" title="고려아연(주) 온산제련소 제2 폐기물처리시설 증설">
<a href="javascript:view('eia', 'ND2026O009', '45901');">고려아연(주) 온산제련소 제2 폐기물처리시설 증설</a></td>
<td data-cell-header="접수일 : ">2026.10.27</td>
<td data-cell-header="완료일 : "></td>
<td data-cell-header="진행현황 : "><span class="btn_item btn_white round">초안(진행)</span></td>
</tr>
<tr>
<td data-cell-header="사업코드 : ">ND2021O002</td>
<td data-cell-header="사업구분 : " title="폐기물처리시설">폐기물처리시</td>
<td data-cell-header="사업명 : " class="title" title="고려아연(주) 온산제련소 폐기물처리시설 설치">
<a href="javascript:view('eia', 'ND2021O002', '1');">고려아연(주) 온산제련소 폐기물처리시설 설치</a></td>
<td data-cell-header="접수일 : ">2021.09.15</td>
<td data-cell-header="완료일 : ">2022.01.06</td>
<td data-cell-header="진행현황 : "><span class="btn_item btn_white round">본협의(완료)</span></td>
</tr>
<tr>
<td data-cell-header="사업코드 : ">ME2026X001</td>
<td data-cell-header="사업구분 : " title="산업단지">산업단지</td>
<td data-cell-header="사업명 : " class="title" title="포스코퓨처엠 광양 양극재 공장 증설">
<a href="#">포스코퓨처엠 광양 양극재 공장 증설</a></td>
<td data-cell-header="접수일 : ">2026.10.27</td>
<td data-cell-header="완료일 : "></td>
<td data-cell-header="진행현황 : "><span>초안(진행)</span></td>
</tr>
</tbody></table><table class="tbl01 table_tm disTm"><tbody></tbody></table>"""


class Eia(unittest.TestCase):
    def setUp(self):
        self.cfg = {"companies": [{"company": "고려아연", "queries": ["고려아연"]}, {"company": "포스코", "queries": ["포스코"]}]}
        self.now = w.dt.datetime(2026, 10, 29, 8, 10, tzinfo=w.KST)

    def fake(self, html=EIA_HTML, status=200):
        class R:
            def __init__(self, text="", content=b"-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\n"):
                self.status_code, self.text, self.content = status, text, content
        posts = []
        return (lambda url, **kw: (posts.append(kw["data"]["query"]), R(html))[1]), (lambda url, **kw: R()), posts

    def test_rows_and_new_stage_after_baseline(self):
        rows = w.eia_rows(EIA_HTML)
        self.assertEqual(rows[0], {"code": "ND2026O009", "category": "폐기물처리시설", "name": "고려아연(주) 온산제련소 제2 폐기물처리시설 증설",
                                   "received": "2026-10-27", "completed": "", "stage": "초안(진행)"})
        post, get, posts = self.fake()
        first, seen, checks = w.eia(self.cfg, self.now, None, post=post, get=get, sleep=lambda s: None)
        self.assertEqual((first, checks[0]["status"], checks[0]["returned"]), ([], "ok", 4))
        self.assertEqual(posts, ["고려아연", "고려아연", "포스코", "포스코"])
        self.assertIn("eia:ND2026O009:2026-10-27:초안(진행)", seen)
        self.assertFalse(any("ME2026X001" in x for x in seen))  # 포스코퓨처엠은 포스코가 아님
        newer = EIA_HTML.replace("초안(진행)</span></td>\n</tr>\n<tr>\n<td data-cell-header=\"사업코드 : \">ND2021O002", "본안(진행)</span></td>\n</tr>\n<tr>\n<td data-cell-header=\"사업코드 : \">ND2021O002", 1)
        post2, get2, _ = self.fake(newer)
        items, _, _ = w.eia(self.cfg, self.now, {"eiaSeen": seen, "eia": []}, post=post2, get=get2, sleep=lambda s: None)
        self.assertEqual([(x["company"], x["stage"], x["kind"], x["isNew"]) for x in items], [("고려아연", "본안(진행)", "환경영향평가", True)])

    def test_site_failure_is_not_zero(self):
        post, get, _ = self.fake(status=503)
        items, _, checks = w.eia(self.cfg, self.now, {"eiaSeen": [], "eia": [{"id": "eia:x", "firstSeen": "2026-10-28T08:10:00+09:00"}]},
                                 post=post, get=get, sleep=lambda s: None)
        self.assertEqual(checks[0]["status"], "failed")
        self.assertEqual([x["id"] for x in items], ["eia:x"])


if __name__ == "__main__":
    unittest.main()
