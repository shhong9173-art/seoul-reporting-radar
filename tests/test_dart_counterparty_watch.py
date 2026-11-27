"""타사 공시 속 출입처: 11-03 탐침 144~146 실제 원문 글자(국도화학 영업양수 결정 — ㈜LG화학 대산 BPA, 에스트래픽 영업양수결정 —
거래상대방 엘에스일렉트릭)로 판정·금액·맥락, 공급계약 계약상대 칸('기아 주식회사'), 같은 그룹 계열사 C, 출입처 자신의 공시 제외,
첫 실행 기준선, 본 접수번호 다시 안 읽기, 원문 실패는 다음 실행에 다시, 목록 실패는 미확인."""
import datetime as dt
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dart_counterparty_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 13, 50, tzinfo=KST)
STYLE = "<style>.xforms * { font-family: 돋움체;} .xforms td { padding-left:0px; }</style>"
KUKDO = (f"<html><head>{STYLE}</head><body>국도화학/영업양수 결정(종속회사의 주요경영사항)/(2026.10.26)영업양수 결정(종속회사의 주요경영사항) "
         "종속회사인 ㈜국도인터내셔널 의 주요경영사항 신고 <table><tr><td>1. 양수영업</td><td>㈜LG화학 대산 BPA 생산 및 판매 사업일체</td></tr>"
         "<tr><td>2. 양수영업 주요내용</td><td>㈜LG화학 대산 공장을 통해 영위하는 BPA사업 및 그 운영에 필요한 자산 등</td></tr>"
         "<tr><td>3. 양수가액(원)</td><td>78,437,000,000</td></tr><tr><td>4. 양수목적</td><td>BPA 수급 안정성 확보 및 시장 변동성 대응 역량 강화</td></tr></table></body></html>")
STRAFFIC = ("<html><body>영업양수 결정 <table><tr><td>거래상대방</td><td>회사명(성명)</td><td>엘에스일렉트릭 주식회사</td></tr>"
            "<tr><td>자본금(원)</td><td>150,000,000,000</td></tr><tr><td>주요사업</td><td>전기회로 개폐, 보호장치 제조업</td></tr></table>"
            "8. 양수대금지급 1. 총 양수대금: 74,536,000,000원 2. 지급형태 : 현금</body></html>")
SUPPLY = ("<html><body>단일판매ㆍ공급계약체결 <table><tr><td>계약상대</td><td>기아 주식회사</td></tr><tr><td>계약금액(원)</td><td>62,000,000,000</td></tr>"
          "<tr><td>체결계약명</td><td>전기차 배터리팩 하우징 공급</td></tr></table></body></html>")
GLOVIS = ("<html><body>단일판매ㆍ공급계약체결 <table><tr><td>계약상대</td><td>현대자동차 주식회사</td></tr><tr><td>계약금액(원)</td><td>900,000,000,000</td></tr>"
          "</table></body></html>")
NOPE = "<html><body>단일판매ㆍ공급계약체결 <table><tr><td>계약상대</td><td>삼성전자 주식회사</td></tr></table> 주요 고객: 현대자동차</body></html>"


def z(markup):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as f:
        f.writestr("doc.xml", markup)
    return b.getvalue()


ROWS = [
    {"corp_name": "국도화학", "report_nm": "영업양수결정(종속회사의주요경영사항)", "rcept_no": "20261026800562", "rcept_dt": "20261026"},
    {"corp_name": "에스트래픽", "report_nm": "[기재정정]주요사항보고서(영업양수결정)", "rcept_no": "20261029000111", "rcept_dt": "20261029"},
    {"corp_name": "디와이오토", "report_nm": "단일판매ㆍ공급계약체결", "rcept_no": "20261027900001", "rcept_dt": "20261027"},
    {"corp_name": "현대글로비스", "report_nm": "단일판매ㆍ공급계약체결", "rcept_no": "20261027900002", "rcept_dt": "20261027"},
    {"corp_name": "아무개전자", "report_nm": "단일판매ㆍ공급계약체결", "rcept_no": "20261027900003", "rcept_dt": "20261027"},
    {"corp_name": "현대모비스", "report_nm": "단일판매ㆍ공급계약체결", "rcept_no": "20261027900004", "rcept_dt": "20261027"},   # 출입처 자신 — 뺀다
    {"corp_name": "어떤회사", "report_nm": "전환사채발행후만기전사채취득", "rcept_no": "20261027900005", "rcept_dt": "20261027"},  # 종류 제외
    {"corp_name": "어떤회사", "report_nm": "기업설명회(IR)개최(안내공시)", "rcept_no": "20261027900006", "rcept_dt": "20261027"},
]
DOCS = {"20261026800562": KUKDO, "20261029000111": STRAFFIC, "20261027900001": SUPPLY, "20261027900002": GLOVIS, "20261027900003": NOPE}


class R:
    def __init__(self, body=None, content=b"", status=200):
        self.body, self.content, self.status_code = body, content, status

    def json(self):
        return self.body


def fake(rows, docs=DOCS, fail_docs=(), fail_list=False):
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, dict(params or {})))
        if url == w.LIST_API:
            if fail_list:
                raise type("ConnectTimeout", (Exception,), {})("x")
            return R({"status": "000", "total_page": 1, "list": rows} if params["pblntf_ty"] == "I" else {"status": "013"})
        rc = params["rcept_no"]
        if rc in fail_docs:
            raise type("ReadTimeout", (Exception,), {})("x")
        return R(content=z(docs[rc]))
    return get, calls


class Judge(unittest.TestCase):
    def test_real_texts(self):
        found, role, ctx, amount = w.judge(ROWS[0], [KUKDO])
        self.assertEqual((found, role, amount), (["LG화학"], "자산·영업·지분 거래 상대", 78437000000))
        self.assertIn("㈜LG화학 대산 BPA 생산 및 판매 사업일체", ctx)
        self.assertNotIn("xforms", ctx)
        found, role, ctx, amount = w.judge(ROWS[1], [STRAFFIC])
        self.assertEqual((found, role, amount), (["LS일렉트릭"], "자산·영업·지분 거래 상대", 74536000000))
        found, role, ctx, amount = w.judge(ROWS[2], [SUPPLY])
        self.assertEqual((found, role, amount), (["기아"], "공급계약 상대", 62000000000))
        self.assertIn("계약상대 기아 주식회사 · 계약명 전기차 배터리팩 하우징 공급", ctx)
        self.assertIsNone(w.judge(ROWS[4], [NOPE]))   # 계약상대는 다른 회사, 출입처는 회사 소개에만
        self.assertEqual(w.eok(78437000000), "약 784억원")
        self.assertEqual(w.eok(1250000000000), "약 1조2500억원")

    def test_name_rules(self):
        self.assertEqual(w.beats_in("주식회사 포스코퓨처엠"), [])
        self.assertEqual(w.beats_in("㈜포스코 광양제철소"), ["포스코"])
        self.assertEqual(w.beats_in("현대자동차써비스"), [])
        self.assertEqual(w.beats_in("기아대책"), [])
        self.assertEqual(w.beats_in("기아", loose=True), ["기아"])
        # DART 회사명(11-03 탐침 147) — 출입처 자신의 공시로 알아본다
        self.assertEqual(w.beats_in("S-Oil"), ["S-OIL"])
        self.assertEqual(w.beats_in("POSCO홀딩스"), ["포스코홀딩스"])
        self.assertEqual(w.beats_in("LS ELECTRIC"), ["LS일렉트릭"])
        self.assertEqual(w.beats_in("POSCO International"), [])
        self.assertFalse(w.KIND.search("영업(잠정)실적(공정공시)") and not w.SKIP_KIND.search("영업(잠정)실적(공정공시)"))


class Run(unittest.TestCase):
    def test_baseline_then_events_and_seen(self):
        get, calls = fake(ROWS[:1])
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        self.assertEqual((doc["status"], doc["events"]), ("complete", []))
        self.assertEqual([(x["company"], x["tier"], x.get("baseline")) for x in doc["items"]], [("LG화학", "A", True)])
        get2, calls2 = fake(ROWS)
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, key="k", get=get2, sleep=lambda s: None)
        opened = [p["rcept_no"] for u, p in calls2 if u == w.DOC_API]
        self.assertNotIn("20261026800562", opened)            # 본 접수번호는 다시 안 읽음
        self.assertNotIn("20261027900004", opened)            # 출입처 자신의 공시
        self.assertNotIn("20261027900005", opened)            # 종류 제외
        ev = {e["id"]: e for e in doc2["events"]}
        self.assertEqual(sorted((e["company"], e["tier"]) for e in ev.values()), [("LS일렉트릭", "A"), ("기아", "A")])
        st = ev["dcp:20261029000111"]
        self.assertEqual(st["kind"], "타사 공시 · 자산·영업·지분 거래 상대")
        self.assertEqual([w.subject_josa(x) for x in ("두산에너빌리티", "LG화학", "LS일렉트릭", "S-OIL")], ["두산에너빌리티가", "LG화학이", "LS일렉트릭이", "S-OIL이(가)"])   # 11-23
        self.assertIn("에스트래픽 공시 「[기재정정]주요사항보고서(영업양수결정)」(20261029) — LS일렉트릭이 자산·영업·지분 거래 상대 · 금액 74,536,000,000원(약 745억원)", st["text"])
        self.assertIn("상대 회사 공시(출입처 공시 아님)", st["text"])
        self.assertEqual(st["url"], "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20261029000111")
        glovis = [x for x in doc2["items"] if x["filer"] == "현대글로비스"][0]
        self.assertEqual((glovis["tier"], glovis["sameGroup"]), ("C", True))   # 같은 그룹 — 참고, 이벤트 없음
        self.assertNotIn("dcp:20261027900002", ev)
        self.assertNotIn("note", doc2["checks"][1])
        # 11-23: 새 후보가 없는 실행의 원문 0줄은 사유를 적는다(조용한 0건 '형식 변경 의심'에서 빠지게)
        get3, _ = fake(ROWS)
        doc3 = w.run(NOW + dt.timedelta(hours=6), doc2, key="k", get=get3, sleep=lambda s: None)
        self.assertEqual((doc3["checks"][1]["returned"], doc3["checks"][1]["note"]), (0, "새로 열어 볼 후보 공시 없음(공시검색 8건 중 거래·계약 종류의 새 공시 0건)"))
        self.assertNotIn("note", doc3["checks"][0])

    def test_rest_window_runs_are_not_counted_by_quiet_zero_watch(self):
        # 11-23: 토요일 03:52 늦은 예약 실행·월요일 02:54 push 실행(목록 1줄)이 '형식 변경 의심'으로 견줘졌다
        sat = dt.datetime(2026, 11, 21, 3, 52, tzinfo=KST)
        mon_early = dt.datetime(2026, 11, 23, 2, 54, tzinfo=KST)
        mon_work = dt.datetime(2026, 11, 23, 10, 50, tzinfo=KST)
        tue_early = dt.datetime(2026, 11, 24, 2, 54, tzinfo=KST)
        self.assertEqual([w.rest_window(t, frozenset()) for t in (sat, mon_early, mon_work, tue_early)], [True, True, False, False])
        self.assertTrue(w.rest_window(dt.datetime(2026, 12, 26, 3, 0, tzinfo=KST), frozenset({"2026-12-25"})))   # 공휴일 다음 날 새벽
        get, _ = fake(ROWS[:1])
        doc = w.run(mon_early, None, key="k", get=get, sleep=lambda s: None, holidays=frozenset())
        self.assertEqual([c.get("restDay") for c in doc["checks"]], [True, True])
        doc2 = w.run(mon_work, doc, key="k", get=get, sleep=lambda s: None, holidays=frozenset())
        self.assertEqual([c.get("restDay") for c in doc2["checks"]], [None, None])

    def test_failures(self):
        get, _ = fake(ROWS[:1])
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        get2, _ = fake(ROWS[:3], fail_docs=("20261029000111",))
        doc2 = w.run(NOW + dt.timedelta(hours=3), doc, key="k", get=get2, sleep=lambda s: None)
        self.assertNotIn("20261029000111", doc2["seen"])      # 원문 실패는 다음 실행에 다시
        self.assertEqual(doc2["status"], "partial")
        get3, _ = fake(ROWS, fail_list=True)
        self.assertEqual(w.run(NOW, doc, key="k", get=get3, sleep=lambda s: None)["status"], "failed")
        self.assertEqual(w.run(NOW, None, key="", get=get3, sleep=lambda s: None)["checks"][0]["status"], "not_configured")

    def test_document_failure_reasons_are_counted(self):
        # 11-27 운영: 후보 29건 중 23건 '원문 읽기 실패' — 응답 코드를 건수로 적는다(키·본문은 안 적음)
        rows = ROWS[:5]
        answers = {"20261029000111": R(content=rb'{"status":"014","message":"\ud30c\uc77c\uc774 \uc874\uc7ac\ud558\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4."}'),
                   "20261027900001": R(content="<result><status>014</status><message>파일이 존재하지 않습니다.</message></result>".encode()),
                   "20261027900002": R(content=b"", status=503),
                   "20261027900003": R(content="<result><status>020</status></result>".encode())}
        def get(url, params=None, headers=None, timeout=None):
            if url == w.LIST_API:
                return R({"status": "000", "total_page": 1, "list": rows} if params["pblntf_ty"] == "I" else {"status": "013"})
            return answers.get(params["rcept_no"]) or R(content=z(DOCS[params["rcept_no"]]))
        doc = w.run(NOW, None, key="k", get=get, sleep=lambda s: None)
        check = doc["checks"][1]
        self.assertEqual((check["status"], check["error"]), ("partial", "원문 읽기 실패 4건(DART 014 파일 없음 2 · DART 020 요청 제한 초과 1 · HTTP 503 1)"))
        self.assertEqual(sorted(doc["seen"]), ["20261026800562"])       # 실패한 공시는 다음 실행에 다시
        self.assertEqual(w.doc_error_reason(200, b"<html>oops</html>"), "ZIP 아닌 응답")
        self.assertEqual(w.doc_error_reason(200, b""), "빈 응답")
        self.assertEqual(w.doc_error_reason(200, b'{"status":"999"}'), "DART 999")

    def test_documents_the_api_never_serves_stop_after_tries_and_are_kept_as_titles(self):
        # 11-27 운영: 후보 24건 중 16건이 실행마다 'DART 014 파일 없음' — 같은 접수번호를 계속 다시 불렀다
        rows = ROWS[:3]
        no_doc = R(content="<result><status>014</status><message>파일이 존재하지 않습니다.</message></result>".encode())
        flaky = {"n": 0}
        def get(url, params=None, headers=None, timeout=None):
            if url == w.LIST_API:
                return R({"status": "000", "total_page": 1, "list": rows} if params["pblntf_ty"] == "I" else {"status": "013"})
            rc = params["rcept_no"]
            if rc == "20261029000111":
                return no_doc
            if rc == "20261027900001":
                flaky["n"] += 1
                return R(content=b"", status=503) if flaky["n"] <= 3 else R(content=z(DOCS[rc]))
            return R(content=z(DOCS[rc]))
        doc = None
        for i in range(w.NO_DOC_TRIES):
            doc = w.run(NOW + dt.timedelta(hours=3 * i), doc, key="k", get=get, sleep=lambda s: None)
            if i < w.NO_DOC_TRIES - 1:
                self.assertEqual((doc["docFails"]["20261029000111"]["n"], doc["checks"][1]["status"]), (i + 1, "partial"))
                self.assertNotIn("20261029000111", doc["seen"])
        self.assertIn("20261029000111", doc["seen"])          # 세 번째 '파일 없음'에서 그만 부른다
        self.assertNotIn("20261029000111", doc["docFails"])
        self.assertEqual([(u["rceptNo"], u["filer"], u["reason"], u["tries"]) for u in doc["unreadable"]], [("20261029000111", "에스트래픽", "DART 014 파일 없음", 3)])
        self.assertEqual(doc["checks"][1]["unreadable"], 1)
        self.assertIn("더 부르지 않음", doc["checks"][1]["note"])
        # 다른 실패(HTTP 503)는 횟수에 안 들고 계속 다시 본다 — 세 번째 실행까지 실패, 네 번째에 읽힘
        self.assertNotIn("20261027900001", doc["seen"])
        doc = w.run(NOW + dt.timedelta(hours=12), doc, key="k", get=get, sleep=lambda s: None)
        self.assertIn("20261027900001", doc["seen"])
        self.assertEqual((doc["docFails"], doc["checks"][1]["status"]), ({}, "ok"))
        self.assertEqual(len(doc["unreadable"]), 1)                # 남긴 제목은 보관 기간 동안 그대로

    def test_no_doc_filings_that_leave_the_list_window_are_kept_as_titles(self):
        # 금요일 오후 공시: 두 번 '파일 없음' 뒤 월요일 공시검색 창(어제·오늘)에 없어 세 번을 못 채운다
        no_doc = R(content="<result><status>014</status></result>".encode())
        def mk(rows, fail_list=False):
            def get(url, params=None, headers=None, timeout=None):
                if url == w.LIST_API:
                    if fail_list:
                        raise type("ConnectTimeout", (Exception,), {})("x")
                    return R({"status": "000", "total_page": 1, "list": rows} if params["pblntf_ty"] == "I" else {"status": "013"})
                return no_doc if params["rcept_no"] == "20261029000111" else R(content=z(DOCS[params["rcept_no"]]))
            return get
        doc = w.run(NOW, None, key="k", get=mk(ROWS[:2]), sleep=lambda s: None)
        doc = w.run(NOW + dt.timedelta(hours=3), doc, key="k", get=mk(ROWS[:2]), sleep=lambda s: None)
        self.assertEqual(doc["docFails"]["20261029000111"]["n"], 2)
        later = w.run(NOW + dt.timedelta(days=3), doc, key="k", get=mk(ROWS[:2], fail_list=True), sleep=lambda s: None)
        self.assertIn("20261029000111", later["docFails"])           # 목록 실패로 안 보인 것은 빠졌다고 치지 않는다
        doc = w.run(NOW + dt.timedelta(days=3), doc, key="k", get=mk(ROWS[:1]), sleep=lambda s: None)
        self.assertEqual([(u["rceptNo"], u["filer"], u["tries"], u["left"]) for u in doc["unreadable"]], [("20261029000111", "에스트래픽", 2, True)])
        self.assertEqual((doc["docFails"], doc["checks"][1]["unreadable"]), ({}, 1))


if __name__ == "__main__":
    unittest.main()
