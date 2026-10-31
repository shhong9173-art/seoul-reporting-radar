"""법제처 공유서비스 감시: 10-31 탐침의 실제 응답 모양(AdmRulSearch·LawSearch·Expc, 태그 이름 그대로)으로
첫 실행 기준선(최근 45일만 목록에, 이벤트 없음), 다음 실행의 새 일련번호만 [신규], 오래된 발령일은 새것 아님, 부처·업종 걸러내기,
등급(출입 업종 부처+업종 낱말 B, 관세청 통관 사무 C, 법령은 제정·전부개정만 B, 해석례는 업종 낱말 B), 연결 실패 한 번 재시도,
오류 응답·전부 실패는 미확인, 쪽 상한, 시간 상한, kr_official run에 연결·실패 시 지난 목록 유지."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_official_watch as ko  # noqa: E402
import law_rules_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 2, 8, 10, tzinfo=KST)
NOSLEEP = lambda s: None  # noqa: E731


def admrul(seq, name, date, org="산업통상부", kind="고시", change="일부개정", no=None):
    no = no or f"2026-{seq[-3:]}"
    return (f"<admrul id=\"1\"><행정규칙일련번호>{seq}</행정규칙일련번호><행정규칙명>{name}</행정규칙명><행정규칙종류>{kind}</행정규칙종류>"
            f"<발령일자>{date}</발령일자><발령번호>{no}</발령번호><소관부처명>{org}</소관부처명><현행연혁구분>현행</현행연혁구분>"
            f"<제개정구분코드>1</제개정구분코드><제개정구분명>{change}</제개정구분명><행정규칙ID>99</행정규칙ID>"
            f"<행정규칙상세링크>/DRF/lawService.do?OC=x&amp;target=admrul&amp;ID={seq}</행정규칙상세링크><시행일자>{date}</시행일자><생성일자>{date}</생성일자></admrul>")


def law(seq, name, date, org="산업통상부", change="일부개정", kind="대통령령"):
    return (f"<law id=\"1\"><법령일련번호>{seq}</법령일련번호><현행연혁코드>현행</현행연혁코드><법령명한글>{name}</법령명한글><법령ID>1</법령ID>"
            f"<공포일자>{date}</공포일자><공포번호>1</공포번호><제개정구분명>{change}</제개정구분명><소관부처코드>1</소관부처코드>"
            f"<소관부처명>{org}</소관부처명><법령구분명>{kind}</법령구분명><시행일자>{date}</시행일자></law>")


def expc(seq, name, date):
    return (f"<expc id=\"1\"><법령해석례일련번호>{seq}</법령해석례일련번호><안건명>{name}</안건명><안건번호>26-0001</안건번호>"
            f"<질의기관명>산업통상부</질의기관명><질의기관코드>1</질의기관코드><회신기관명>법제처</회신기관명><회신기관코드>1</회신기관코드>"
            f"<회신일자>{date}</회신일자><법령해석례상세링크>/DRF/x</법령해석례상세링크></expc>")


ROOT = {"admrul": "AdmRulSearch", "law": "LawSearch", "expc": "Expc"}


def page(kind, rows, total=None):
    return (f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><{ROOT[kind]}><resultCode>00</resultCode><resultMsg>success</resultMsg>"
            f"<target>{kind}</target><totalCnt>{len(rows) if total is None else total}</totalCnt><page>1</page>{''.join(rows)}</{ROOT[kind]}>").encode()


class R:
    def __init__(self, code=200, content=b""):
        self.status_code, self.content = code, content


def fake(data, calls=None, fail=None):
    """data: {(kind, query): [rows] 또는 [[1쪽], [2쪽]]}. 없는 질의는 0건. fail: (kind, query) → 예외 목록(차례로)."""
    fail = {k: list(v) for k, v in (fail or {}).items()}

    def get(url, params=None, timeout=None):
        k = (params["target"], params["query"])
        if calls is not None:
            calls.append((k, params["pageNo"]))
        if fail.get(k):
            raise fail[k].pop(0)
        rows = data.get(k, [])
        if rows and isinstance(rows[0], list):
            total = sum(len(p) for p in rows)
            return R(content=page(k[0], rows[params["pageNo"] - 1], total))
        return R(content=page(k[0], rows))
    return get


def run(prev, data, now=NOW, **k):
    return w.collect(prev, now, "KEY", get=fake(data, **{x: k.pop(x) for x in ("calls", "fail") if x in k}), teams_of=ko.teams_of,
                     ministries=ko.BEAT_MINISTRIES, sleep=NOSLEEP, **k)


BASE = {("admrul", "전기"): [admrul("2100000270001", "전기설비기술기준", "20261023"),
                              admrul("2100000100000", "전기사업 회계규칙", "20230101")],
        ("admrul", "관세"): [admrul("2100000270002", "관세법 시행세칙 사무처리에 관한 고시", "20261020", org="관세청"),
                             admrul("2100000270003", "원산지표시제도 운영에 관한 고시", "20261021", org="관세청")],
        ("admrul", "자동차"): [admrul("2100000270004", "자동차 정비업 교육 규정", "20261022", org="교육부")],
        ("law", "전기"): [law("280001", "전기사업법 시행령", "20261015"), law("280002", "전기공사업법 시행규칙", "20261016", change="제정",
                                                                                     kind="산업통상부령")],
        ("expc", "전기"): [expc("330001", "산업통상부 - 「전기사업법」 제7조(발전사업 허가) 관련", "2026.10.20")]}


class Collect(unittest.TestCase):
    def test_first_run_is_baseline_with_recent_only(self):
        sec, check = run(None, BASE)
        self.assertEqual(check["status"], "ok")
        ids = {x["id"]: x for x in sec["items"]}
        self.assertNotIn("admrul:2100000100000", ids)            # 2023 발령 — 최근 아님
        self.assertNotIn("admrul:2100000270004", ids)            # 교육부 — 출입 부처 아님
        self.assertEqual(ids["admrul:2100000270001"]["tier"], "B")
        self.assertEqual(ids["admrul:2100000270002"]["tier"], "C")  # 관세청 통관 사무(공통 낱말만)
        self.assertEqual(ids["admrul:2100000270003"]["tier"], "B")  # 원산지
        self.assertEqual(ids["law:280001"]["tier"], "C")           # 법령 일부개정
        self.assertEqual(ids["law:280002"]["tier"], "B")           # 법령 제정
        self.assertEqual(ids["expc:330001"]["tier"], "B")
        self.assertEqual(ids["expc:330001"]["date"], "2026-10-20")
        self.assertFalse(any(x["isNew"] for x in sec["items"]))
        self.assertEqual(ids["admrul:2100000270001"]["url"], "https://www.law.go.kr/행정규칙/%EC%A0%84%EA%B8%B0%EC%84%A4%EB%B9%84%EA%B8%B0%EC%88%A0%EA%B8%B0%EC%A4%80")
        self.assertEqual(ids["expc:330001"]["url"], "https://www.law.go.kr/LSW/expcInfoP.do?expcSeq=330001")
        self.assertIn("admrul:2100000100000", sec["seen"])

    def test_next_run_marks_only_new_serials(self):
        first, _ = run(None, BASE)
        data = dict(BASE)
        # 개정되면 일련번호가 바뀐다(현행 목록에서 옛 번호는 빠짐)
        data[("admrul", "전기")] = [admrul("2100000280001", "전기설비기술기준", "20261030", change="일부개정"),
                                   admrul("2100000100000", "전기사업 회계규칙", "20230101"),
                                   admrul("2100000099999", "전력기술 관리 규정", "20200101")]  # 새로 보이지만 오래된 발령
        sec, check = run(first, data, now=NOW + dt.timedelta(days=1))
        new = [x for x in sec["items"] if x["isNew"]]
        self.assertEqual([x["id"] for x in new], ["admrul:2100000280001"])
        self.assertEqual(sec["baselineSince"], first["baselineSince"])
        self.assertTrue(any(x["id"] == "admrul:2100000270001" and not x["isNew"] for x in sec["items"]))

    def test_same_notice_number_is_grouped_and_industrial_complex_plans_are_c(self):
        # 운영 10-31: 산업통상부 고시 2026-118이 국가산업단지 관리기본계획 6곳으로 따로 올라와 B 6건
        data = {("admrul", "산업단지"): [admrul(f"21000002700{i}", f"국가산업단지 관리기본계획({n})", "20261022", no="2026-118")
                                        for i, n in enumerate(("구미", "석문", "빛그린"))]}
        sec, _ = run(None, data)
        main = [x for x in sec["items"] if not x.get("grouped")]
        self.assertEqual(len(main), 1)
        self.assertEqual((main[0]["siblings"], main[0]["tier"]), (2, "C"))
        self.assertEqual(sum(1 for x in sec["items"] if x.get("grouped") == main[0]["id"]), 2)

    def test_ministry_names_and_asker_prefix_are_not_beat_words(self):
        # 운영 10-31: 원안위 인사운영규정, '기후에너지환경부 - 낙동강수계 주민지원사업' 해석례가 전력·에너지 B
        data = {("admrul", "원자력"): [admrul("2100000271001", "원자력안전위원회 인사운영규정", "20261006", org="원자력안전위원회", kind="훈령"),
                                       admrul("2100000271002", "(원자력안전위원회) 사용후핵연료 저장ㆍ처분 안전성 확보를 위한 핵심기술개발 사업 운영관리규정",
                                              "20261026", org="원자력안전위원회", kind="훈령")],
                ("admrul", "자동차"): [admrul("2100000271003", "화물자동차 유가보조금 관리 규정", "20261001", org="국토교통부")],
                ("expc", "에너지"): [expc("343843", "기후에너지환경부 - 주민지원사업 중 간접지원사업의 지원대상 포함 여부", "2026.10.01"),
                                    expc("344169", "민원인 - 삼상유도전동기를 수입한 자가 「에너지이용 합리화법」 제15조제3항의 ‘수입업자’에 해당하는지 여부",
                                         "2026.10.29")]}
        sec, _ = run(None, data)
        ids = {x["id"]: x for x in sec["items"]}
        self.assertNotIn("admrul:2100000271001", ids)        # 업종 낱말 없음(부처 이름뿐)
        self.assertNotIn("expc:343843", ids)
        self.assertEqual(ids["admrul:2100000271002"]["tier"], "B")   # 핵연료
        self.assertEqual(ids["admrul:2100000271003"]["tier"], "C")   # 유가보조금
        self.assertEqual(ids["expc:344169"]["tier"], "B")

    def test_stored_items_are_retiered_with_current_rules(self):
        first, _ = run(None, BASE)
        x = next(x for x in first["items"] if x["id"] == "admrul:2100000270002")
        x["tier"] = "B"  # 예전 규칙으로 저장된 등급
        first["items"].append(dict(x, id="admrul:2100000270099", title="원자력안전위원회 인사운영규정", org="원자력안전위원회",
                                   teams=["전력·에너지"], tier="B"))
        sec, _ = run(first, BASE, now=NOW + dt.timedelta(days=1))
        self.assertEqual(next(x for x in sec["items"] if x["id"] == "admrul:2100000270002")["tier"], "C")
        old = next(x for x in sec["items"] if x["id"] == "admrul:2100000270099")
        self.assertEqual((old["tier"], old["teams"]), ("C", []))

    def test_paging_retry_and_errors(self):
        calls = []
        rows = [[admrul(f"21000002900{i:02d}", f"전기설비 규정 {i}", "20261025") for i in range(100)],
                [admrul("2100000291000", "전기설비 규정 끝", "20261025")]]
        import requests
        sec, check = run(None, {("admrul", "전기"): rows}, calls=calls, fail={("admrul", "가스"): [requests.ConnectionError("x")],
                                                                              ("admrul", "석유"): [requests.ConnectionError("x"), requests.ConnectionError("y")]})
        self.assertIn((("admrul", "전기"), 2), calls)
        self.assertEqual(sum(1 for x in sec["items"] if x["title"].startswith("전기설비 규정")), 101)
        self.assertEqual(check["status"], "partial")
        self.assertIn("행정규칙 '석유' 1쪽 ConnectionError", check["error"])
        self.assertNotIn("'가스'", check["error"])  # 한 번 실패는 재시도로 통과

    def test_error_response_and_page_cap(self):
        def get(url, params=None, timeout=None):
            return R(content=b"<OpenAPI_ServiceResponse><cmmMsgHeader><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>")
        sec, check = w.collect(None, NOW, "KEY", get=get, teams_of=ko.teams_of, ministries=ko.BEAT_MINISTRIES, sleep=NOSLEEP)
        self.assertEqual(check["status"], "failed")
        self.assertIn("totalCnt 없음", check["error"])
        big = [[admrul(f"2{p:02d}{i:03d}", f"전기 {p}-{i}", "20200101") for i in range(100)] for p in range(w.MAX_PAGES + 1)]
        _, check = run(None, {("admrul", "전기"): big})
        self.assertIn(f"행정규칙 '전기' {100 * (w.MAX_PAGES + 1)}건 중 {w.MAX_PAGES * 100}건", check["error"])

    def test_deadline_skips_remaining_queries(self):
        import time
        sec, check = run(None, BASE, deadline=time.monotonic() - 1)
        self.assertEqual((check["status"], check["returned"]), ("partial", 0))
        self.assertIn("시간 상한으로", check["error"])


class KrOfficialRun(unittest.TestCase):
    def cfg(self):
        return {"companies": []}

    def test_law_rules_ride_on_kr_official_and_keep_previous_when_all_fail(self):
        doc = ko.run(self.cfg(), "KEY", now=NOW, get=lambda *a, **k: R(500), law_key="LAWKEY", law_get=fake(BASE), sleep=NOSLEEP)
        self.assertIn("lawRules", doc)
        self.assertIn("법제처 행정규칙·법령·해석례", [c["source"] for c in doc["checks"]])
        self.assertTrue(any(x["id"] == "admrul:2100000270001" for x in doc["lawRules"]["items"]))

        def down(url, params=None, timeout=None):
            return R(503, b"")
        doc2 = ko.run(self.cfg(), "KEY", now=NOW + dt.timedelta(days=1), previous=doc, get=lambda *a, **k: R(500), law_key="LAWKEY", law_get=down, sleep=NOSLEEP)
        self.assertTrue(doc2["lawRules"]["stale"])
        self.assertEqual(len(doc2["lawRules"]["items"]), len(doc["lawRules"]["items"]))

    def test_without_law_key_previous_section_is_carried(self):
        doc = ko.run(self.cfg(), "KEY", now=NOW, previous={"lawRules": {"items": [], "seen": ["admrul:1"]}}, get=lambda *a, **k: R(500), sleep=NOSLEEP)
        self.assertEqual(doc["lawRules"]["seen"], ["admrul:1"])
        self.assertNotIn("법제처 행정규칙·법령·해석례", [c["source"] for c in doc["checks"]])


if __name__ == "__main__":
    unittest.main()
