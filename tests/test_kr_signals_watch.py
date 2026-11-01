"""KR signals watch: FTC decision list/text parsing (live layout of case.ftc.go.kr, 2026-10-27), whole-name matching
(포스코 vs 포스코이앤씨, 발주처 vs 피심인), KEPCO bid filtering and state changes, KOMIS price signals (range records with
dates, one-month moves, LME stock), baseline and budget handling, failures kept as failures."""
import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_signals_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 15, 20, tzinfo=KST)
CFG = json.loads((Path(__file__).resolve().parents[1] / "data" / "kr_signals.json").read_text(encoding="utf-8"))


def row(csno, blno, name, action, apdate, file_id, doc=None):
    """One <tr> of ltfr.do as served on 2026-10-27 (hidden inputs, then PDF and open-document cells)."""
    view = ("" if doc is None else
            f'<td><a class="down_files html" href="#view" onclick="javascript:fn_htmlView(this);" title="{name} 개방문서를 미리보기 합니다"></a>\n'
            f'    \t                    <input type="hidden" value="{doc[0]}">\n        \t                <input type="hidden" value="{doc[1]}">\n'
            f'        \t                <input type="hidden" value="{doc[2]}">\n                        </td>')
    return (f'<tr>\n<td class="rwd_hidden">{csno}</td>\n<td class="rwd_hidden">{blno}</td>\n'
            f'<td><a href="#link" onclick="javascript:fn_ltfrView(this);">{name}</a>\n'
            f'<input type="hidden" name="csno" value="{csno}">\n<input type="hidden" name="blno" value="{blno}">\n'
            f'<input type="hidden" name="csname" value="{name}">\n<input type="hidden" name="ttcnts" value="{action}">\n'
            f'<input type="hidden" name="apdate" value="{apdate}">\n<input type="hidden" name="fileId" value="{file_id}">\n'
            f'<input type="hidden" name="fileSn" value="2">\n<input type="hidden" name="fileNm" value="의결서.pdf">\n</td>\n'
            f'<td>{action}</td>\n<td class="rwd_hidden">{apdate}</td>\n<td><a class="down_files pdf" href="#down"></a></td>\n{view}\n</tr>')


def page(rows):
    return f"<html><table><thead><tr><th>사건명</th></tr></thead><tbody>{''.join(rows)}</tbody></table></html>"


KUMHO = row("2023유대1720", "약식2025-129", "금호타이어(주)의 대리점법 등 위반행위에 대한 건", "시정명령", "2026-10-12", "20261021105938510993",
            ("20261021105938510993", "15089", "OCPLTFR1"))
POSCO = row("2024구사0058", "약식2025-053", "(주)포스코 및 포스코홀딩스(주)의 부당한 광고행위에 대한 건", "과징금", "2026-10-02", "20261020141800570306",
            ("20261020141800570306", "14879", "OCPLTFR2"))
BUYER = row("2025국카2422", "의결2026-200", "현대자동차(주) 및 기아(주) 발주 차량용 내장재 표면처리 입찰 관련 3개 사업자의 부당한 공동행위에 대한 건",
            "과징금", "2026-09-30", "20261015100000000001", ("20261015100000000001", "15001", "OCPLTFR3"))
POSCO_ENC = row("2025서카0001", "의결2026-150", "㈜포스코이앤씨 발주 시스템 가구 입찰 관련 9개 사업자의 부당한 공동행위에 대한 건", "고발", "2026-09-01",
                "20261001100000000002", ("20261001100000000002", "15002", "OCPLTFR4"))
SCHOOL = [row(f"2026입담{n}", "의결2026-204", "용인시 영문중학교 발주 교복 학교주관구매 입찰 관련 4개 사업자의 부당한 공동행위에 대한 건", "과징금",
              "2026-10-01", "20261016105000140602", ("20261016105000140602", "15417", "OCPLTFR5")) for n in ("1265", "0347")]
INSTALL = row("2026기결0100", "결정2026-040", "6개 강관 제조사의 부당한 공동행위에 대한 건 관련 현대제철(주)의 과징금 납부기한 연장 및 분할납부 신청에 대한 건",
              "인용", "2026-10-10", "20261022090000000003")  # no open document (PDF only)

DOCS = {
    "15089": "<html><script>var x=1;</script><div>목차 주요사항 주문 이유 1. 기초사실 4 피심인의 대리점은 전부 비전속</div><div>주요사항 공 정 거 래 위 원 회 "
             "사건번호2023유대1720 사건명금호타이어(주)의 대리점법 등 위반행위에 대한 건 피 심 인금호타이어 주식회사 광주광역시 광산구 어등대로 658 "
             "대표이사 정ㅇㅇ 심 의 종 결 일2025. 9. 27. 주문 1. 피심인은 대리점에게 판매금액 정보를 제공하도록 요구하는 행위를 다시 하여서는 아니 된다. "
             "이유 1. 기초사실 가. 피심인 적격성</div></html>",
    "14879": "<div>사건명(주)포스코 및 포스코홀딩스(주)의 부당한 광고행위에 대한 건 피 심 인1. 주식회사 포스코 포항시 남구 동해안로6261 대표이사 이○○ "
             "2. 포스코홀딩스 주식회사 포항시 남구 동해안로6261 심의종결일2025. 4. 7. 주문 1. 피심인 주식회사 포스코는 거짓·과장의 광고 행위를 다시 하여서는 "
             "아니 된다. 2. 피심인 주식회사 포스코는 과징금 1,234백만원을 납부하여야 한다. 이유 1. 기초사실 가. 포스코퓨처엠과 포스코인터내셔널은 이 사건과 무관</div>",
    "15001": "<div>사건명현대자동차(주) 및 기아(주) 발주 차량용 내장재 표면처리 입찰 관련 3개 사업자의 부당한 공동행위에 대한 건 피 심 인1. 주식회사 갑을 2. 을병(주) "
             "심의종결일2026. 9. 1. 주문 1. 피심인들은 다시 하여서는 아니 된다. 이유 1. 기초사실 현대자동차 주식회사와 기아 주식회사가 발주한</div>",
    "15002": "<div>사건명㈜포스코이앤씨 발주 시스템 가구 입찰 관련 9개 사업자의 부당한 공동행위에 대한 건 피 심 인1. 가구(주) 심의종결일2026. 8. 1. "
             "주문 1. 피심인은 아니 된다. 이유 1. 기초사실 포스코이앤씨가 발주한</div>",
    "15417": "<div>사건명용인시 처인구 소재 8개 중고등학교 발주 교복 입찰 관련 4개 사업자의 부당한 공동행위에 대한 건 피 심 인1. ㅇㅇㅇ(스마트학생복 대표) "
             "심의종결일2026. 9. 4. 주문 피심인 ㅇㅇㅇ는 과징금 39,000,000원 이유 1. 기초사실</div>",
}


class Resp:
    def __init__(self, text="", status=200, payload=None):
        self.text, self.status_code, self._payload = text, status, payload

    def json(self):
        if self._payload is None:
            return json.loads(self.text)
        return self._payload


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def request(self, method, url, *, timeout=None, **kw):
        self.calls.append((method, url, kw.get("params") or kw.get("data")))
        for prefix, fn in self.routes.items():
            if url.startswith(prefix):
                out = fn(method, url, kw)
                if isinstance(out, Exception):
                    raise out
                return out
        return Resp("blocked", 599)


def ftc_routes(rows, docs=DOCS, fail_list=False):
    def lst(method, url, kw):
        if fail_list:
            return Resp("", 503)
        p = int((kw.get("params") or {}).get("pageIndex", 1))
        return Resp(page(rows if p == 1 else []))  # page 2 is empty: end of list

    def doc(method, url, kw):
        return Resp(docs.get(kw["params"]["docCnvrMnNo"], ""))
    return {w.FTC_LIST: lst, w.FTC_TEXT: doc}


def komis_series(start, end, step=1.0, base=3000.0, stock=200000.0, stock_step=0.0):
    """Daily rows newest first, like getMnrlPrcByMnrkndUnqCd (crtrYmd, cmercPrc, invt)."""
    rows, d, v, s = [], dt.date.fromisoformat(start), base, stock
    while d <= dt.date.fromisoformat(end):
        if d.weekday() < 5:
            rows.append({"crtrYmd": d.strftime("%Y%m%d"), "cmercPrc": f"{v:.2f}", "invt": f"{s:.2f}"})
            v += step
            s += stock_step
        d += dt.timedelta(days=1)
    return list(reversed(rows))


def komis_routes(series_by_code, fail=()):
    def crtr(method, url, kw):
        code = kw["data"]["mnrkndUnqCd"]
        basis = next(c["basis"] for c in CFG["commodities"] if c["code"] == code)
        return Resp(payload={"data": [{"cdVal": basis + " suffix", "cdKey": 500}, {"cdVal": "LME 3개월", "cdKey": 503}]})

    def price(method, url, kw):
        code = kw["data"]["srchMnrkndUnqCd"]
        if code in fail:
            return Resp("", 500)
        return Resp(payload={"dataAvg": {"INFO": {"prcUnitCdNm": "USD", "weigUnitCd": "ton", "prcCrtr": "LME CASH", "archNm": "광물자원공사"}},
                             "data": {"defaultMnrl": series_by_code.get(code, [])}})
    return {w.KOMIS_PAGE: lambda *a: Resp("<html></html>"), w.KOMIS_CRTR: crtr, w.KOMIS_PRICE: price}


def http(routes):
    return w.Http(FakeSession(routes), sleep=lambda s: None, gap=0)


def flat_cfg(**over):
    cfg = json.loads(json.dumps(CFG))
    cfg["commodities"] = over.get("commodities", cfg["commodities"][:1])
    return cfg


class NameMatching(unittest.TestCase):
    def setUp(self):
        self.pats = w.company_patterns(CFG)

    def who(self, name, text=""):
        return [(m["company"], m["role"]) for m in w.mentions(w._norm(name), w.doc_text(text) if text else "", self.pats)]

    def test_whole_names_only(self):
        self.assertEqual(self.who("(주)포스코에이앤씨건축사사무소 발주 빌트인 특판가구"), [])
        self.assertEqual(self.who("㈜포스코이앤씨 발주 시스템 가구 입찰"), [])
        self.assertEqual(self.who("(주)GS리테일의 가맹사업법 위반"), [])
        self.assertEqual(self.who("GS25 가맹점"), [])
        self.assertEqual(self.who("엘에스 기업집단 계열회사의 부당한 지원행위"), [])  # LS지주 only by legal form
        self.assertEqual(self.who("주식회사 엘에스의 부당 지원"), [("LS지주", "사건명 언급")])
        self.assertEqual(self.who("현대제철이 발주한"), [("현대제철", "발주처")])

    def test_buyer_is_not_respondent(self):
        found = self.who(BUYER.split('name="csname" value="')[1].split('"')[0], DOCS["15001"])
        self.assertEqual(sorted(found), [("기아", "발주처"), ("현대차", "발주처")])

    def test_respondent_block_skips_table_of_contents(self):
        resp, order = w.sections(w.doc_text(DOCS["15089"]))
        self.assertTrue(resp.startswith("금호타이어 주식회사 광주광역시"))
        self.assertTrue(order.startswith("1. 피심인은 대리점에게"))
        m = w.mentions(w._norm("금호타이어(주)의 대리점법 등 위반행위에 대한 건"), w.doc_text(DOCS["15089"]), self.pats)
        self.assertEqual([(x["company"], x["role"]) for x in m], [("금호타이어", "피심인")])
        self.assertTrue(m[0]["snippet"].startswith("금호타이어 주식회사"))

    def test_order_amount_is_quoted_not_computed(self):
        m = {x["company"]: x for x in w.mentions(w._norm("(주)포스코 및 포스코홀딩스(주)의 부당한 광고행위에 대한 건"), w.doc_text(DOCS["14879"]), self.pats)}
        self.assertEqual(m["포스코"]["role"], "피심인")
        self.assertEqual(m["포스코홀딩스"]["role"], "피심인")
        self.assertEqual(m["포스코"]["orderAmounts"], ["1,234백만원"])
        self.assertNotIn("포스코퓨처엠", m)


class FtcWatch(unittest.TestCase):
    def test_list_parsing_groups_case_numbers_and_reads_open_document_ids(self):
        rows, last = w.parse_ftc_list(page([KUMHO, *SCHOOL, INSTALL]))
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["doc"], {"docId": "20261021105938510993", "docCnvrMnNo": "15089", "id": "OCPLTFR1"})
        self.assertIsNone(rows[3]["doc"])
        self.assertEqual(w.file_date("20261016105000140602"), "2026-10-16 10:50")

    def test_first_run_is_baseline_keeps_only_named_decisions(self):
        h = http(ftc_routes([KUMHO, POSCO, BUYER, POSCO_ENC, *SCHOOL, INSTALL]))
        decisions, seen, check = w.ftc(CFG, NOW, None, h)
        ids = {d["id"]: d for d in decisions}
        self.assertEqual(sorted(ids), ["ftc:결정2026-040", "ftc:약식2025-053", "ftc:약식2025-129", "ftc:의결2026-200"])
        self.assertTrue(all(not d["isNew"] for d in decisions))
        self.assertEqual(check["status"], "ok")
        self.assertEqual((check["listed"], check["decisions"], check["read"]), (7, 6, 5))  # school case: 2 case numbers, 1 decision
        install = ids["ftc:결정2026-040"]
        self.assertEqual(install["flags"], ["과징금 납부기한 연장·분할납부", "이의신청 재결"])
        self.assertEqual(install["mentions"][0]["company"], "현대제철")
        self.assertIn("개방문서 없음", install["note"])
        self.assertTrue(install["url"].endswith("caseNo=2026기결0100"))
        self.assertEqual(ids["ftc:약식2025-129"]["fileDate"], "2026-10-21 10:59")
        self.assertIn("openDocView.do?docTy=LTFR&docId=20261021105938510993", ids["ftc:약식2025-129"]["url"])
        self.assertIn("ftc:의결2026-204", seen)  # read once, never again

    def test_next_run_reads_only_new_decisions_and_marks_them_new(self):
        h1 = http(ftc_routes([KUMHO, *SCHOOL]))
        d1, seen, _ = w.ftc(CFG, NOW, None, h1)
        prev = {"decisions": d1, "ftcSeen": seen}
        s2 = FakeSession(ftc_routes([POSCO, KUMHO, *SCHOOL]))
        d2, _, check = w.ftc(CFG, NOW + dt.timedelta(hours=7), prev, w.Http(s2, sleep=lambda s: None, gap=0))
        docs_read = [c for c in s2.calls if c[1].startswith(w.FTC_TEXT)]
        self.assertEqual(len(docs_read), 1)
        new = {d["id"]: d for d in d2}
        self.assertTrue(new["ftc:약식2025-053"]["isNew"])
        self.assertFalse(new["ftc:약식2025-129"]["isNew"])
        self.assertEqual(check["read"], 1)

    def test_budget_leaves_rest_pending_and_list_failure_is_not_zero(self):
        old = w.FTC_DOC_BUDGET
        w.FTC_DOC_BUDGET = 1
        try:
            _, seen, check = w.ftc(CFG, NOW, None, http(ftc_routes([KUMHO, POSCO])))
        finally:
            w.FTC_DOC_BUDGET = old
        self.assertEqual((check["status"], check["pending"]), ("partial", 1))
        self.assertNotIn("ftc:약식2025-053", seen)  # retried next run
        decisions, _, check = w.ftc(CFG, NOW, None, http(ftc_routes([], fail_list=True)))
        self.assertEqual((check["status"], check["error"]), ("failed", "HTTP 503"))
        self.assertEqual(decisions, [])


class KepcoWatch(unittest.TestCase):
    def data(self, state="PreAttendProgress"):
        return {"data": [
            {"companyId": "COM01", "no": "R26-1", "name": "154kV 지중 전력케이블 구매", "presumedPrice": "12,300,000,000", "noticeDate": "20261024103000",
             "progressState": state, "purchaseType": "Product", "competitionType": "Open", "bidType": "LowestPrice", "placeName": "한국전력공사",
             "filename1": "공고_구매규격서.pdf"},
            {"companyId": "COM04", "no": "R26-2", "name": "사옥 청소 용역", "presumedPrice": "300000000", "noticeDate": "20261024", "progressState": "Close"},
            {"companyId": "COM05", "no": "R26-3", "name": "배전용 변압기 단가계약", "presumedPrice": "900000000", "noticeDate": "20261023", "progressState": "Close",
             "purchaseType": "Product"},
            # live examples from 2026-10-26 that are construction or services, not equipment purchases
            {"companyId": "COM01", "no": "E1", "name": "154kV 남광명분기 지중T/L 건설공사", "presumedPrice": "1969674000", "noticeDate": "20261026",
             "progressState": "PreAttendProgress", "purchaseType": "ConstructionService"},
            {"companyId": "COM01", "no": "E2", "name": "인제 다미뷔페~회전교차로 지중화공사 감리용역", "presumedPrice": "200701931", "noticeDate": "20261026",
             "progressState": "AttendProgress", "purchaseType": "ConstructionService"},
            {"companyId": "COM01", "no": "E3", "name": "보호배전반,SHUNT REACTOR용,345/154/23KV 1면 (서서울2SS) - 지역제한", "presumedPrice": "35000000",
             "noticeDate": "20261026", "progressState": "AttendProgress", "purchaseType": "Product"},
            {"companyId": "COM01", "no": "E4", "name": "서해안 HVDC 해저케이블 건설공사", "presumedPrice": "250000000000", "noticeDate": "20261025",
             "progressState": "PreAttendProgress", "purchaseType": "ConstructionService"}]}

    def test_unset_key_is_not_a_failure_and_not_zero(self):
        rows, events, check = w.kepco(CFG, "", NOW, None, http({}))
        self.assertEqual((check["status"], rows, events), ("unset", [], []))

    def test_keeps_power_equipment_marks_big_and_tracks_state(self):
        routes = {w.KEPCO_API: lambda m, u, kw: Resp(payload=self.data())}
        rows, events, check = w.kepco(CFG, "k" * 40, NOW, None, http(routes))
        self.assertEqual(sorted(r["name"] for r in rows), sorted(["154kV 지중 전력케이블 구매", "배전용 변압기 단가계약",
                                                                  "보호배전반,SHUNT REACTOR용,345/154/23KV 1면 (서서울2SS) - 지역제한", "서해안 HVDC 해저케이블 건설공사"]))
        rows = sorted(rows, key=lambda r: r["name"])  # equipment purchases plus HVDC-class projects; plain construction and 감리 dropped
        cable = next(r for r in rows if r["name"].startswith("154kV 지중"))
        self.assertEqual((cable["price"], cable["big"], cable["state"], cable["company"]), (12_300_000_000, True, "공고진행", "한국전력공사"))
        self.assertFalse(next(r for r in rows if r["name"].startswith("배전용"))["big"])
        self.assertEqual((check["returned"], check["kept"]), (7, 4))
        routes2 = {w.KEPCO_API: lambda m, u, kw: Resp(payload=self.data("Fail"))}
        rows2, events2, _ = w.kepco(CFG, "k" * 40, NOW + dt.timedelta(days=1), {"kepco": rows}, http(routes2))
        self.assertEqual(len(events2), 1)
        self.assertIn("공고진행 → 유찰", events2[0]["text"])

    def test_bad_answer_keeps_previous_rows(self):
        prev = {"kepco": [{"id": "kepco:COM01:X", "noticeDate": "20261020", "name": "x"}]}
        rows, _, check = w.kepco(CFG, "k" * 40, NOW, prev, http({w.KEPCO_API: lambda m, u, kw: Resp(payload={"errCd": 401})}))
        self.assertEqual(check["status"], "failed")
        self.assertEqual([r["id"] for r in rows], ["kepco:COM01:X"])


class PriceSignals(unittest.TestCase):
    def test_range_record_and_month_move_with_dates(self):
        zinc = komis_series("2024-01-01", "2026-10-26", step=1.0)  # steady rise: latest is the highest since 2024-01-01
        cfg = flat_cfg()
        prices, events, checks = w.komis(cfg, NOW, None, http(komis_routes({"MNRL0023": zinc})))
        p = prices[0]
        self.assertEqual(checks[0]["status"], "ok")
        self.assertEqual(p["summary"]["date"], "2026-10-26")
        self.assertEqual(p["basis"], "LME CASH suffix")
        self.assertEqual(p["unit"], "USD/ton")
        kinds = {s["kind"]: s["text"] for s in p["signals"]}
        self.assertIn("조회 범위 최고", kinds)
        self.assertEqual(kinds["조회 범위 최고"], "2024-01-01 이후 최고(조회 범위 안)")
        self.assertNotIn("한 달 큰 변동", kinds)  # ~21/3700 per month, far below 10%
        self.assertEqual(len(events), 1)
        self.assertIn("아연(LME CASH suffix, USD/ton)", events[0]["text"])

    def test_since_date_with_gap_and_no_repeat_within_two_weeks(self):
        rows = komis_series("2024-01-01", "2026-10-26", step=0.0, base=3000.0)
        for r in rows:  # one old spike above today's level, then flat, then a jump today
            if r["crtrYmd"] == "20250303":
                r["cmercPrc"] = "4000.00"
        rows[0]["cmercPrc"] = "3600.00"
        cfg = flat_cfg()
        prices, events, _ = w.komis(cfg, NOW, None, http(komis_routes({"MNRL0023": rows})))
        texts = [s["text"] for s in prices[0]["signals"]]
        self.assertTrue(any(t.startswith("2025-03-03(4,000.00) 이후 최고") for t in texts), texts)
        self.assertTrue(any(t.startswith("2026-09-25 대비 +20.0%") for t in texts), texts)
        prices2, events2, _ = w.komis(cfg, NOW + dt.timedelta(days=1), {"prices": prices, "events": events}, http(komis_routes({"MNRL0023": rows})))
        self.assertEqual(events2, [])  # same signals within repeatDays are not new events

    def test_new_source_items_compare_only_after_since_and_lme_stock_move(self):
        cfg = flat_cfg(commodities=[c for c in CFG["commodities"] if c["id"] in ("iron-ore", "copper")])
        old_and_new = komis_series("2025-06-01", "2026-10-26", step=0.0, base=100.0)
        copper = komis_series("2024-01-01", "2026-10-26", step=0.0, base=9000.0, stock=100000.0)
        copper[0]["invt"] = "140000.00"  # LME stock +40% against 21 trading days earlier
        prices, _, _ = w.komis(cfg, NOW, None, http(komis_routes({"MNRL1011": old_and_new, "MNRL0008": copper})))
        iron = next(p for p in prices if p["id"] == "iron-ore")
        self.assertEqual(iron["summary"]["span"][0], "2026-01-05")
        self.assertIn("자료원", iron["sinceNote"])
        cu = next(p for p in prices if p["id"] == "copper")
        self.assertEqual([s["text"] for s in cu["signals"] if s["kind"] == "LME 재고 큰 변동"], ["재고 100,000 → 140,000(+40.0%, 2026-09-25 대비)"])
        self.assertEqual(cu["summary"]["stockMonth"], 40.0)

    def test_failure_keeps_previous_value_marked_stale(self):
        cfg = flat_cfg()
        prev = {"prices": [{"id": "zinc", "name": "아연", "summary": {"date": "2026-10-20"}}]}
        prices, events, checks = w.komis(cfg, NOW, prev, http(komis_routes({}, fail=("MNRL0023",))))
        self.assertEqual(checks[0]["status"], "failed")
        self.assertTrue(prices[0]["stale"])
        self.assertEqual(events, [])


def motir_row(aid, title, dept, date, kind="보도자료", attach=None):
    """One <tr> of the 산업통상부 보도·참고자료 board as the server sends it on 2026-10-27 (no data-cell-header labels — the page script adds them)."""
    att = ("" if attach is None else f'<td>\n<a href="/attach/down/095a2dda/b8b95622" title="{attach} 다운로드">\n'
           f'<img src="/images/ico/ico_file_pdf.png" alt="PDF 파일"></a></td>')
    return (f'<tr>\n<td>\n30,162\n</td>\n<td>\t\n<span class="badge-category"><i>{kind}</i></span>\n</td>\n'
            f'<td class="ta-l">\n<div class="board-link">\n<a href="/kor/article/ATCL3f49a5a8c/{aid}/view?mno=&amp;pageIndex=1" '
            f'onclick="article.view(\'{aid}\'); return false;">\n<i>{title}</i>\n</a>\n<span class="badge-new"><i><img src="/images/ico/ico_new01.png" alt="새글"></i></span>\n</div>\n</td>\n<td><i>{dept}</i></td>\n'
            f'<td>{date}</td>\n<td>579</td>\n{att}\n</tr>')


MOTIR_PAGE = page([
    motir_row("172335", "자동차·가전부터 한우·수산물까지...최대 50% 할인 정부, 「제2회 코리아 그랜드 페스티벌」 시작(10.29~11.15)", "유통물류과", "2026-10-27",
              attach="1026(27석간, 27일(화) 국무회의 종료시 엠바고)유통물류과, 자동차·가전부터 한우·수산물까지.pdf"),
    motir_row("172158", "국민이 직접 뽑은 기업 사회공헌 맛집은 어디?", "산업정책과", "2026-10-26"),
    motir_row("172155", "무역위, 중국산 아연도금냉연, 옵셋인쇄판 덤핑조사 최종판정", "무역구제정책과", "2026-10-23"),
    motir_row("172254", "2026년 9월 수출입 동향", "수출입과", "2026-10-01"),
    motir_row("172300", "현대제철, 포스코와 탄소중립 공동연구 협약", "철강세라믹과", "2026-10-20")])
TRADE_BODY = ("<div>2026년 9월 수출입 동향 담당부서수출입과 * 9월 수출 1,209.4억 달러(+83.5%), 수입 710.9억 달러(+26.0%), 수지 498.5억 달러 흑자 "
              "【품목】9월에는 20대 주력 수출품목 중 11개 품목 수출이 증가했다. 【9월 20대 주요품목별 수출액(억달러) 및 증감률(%)】 반도체 디스플레이 무선통신기기 "
              "컴퓨터 자동차 자동차부품 선박 603 (+263) 16 (△9) 21 (+23) 70 (+435) 61 (△5) 18 (△7) 38 (+30) 석유제품 석유화학 이차전지 일반기계 전기기기 철강 "
              "비철금속 72 (+72) 40 (+5) 7 (+14) 41 (△3) 18 (+23) 22 (+3) 17 (+34) 농수산식품 화장품 생활용품 섬유 가전 바이오헬스 총 수출액 11 (△5) 15 (+31) "
              "7 (△5) 9 (△7) 6 (△13) 15 (△9) 1,209 (+84) (IT) 반도체 수출(603.0억 달러, +262.8)은 … 자동차(60.5억 달러, △5.5%) 수출은 …</div>")


def motir_routes(trade_body=TRADE_BODY):
    return {w.MOTIR_LIST + "/172254/view": lambda m, u, kw: Resp(trade_body),
            w.MOTIR_LIST: lambda m, u, kw: Resp(MOTIR_PAGE if (kw.get("params") or {}).get("pageIndex") == 1 else page([]))}


class MotirWatch(unittest.TestCase):
    def test_list_parsing_embargo_and_beat_filter(self):
        rows = w.parse_motir_list(MOTIR_PAGE)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["id"], "motir:172335")
        self.assertEqual(rows[0]["embargo"], "27석간, 27일(화) 국무회의 종료시 엠바고")
        self.assertEqual((rows[2]["dept"], rows[2]["date"], rows[2]["kind"]), ("무역구제정책과", "2026-10-23", "보도자료"))
        items, check = w.motir(CFG, NOW, None, http(motir_routes()))
        ids = [x["id"] for x in items]
        self.assertNotIn("motir:172158", ids)  # no beat topic or name
        self.assertNotIn("motir:172335", ids)  # '자동차' 낱말이 있어도 할인 행사(페스티벌)는 업종 밖
        self.assertIn("motir:172155", ids)
        named = next(x for x in items if x["id"] == "motir:172300")
        self.assertEqual(named["companies"], ["포스코", "현대제철"])
        self.assertEqual((check["status"], check["listed"]), ("ok", 5))

    def test_off_beat_releases_with_beat_words_are_dropped(self):
        # 10-31 운영 제목들: 직함 속 '통상', 바이오 회사의 '화학', 할인 행사의 '자동차'
        for title in ("통상교섭본부장, K-콘텐츠 기업과 함께중국 시장 진출 전략 모색",
                      "글로벌 화학 기업 독일 머크(Merck), 대전 바이오 원부자재 제조 거점 개소",
                      "자동차·가전부터 한우·수산물까지...최대 50% 할인 정부, 「제2회 코리아 그랜드 페스티벌」 시작(10.29~11.15)"):
            self.assertFalse(w.motir_topic(title), title)
        for title in ("(참고자료)EU, 수입 하이브리드 자동차에 대한 글로벌 세이프가드 조사 개시", "외국의 통상조치로 인한 피해까지 지원대상 늘린다",
                      "민관 원팀으로 중동發 공급망 위기 넘어, 구조개편 가속화로 화학산업 재도약 다짐", "K-원전, 글로벌 공급망에 올라탄다!"):
            self.assertTrue(w.motir_topic(title), title)

    def test_refining_titles_are_beat_topics(self):
        # 11-01 출입처에 정유 3사(S-OIL·SK이노베이션·HD현대오일뱅크) 추가 — 정유·원유·나프타 제목도 업종 안
        for title in ("정유업계 간담회 개최, 중동 정세에 따른 석유제품 수급 점검", "나프타 수입선 다변화 지원", "국제유가 급등 대비 원유 비축 방출 검토"):
            self.assertTrue(w.motir_topic(title), title)
        for title in ("유가족 지원 협약 체결", "K-뷰티 수출 상담회 개최"):
            self.assertFalse(w.motir_topic(title), title)
        # 예전 실행이 남긴 업종 밖 줄도 걸러진다(출입처 이름이 있으면 둔다)
        prev = {"motir": [{"id": "motir:1", "title": "통상교섭본부장, K-콘텐츠 기업과 함께", "date": "2026-10-30", "companies": []},
                          {"id": "motir:2", "title": "현대차, 바이오 연료 실증", "date": "2026-10-30", "companies": ["현대차"]}]}
        items, _ = w.motir(CFG, NOW, prev, http(motir_routes()))
        ids = [x["id"] for x in items]
        self.assertNotIn("motir:1", ids)
        self.assertIn("motir:2", ids)

    def test_trade_release_items_quoted_as_published(self):
        t = w.parse_trade(TRADE_BODY)
        self.assertEqual(t["exports"], {"value": "1,209.4", "yoy": "+83.5"})
        self.assertEqual(t["items"]["자동차"], {"value": "61", "yoy": "-5"})
        self.assertEqual(t["items"]["철강"], {"value": "22", "yoy": "+3"})
        self.assertEqual(t["items"]["비철금속"], {"value": "17", "yoy": "+34"})
        self.assertNotIn("반도체", t["items"])
        bad = w.parse_trade(TRADE_BODY.replace("자동차부품 선박", "자동차부품"))  # names and values no longer line up
        self.assertIn("표 해석 실패", bad["tableError"])
        self.assertEqual(bad["items"]["자동차"], {"value": "60.5", "yoy": "-5.5", "from": "본문"})  # prose fallback
        items, _ = w.motir(CFG, NOW, None, http(motir_routes()))
        trade = next(x for x in items if x["id"] == "motir:172254")["trade"]
        self.assertEqual(trade["period"], "2026-09")
        self.assertEqual(trade["items"]["석유화학"], {"value": "40", "yoy": "+5"})


def ftc_row(no, kind, ntt, title, dept, date, key="12", ctg="01,02", new=False):
    badge = '\n<!--<span class="krds-badge bg4">New</span>--> ' if new else "\n"
    return (f'<tr>\n<td>{no}</td>\n<td>{kind}</td>\n<td class="p-subject">\n'
            f'<a href="./selectBbsNttView.do?pageUnit=10&amp;pageIndex=1&amp;searchCnd=all&amp;key={key}&amp;bordCd=3&amp;searchCtgry={ctg}&amp;nttSn={ntt}">\n'
            f'<span class="p-table__text">{title}</span>{badge}</a>\n</td>\n<td>{dept}</td>\n<td>{date}</td>\n<td class="p-file">\n'
            f'<a href="./downloadBbsFileAll.do?atchmnflNo={ntt}" class="btn btn-txt ico-down">파일다운로드</a>\n</td>\n</tr>')


def ftc_page(rows):
    return f"<table><thead><tr><th>번호</th></tr></thead><tbody>\n{''.join(rows)}\n</tbody></table>"


# 11-01 운영 목록 형식(probe 80): 제목 뒤 주석 처리된 New 배지, 설명자료 제목 앞 날짜
FTC_PRESS_PAGE = ftc_page([
    ftc_row("9811", "보도", "48168", "한세모빌리티㈜의 기술자료 관련 하도급법 위반행위 제재", "기술유용조사과", "2026-10-30", new=True),
    ftc_row("9810", "참고", "48165", "2026년 공정거래 학술연구 지원사업 최종발표회 개최", "경쟁정책과", "2026-10-29"),
    ftc_row("9808", "보도", "48163", "현대자동차㈜의 하도급법 위반행위 제재", "제조하도급과", "2026-10-29"),
    ftc_row("9807", "보도", "48160", "정유 4사의 석유제품 가격 담합 제재", "카르텔조사국", "2026-10-28"),
    ftc_row("9700", "보도", "47000", "한국전력공사 발주 변압기 입찰 담합 제재", "입찰담합조사과", "2026-08-01")])
FTC_EXPLAIN_PAGE = ftc_page([
    ftc_row("1146", "설명", "48166", "20261029 [설명] 국민일보(10.29.) 기업 때리니 로펌대박 공정위 發 기이한 호황 등 기사 관련", "심판총괄담당관", "2026-10-29", key="13", ctg="03"),
    ftc_row("1145", "설명", "48161", "[설명] 한국경제(10.28.) 포스코 하도급 대금 관련 기사", "제조하도급과", "2026-10-28", key="13", ctg="03")])


def ftc_press_routes(fail=False, empty12=False):
    def lst(method, url, kw):
        p = kw.get("params") or {}
        if fail:
            return Resp("", 503)
        if p.get("key") == "13":
            return Resp(FTC_EXPLAIN_PAGE)
        return Resp(ftc_page([]) if empty12 or int(p.get("pageIndex", 1)) > 1 else FTC_PRESS_PAGE)
    return {w.FTC_PRESS: lst}


class FtcPressWatch(unittest.TestCase):
    def test_list_parsing(self):
        rows = w.parse_ftc_press(FTC_PRESS_PAGE, "12", "01,02")
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0], {"id": "ftcpress:48168", "title": "한세모빌리티 (주) 의 기술자료 관련 하도급법 위반행위 제재", "kind": "보도",
                                   "dept": "기술유용조사과", "date": "2026-10-30",
                                   "url": "https://www.ftc.go.kr/www/selectBbsNttView.do?bordCd=3&key=12&searchCtgry=01,02&nttSn=48168"})
        ex = w.parse_ftc_press(FTC_EXPLAIN_PAGE, "13", "03")
        self.assertEqual(ex[0]["title"], "[설명] 국민일보(10.29.) 기업 때리니 로펌대박 공정위 發 기이한 호황 등 기사 관련")  # 앞 날짜 뗌
        self.assertEqual(ex[0]["kind"], "설명")

    def test_beat_filter_names_and_window(self):
        items, check = w.ftc_press(CFG, NOW, None, http(ftc_press_routes()))
        by = {x["id"]: x for x in items}
        self.assertEqual(by["ftcpress:48163"]["companies"], ["현대차"])  # 출입처 이름
        self.assertIn("ftcpress:48160", by)  # 정유 업종 낱말
        self.assertEqual(by["ftcpress:48161"]["companies"], ["포스코"])  # 설명자료도 출입처 이름이면
        self.assertNotIn("ftcpress:48168", by)  # 출입처 밖 하도급 제재(회사 이름 속 '모빌리티'는 업종 낱말로 보지 않음)
        self.assertNotIn("ftcpress:48165", by)
        self.assertNotIn("ftcpress:48166", by)
        self.assertNotIn("ftcpress:47000", by)  # 60일 밖
        self.assertEqual((check["status"], check["listed"], check["kept"]), ("ok", 7, 3))
        self.assertFalse(any(x["isNew"] for x in items))  # 첫 실행은 기준선

    def test_new_only_after_baseline_and_failures_are_unconfirmed(self):
        first, _ = w.ftc_press(CFG, NOW, None, http(ftc_press_routes()))
        prev = {"ftcPress": [x for x in first if x["id"] != "ftcpress:48160"]}
        items, _ = w.ftc_press(CFG, NOW, prev, http(ftc_press_routes()))
        self.assertEqual([x["id"] for x in items if x["isNew"]], ["ftcpress:48160"])
        items, check = w.ftc_press(CFG, NOW, prev, http(ftc_press_routes(fail=True)))
        self.assertEqual(check["status"], "failed")
        self.assertEqual(len(items), len(prev["ftcPress"]))  # 이전 줄 유지
        _, check = w.ftc_press(CFG, NOW, None, http(ftc_press_routes(empty12=True)))
        self.assertEqual(check["status"], "partial")
        self.assertIn("보도·참고자료 목록 형식(행 없음)", check["error"])


# 11-01 운영 '2026년 10월 수출입 동향'(172360) 본문 형식(probe 83·84): 낱말마다 띄어 나오고 끝의 총 수출액에 괄호가 없다
OCT_BODY = ("<div>- 수출 2 개월 연속 1,100 억 달러 상회 * 10 월 수출 1,153 억 달러 (+93.7%) , 수입 728 억 달러 (+36.0%) , 수지 425 억 달러 흑자 "
            "* 1~10 월 누적 수출 9,300 억 달러 (+60.6%) , 수입 6,351 억 달러 (+21.4%) 【 품목 】 10 월에는 20 대 주력 수출품목 중 18 개 품목 수출이 증가했다 . "
            "【 10 월 20 대 주요품목별 수출액 ( 억 달러 ) 및 증감률 (%) 】 반도체 디스플레이 무선통신기기 컴퓨터 자동차 자동차부품 선박 564 (+259) 19 (+29) "
            "19 (+7) 59 (+497) 65 (+18) 17 (+15) 26 ( △ 44) 석유제품 석유화학 이차전지 일반기계 전기기기 철강 비철금속 69 (+80) 40 (+28) 7 (+38) 41 (+24) "
            "20 (+74) 23 (+22) 17 (+38) 농수산식품 화장품 생활용품 섬유 가전 바이오헬스 총 수출액 11 (+12) 14 (+58) 7 ( △ 13) 10 (+25) 6 (+6) 15 (+30) "
            "1,153 +94 (IT) 반도체 수출 (564.4 억 달러 , +259.4%) 은 … ( 모빌리티 ) 자동차 (65.5 억 달러 , +18.1%) 수출은 … 선박 (26.4 억 달러 , △ 43.6%) "
            "수출은 … 철강 (22.9 억 달러 , +22.3%) 수출은 … 전기기기 수출 (19.9 억 달러 , +74.0%) 은 …</div>")


class TradeOctoberFormat(unittest.TestCase):
    def test_spaced_body_parses(self):
        t = w.parse_trade(OCT_BODY)
        self.assertEqual(t["exports"], {"value": "1,153", "yoy": "+93.7"})
        self.assertEqual(t["imports"], {"value": "728", "yoy": "+36.0"})
        self.assertNotIn("tableError", t)
        self.assertEqual(t["items"]["자동차"], {"value": "65", "yoy": "+18"})
        self.assertEqual(t["items"]["선박"], {"value": "26", "yoy": "-44"})
        self.assertEqual(t["items"]["전기기기"], {"value": "20", "yoy": "+74"})
        self.assertEqual(len(t["items"]), 10)
        bad = w.parse_trade(OCT_BODY.replace("자동차부품 선박", "자동차부품"))
        self.assertIn("표 해석 실패", bad["tableError"])
        self.assertEqual(bad["items"]["자동차"], {"value": "65.5", "yoy": "+18.1", "from": "본문"})
        self.assertEqual(bad["items"]["전기기기"], {"value": "19.9", "yoy": "+74.0", "from": "본문"})  # '전기기기 수출 (…)'

    def test_failed_parse_is_read_again(self):
        prev = {"motir": [{"id": "motir:172254", "title": "2026년 9월 수출입 동향", "date": "2026-10-01", "companies": [],
                           "trade": {"period": "2026-09", "items": {}, "tableError": "표 해석 실패(이름 21·값 20)"}}]}
        items, _ = w.motir(CFG, NOW, prev, http(motir_routes()))
        trade = next(x for x in items if x["id"] == "motir:172254")["trade"]
        self.assertNotIn("tableError", trade)
        self.assertEqual(trade["exports"], {"value": "1,209.4", "yoy": "+83.5"})
        ok = {"motir": [{**prev["motir"][0], "trade": trade}]}
        calls = http(motir_routes())
        w.motir(CFG, NOW, ok, calls)
        self.assertFalse(any("/172254/view" in c[1] for c in calls.s.calls))  # 해석된 것은 다시 읽지 않음


def brief_row(nid, title, date, dept, code="A00019"):
    return (f'<li> <a href="/briefing/pressReleaseView.do?newsId={nid}&amp;pageIndex=1&amp;repCodeType={code[0]}&amp;repCode={code}&amp;startDate=2025-11-01'
            f'&amp;endDate=2026-11-01&srchWord=&amp;period="> <span class="text"> <strong>{title}</strong> <span class="lead"> ▷ 요약 문장 … </span> '
            f'<span class="source"> <span>{date}</span> <span>{dept}</span> </span> </span> </a> </li>')


def brief_page(rows):
    return f'<div class="list_type"> <ul> {"".join(rows)} </ul> </div>'


# 11-01 운영 목록 형식(probe 82·85): 부처 코드로 거른 쪽은 날짜가 '2026-10-30', 거르지 않은 쪽은 '2026.11.01'
ME_PAGE = brief_page([
    brief_row("156787389", "2026년 수소발전 입찰시장 개설", "2026-10-30", "기후에너지환경부"),
    brief_row("156787339", "고준위위원회, 고준위 방사성폐기물 관리시설 부적합지역 배제기준 확정", "2026-10-30", "기후에너지환경부"),
    brief_row("156786947", "국립생물자원관, 도시 야생동물과의 안전한 공존을 위한 과학적 관리 방안 모색", "2026-10-29", "기후에너지환경부"),
    brief_row("156786456", "자동차 연료첨가제, 민간 전문기관과 함께 철저히 관리한다", "2026-10-26", "기후에너지환경부"),
    brief_row("156786000", "현대제철 당진공장 배출권 할당 변경 공고", "2026-10-20", "기후에너지환경부")])
MOLIT_PAGE = brief_page([
    brief_row("156787238", "울산화력발전소 보일러타워 붕괴사고 조사결과", "2026-10-30", "국토교통부", "A00006"),
    brief_row("156787184", "&#039;26년 9월 주택통계", "2026-10-30", "국토교통부", "A00006"),
    brief_row("156787100", "기아 등 5개사 12개 차종 3만 2천여 대 자발적 시정조치(리콜)", "2026.10.29", "국토교통부", "A00006")])
CUSTOMS_PAGE = brief_page([brief_row("156787106", "관세청, 특송물품 악용한 마약밀수 차단을 위한 검사 강화 현장점검 실시", "2026-10-29", "관세청", "B00003")])
PPS_PAGE = brief_page([brief_row("156786754", "조달청, 한국수출입은행과 함께 공공비축 확대 나선다", "2026-10-28", "조달청", "B00013")])
MIXED_PAGE = brief_page([brief_row("156787418", "[연구행정 혁신+-⑨] 협력의 문은 넓게", "2026.11.01", "과학기술정보통신부")])


def briefing_routes(fail=None, mixed=None):
    def lst(method, url, kw):
        p = kw.get("params") or {}
        if p.get("repCode") == fail:
            return Resp("", 503)
        if int(p.get("pageIndex", 1)) > 1:
            return Resp(brief_page([]))
        if p.get("repCode") == mixed:
            return Resp(MIXED_PAGE)
        return Resp({"A00019": ME_PAGE, "A00006": MOLIT_PAGE, "B00003": CUSTOMS_PAGE, "B00013": PPS_PAGE}[p.get("repCode")])
    return {w.BRIEFING_LIST: lst}


class BriefingWatch(unittest.TestCase):
    def test_parse_and_filter(self):
        rows = w.parse_briefing(MOLIT_PAGE)
        self.assertEqual(rows[2], {"id": "briefing:156787100", "title": "기아 등 5개사 12개 차종 3만 2천여 대 자발적 시정조치(리콜)", "date": "2026-10-29",
                                   "ministry": "국토교통부", "url": "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156787100"})
        self.assertEqual(rows[1]["title"], "'26년 9월 주택통계")
        self.assertNotIn("요약", json.dumps(rows, ensure_ascii=False))  # 요약(lead)은 남기지 않는다
        items, check = w.briefing(CFG, NOW, None, http(briefing_routes()))
        by = {x["id"]: x for x in items}
        self.assertEqual(by["briefing:156787100"]["companies"], ["기아"])
        self.assertEqual(by["briefing:156786000"]["companies"], ["현대제철"])
        for kept in ("briefing:156787389", "briefing:156786456", "briefing:156787238"):
            self.assertIn(kept, by)  # 부처별 업종 낱말(수소발전·자동차·발전소)
        for dropped in ("briefing:156786947", "briefing:156787184", "briefing:156787339"):
            self.assertNotIn(dropped, by)
        self.assertIn("briefing:156786754", by)  # 조달청 공공비축
        self.assertNotIn("briefing:156787106", by)  # 관세청 마약 단속
        self.assertEqual((check["status"], check["listed"], check["kept"]), ("ok", 10, 6))
        self.assertFalse(any(x["isNew"] for x in items))

    def test_unfiltered_page_and_failure_are_unconfirmed(self):
        items, check = w.briefing(CFG, NOW, None, http(briefing_routes(mixed="A00006")))
        self.assertEqual(check["status"], "partial")
        self.assertIn("국토교통부 목록 형식(다른 부처 섞임)", check["error"])
        self.assertFalse(any(x["ministry"] == "국토교통부" for x in items))  # 섞인 쪽은 버림
        first, _ = w.briefing(CFG, NOW, None, http(briefing_routes()))
        prev = {"briefing": [x for x in first if x["id"] != "briefing:156787100"]}
        items, check = w.briefing(CFG, NOW, prev, http(briefing_routes(fail="A00019")))
        self.assertEqual(check["status"], "partial")
        self.assertEqual([x["id"] for x in items if x["isNew"]], ["briefing:156787100"])
        self.assertIn("briefing:156787389", {x["id"] for x in items})  # 실패한 부처의 이전 줄 유지


class BriefingTopicNarrowing(unittest.TestCase):
    def test_carbon_neutral_slogans_dropped_and_old_rows_refiltered(self):
        # 11-01 운영: '탄소'가 '탄소중립' 구호마다 걸려 친환경 가방·쓰레기 에너지 보도자료까지 잡혔다
        topic = re.compile(next(m["topic"] for m in CFG["briefing"]["ministries"] if m["name"] == "기후에너지환경부"))
        for title in ("친환경 가방 다시 쓰고, 잔반 줄이고… 미래세대의 탄소중립 제안 시범 적용", "쓰레기도 에너지가 된다… 탄소중립 시대, 새로운 해법 찾는다"):
            self.assertIsNone(topic.search(title), title)
        for title in ("기후대응위, 민관 협력으로 철강산업 저탄소 전환 해법 모색", "2026년 수소발전 입찰시장 개설", "석탄발전 폐지에 대응한 고용 안정과 일자리 전환 방안 논의"):
            self.assertIsNotNone(topic.search(title), title)
        prev = {"briefing": [{"id": "briefing:1", "title": "쓰레기도 에너지가 된다… 탄소중립 시대", "date": "2026-10-20", "ministry": "기후에너지환경부", "companies": []},
                             {"id": "briefing:2", "title": "현대차 사회공헌 협약", "date": "2026-10-20", "ministry": "기후에너지환경부", "companies": ["현대차"]}]}
        items, _ = w.briefing(CFG, NOW, prev, http(briefing_routes()))
        ids = {x["id"] for x in items}
        self.assertNotIn("briefing:1", ids)
        self.assertIn("briefing:2", ids)  # 출입처 이름이 있으면 둔다


class BriefingAgencies(unittest.TestCase):
    def test_customs_and_procurement_topics(self):
        # 11-01 운영 첫 쪽(probe 86): 마약·짝퉁·면세점은 빠지고 공공비축·원산지 세탁·우회수출은 남는다
        topic = {m["name"]: re.compile(m["topic"]) for m in CFG["briefing"]["ministries"]}
        self.assertEqual({m["code"] for m in CFG["briefing"]["ministries"]} >= {"B00003", "B00013"}, True)
        for title in ("관세청, 특송물품 악용한 마약밀수 차단을 위한 검사 강화 현장점검 실시", "2026년 면세점 쇼핑 축제 「코리아 듀티프리 페스타」 개막",
                      "관세청, 해외 관세당국과 'K-브랜드' 짝퉁 합동단속 및 마약 밀수 정보교환 체계 구축 추진"):
            self.assertIsNone(topic["관세청"].search(title), title)
        for title in ("중국산 철강재 원산지 세탁 우회수출 업체 적발", "관세청, 수입 강판 원산지 표시 위반 일제 점검"):
            self.assertIsNotNone(topic["관세청"].search(title), title)
        self.assertIsNotNone(topic["조달청"].search("조달청, 한국수출입은행과 함께 공공비축 확대 나선다"))
        for title in ("조달청, 11월 대형사업 총 342건, 2조 9,938억 원 상당 입찰 예정", "우리 아이들이 사용하는 칠판, 더 안전해진다"):
            self.assertIsNone(topic["조달청"].search(title), title)


class BriefingNewMinistryBaseline(unittest.TestCase):
    def test_added_ministry_first_read_is_baseline_and_sale_campaign_dropped(self):
        # 11-01 운영: 관세청·조달청을 더한 첫 실행 줄이 [신규]로 떴고, 관세청이 함께 낸 할인 행사 보도자료가 '자동차'로 잡혔다
        old_doc = {"briefing": [{"id": "briefing:156787389", "title": "2026년 수소발전 입찰시장 개설", "date": "2026-10-30", "ministry": "기후에너지환경부",
                                 "companies": []}],
                   "briefingRead": ["국토교통부", "기후에너지환경부"]}
        items, check = w.briefing(CFG, NOW, old_doc, http(briefing_routes()))
        new = {x["id"]: x["ministry"] for x in items if x["isNew"]}
        self.assertNotIn("조달청", new.values())  # 처음 읽은 청은 기준선
        self.assertIn("briefing:156787100", new)  # 이미 읽던 국토부의 새 줄은 신규
        self.assertEqual(check["read"], ["관세청", "국토교통부", "기후에너지환경부", "조달청"])
        sale = brief_page([brief_row("156786670", "자동차·가전부터 한우·수산물까지...최대 50% 할인 정부, 「제2회 코리아 그랜드 페스티벌」 시작(10.29~11.15)",
                                     "2026-10-27", "관세청", "B00003")])
        routes = briefing_routes()
        base = routes[w.BRIEFING_LIST]

        def with_sale(m, u, kw):
            p = kw.get("params") or {}
            return Resp(sale) if p.get("repCode") == "B00003" and int(p.get("pageIndex", 1)) == 1 else base(m, u, kw)
        routes[w.BRIEFING_LIST] = with_sale
        items, _ = w.briefing(CFG, NOW, None, http(routes))
        self.assertNotIn("briefing:156786670", {x["id"] for x in items})
        stale = {"briefing": [{"id": "briefing:156786670", "title": "자동차·가전부터 한우·수산물까지...최대 50% 할인", "date": "2026-10-27", "ministry": "관세청", "companies": []}]}
        items, _ = w.briefing(CFG, NOW, stale, http(briefing_routes()))
        self.assertNotIn("briefing:156786670", {x["id"] for x in items})  # 저장된 줄도 다시 거름


def ulsan_row(no, did, title, dept, date):
    return (f'<tr> <td class="re_blind7">{no}</td> <td class="ta_l" style="padding-left:0px;"> <a href="./view.do?mId=001004003001000000&amp;'
            f'bbsId=BBS_0000000000000027&amp;dataId={did}" onclick="fn_view(\'{did}\');return false;"> {title}</a> </td> '
            f'<td class="re_blind7">{dept}</td> <td> {date}</td> <td class="re_blind7">247</td> </tr>')


def cn_row(no, nid, title, dept, date):
    return (f'<tr> <td> {no} </td> <td class="td-subj"> <a href="/cnportal/cnapcPressList/cnapcPress/view.do?nttId={nid}&menuNo=500498&pageIndex=1" '
            f'class="tit" title="{title}">{title}</a> </td> <td> {dept}</td> <td>{date}</td> <td>99</td> </tr>')


def table(rows):
    return f"<table><tbody>{''.join(rows)}</tbody></table>"


# 11-01 운영 목록 형식(probe 88)
ULSAN_PAGE = table([ulsan_row("51814", "184854", "‘2026 KOREA 울산 세계궁도대회’개막", "체육지원과", "2026.10.30"),
                    ulsan_row("51813", "184850", "울산시, 고려아연과 온산제련소 이차전지 소재 증설 투자협약", "투자유치과", "2026.10.30"),
                    ulsan_row("51812", "184849", "석유화학 산업위기 대응 지역 협의회 개최", "산업정책과", "2026.10.29")])
CN_PAGE = table([cn_row("3089", "2185409", "충남도립대 건축인테리어학과, 강의실 밖에서 건축의 답 찾다", "충남도립대학교 교무학생처", "2026-10-31"),
                 cn_row("3088", "2185400", "도, 현대제철 당진제철소와 탄소중립 업무협약", "기후환경정책과", "2026-10-30")])


ULSAN_PAGE2 = table([ulsan_row("51804", "184800", "울산시, 에쓰오일 샤힌 프로젝트 준공 지원 점검", "산업정책과", "2026.10.29")])


def province_routes(fail=None, seen=None):
    def make(page, name, param, page2):
        def fn(method, url, kw):
            if seen is not None:
                seen.append((name, dict(kw.get("params") or {})))
            if name == fail:
                return ConnectionError("blocked")
            p = int((kw.get("params") or {}).get(param, 1))
            return Resp(page if p == 1 else page2 if p == 2 else table([]))
        return fn
    return {"https://www.ulsan.go.kr/u/rep/bbs/list.ulsan": make(ULSAN_PAGE, "울산광역시", "page", ULSAN_PAGE2),
            "https://www.chungnam.go.kr/cnportal/cnapcPressList/cnapcPress/list.do": make(CN_PAGE, "충청남도", "pageIndex", table([]))}


class ProvincePress(unittest.TestCase):
    def test_parse_filter_and_links(self):
        rows = w.parse_province(ULSAN_PAGE, CFG["provinces"]["sites"][0])
        self.assertEqual(rows[1], {"id": "province:울산광역시:184850", "site": "울산광역시", "title": "울산시, 고려아연과 온산제련소 이차전지 소재 증설 투자협약",
                                   "dept": "투자유치과", "date": "2026-10-30",
                                   "url": "https://www.ulsan.go.kr/u/rep/bbs/view.do?mId=001004003001000000&bbsId=BBS_0000000000000027&dataId=184850"})
        cn = w.parse_province(CN_PAGE, CFG["provinces"]["sites"][1])
        self.assertEqual(cn[1]["url"], "https://www.chungnam.go.kr/cnportal/cnapcPressList/cnapcPress/view.do?nttId=2185400&menuNo=500498&pageIndex=1")
        items, check = w.province(CFG, NOW, None, http(province_routes()))
        by = {x["id"]: x for x in items}
        self.assertEqual(by["province:울산광역시:184850"]["companies"], ["고려아연"])
        self.assertEqual(by["province:충청남도:2185400"]["companies"], ["현대제철"])
        self.assertIn("province:울산광역시:184849", by)  # 석유화학 + 위기
        self.assertNotIn("province:울산광역시:184854", by)
        self.assertNotIn("province:충청남도:2185409", by)
        self.assertEqual(by["province:울산광역시:184800"]["companies"], ["S-OIL"])  # 울산 2쪽('page' 칸)
        self.assertEqual((check["status"], check["listed"], check["kept"]), ("ok", 6, 4))
        self.assertFalse(any(x["isNew"] for x in items))
        seen = []
        w.province(CFG, NOW, None, http(province_routes(seen=seen)))
        self.assertEqual(seen, [("울산광역시", {}), ("울산광역시", {"page": 2}), ("울산광역시", {"page": 3}), ("충청남도", {"pageUnit": "30"})])

    def test_blocked_runner_is_unconfirmed_and_keeps_rows(self):
        first, _ = w.province(CFG, NOW, None, http(province_routes()))
        items, check = w.province(CFG, NOW, {"province": first, "provinceRead": ["울산광역시", "충청남도"]}, http(province_routes(fail="울산광역시")))
        self.assertEqual(check["status"], "partial")
        self.assertIn("울산광역시 ConnectionError", check["error"])
        self.assertIn("province:울산광역시:184850", {x["id"] for x in items})


class RunDoc(unittest.TestCase):
    def test_document_shape_and_unset_kepco_not_partial(self):
        routes = {**ftc_routes([KUMHO]), **komis_routes({"MNRL0023": komis_series("2026-01-01", "2026-10-26")}), **motir_routes(), **ftc_press_routes(), **briefing_routes(), **province_routes()}
        doc = w.run(flat_cfg(), now=NOW, previous=None, http=http(routes), kepco_key="")
        self.assertEqual(doc["schema"], "kr_signals/v1")
        self.assertEqual(doc["status"], "complete")
        self.assertEqual([c["source"] for c in doc["checks"]], ["공정위 의결서", "한전 전자입찰", "산업통상부 보도자료", "공정위 보도자료", "정책브리핑 부처 보도자료", "시·도 보도자료", "KOMIS 아연"])
        self.assertEqual(doc["confirmedScoops"], 0)
        self.assertTrue(isinstance(doc["prices"], list) and doc["prices"])


if __name__ == "__main__":
    unittest.main()
