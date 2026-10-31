"""대한 수입규제(무역협회 수입규제DB): 10-30 실제 목록 카드·상세 모양 그대로의 가짜 페이지로 카드·머리 표·진행 단계(최신 먼저)·업체 마진,
첫 실행 기준선, 새 사건(출입처 업체 → A, 출입 업종 → B, 나머지 C), 진행 갱신(출입처 → B, 업종 → C, 나머지 없음), 미국 한 단계 낮춤,
같은 단계 반복 없음, 옛 단계는 진행 아님, 실패는 미확인."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kita_watch as k  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 30, 7, 40, tzinfo=KST)
NOSLEEP = lambda s: None  # noqa: E731


def card(tir, country, item, inve, reg, kind, status):
    return (f'<li> <div class="cate d-none d-lg-flex"> <i class="icon-global" data-nation="XX"></i> <span class="caption pt-1">{country}</span> </div> '
            f'<div class="subject"> <a href="javascript:goDetailPage(\'{tir}\')" title="{item}">{item}</a> <div class="date"> '
            f'<p class="d-none d-lg-inline-block"> 조사개시일 : <span class="font-numbers">{inve}</span> </p> '
            f'<p class="d-none d-lg-inline-block"> 최근갱신일 : <span class="font-numbers">{reg}</span> </p> '
            f'<p class="d-lg-none"> {country} · <span class="font-numbers">{reg}</span>(최근갱신일) </p> </div> </div> '
            f'<div class="info caption-sm"> <ul> <li>규제유형 : {kind}</li> <li>규제상태 : {status}</li> </ul> </div> </li>')


def listing(cards):
    return '<ul class="board-list card">' + " ".join(cards) + "</ul>"


def stage(label, firms, note="", link="https://www.federalregister.gov/documents/2026/10/08/x"):
    rows = " ".join(f'<li> <dl> <dt>업체명</dt> <dd>{f}</dd> </dl> <dl> <dt>마진</dt> <dd>{m}</dd> </dl> <dl> <dt>비고</dt> <dd>{n}</dd> </dl> </li>'
                    for f, m, n in firms)
    return (f'<ul class="board-list board-accord box box-radius"> <li> <div class="subject subject-flex collapsed no-style" data-toggle="collapse" '
            f'data-target="#prgIndex_0" aria-expanded="false"> {label} </div> <div id="prgIndex_0" class="desc caption collapse"> <div> '
            f'<ul class="desc-wrap para mb-3"> {rows} </ul> <ul class="list-bull"> <li> {note} </li> </ul> '
            f'<p class="mt-2"> <a href="{link}" class="open-link" target="_blank"> 관련 링크 바로가기</a> </p> </div> </div> </li> </ul>')


def detail(case, country, kind, cat, status, stages):
    return (f'<table class="board-view"><tbody> <tr> <th><p>케이스 번호</p></th> <td colspan="3">{case}</td> </tr> '
            f'<tr> <th class="line-mo"><p>규제국</p></th> <td class="line-mo"> {country} <a href="/x" class="open-link"> 판정절차</a> </td> '
            f'<th><p>유형</p></th> <td class="desc"> <p>{kind}</p> </td> </tr> <tr> <th><p>품목 분류</p></th> <td>{cat}</td> '
            f'<th><p>규제 상태</p></th> <td>{status}</td> </tr> <tr> <th><p>HS코드</p></th> <td>7210.30.0030 7210.41.0000</td> </tr> </tbody></table> '
            '<div class="subject subject-flex collapsed no-style" data-target="#x"> 특이사항 </div> <div>메모</div> ' + " ".join(stages))


CRS = detail("A-580-878", "미국", "반덤핑", "철강/금속", "규제중", [
    stage("재심 · 예비판정(2026.10.08)", [("KG Dongbu Steel Co., Ltd", "23.40", ""), ("Dongkuk Coated Metal Co., Ltd./Aju Steel Co., Ltd", "19.43", ""),
                                       ("기타(All-Others)", "8.31", "현금예치율(Cash Deposit)")],
          "* DOC 9차 연례재심 예비판정<br>*Not Selected 기업 리스트<br>Hyundai Steel Company, POSCO"),
    stage("재심 · 최종판정(2026.05.14)", [("Hyundai Steel Company", "0.00", "미소마진")])])
EAEU = detail("SG-2026", "EAEU", "세이프가드", "철강/금속", "조사중", [stage("조사개시(2026.09.07)", [], "* 폴리머코팅 평판압연 세이프가드 조사 개시", "https://eec.eaeunion.org/x")])
RICE = detail("MG-1", "마다가스카르", "세이프가드", "농산물", "조사중", [stage("조사개시(2026.08.31)", [])])
IPA = detail("IN-ADD-1", "인도", "반덤핑", "화학", "조사중", [stage("조사개시(2026.09.28)", [("Isu Chemical", "-", "")])])


class Http:
    def __init__(self, cards, details, down=False):
        self.cards, self.details, self.down, self.calls = cards, details, down, []

    def post(self, url, data):
        self.calls.append((url, data.get("tirId")))
        if self.down:
            raise type("ConnectTimeout", (Exception,), {})("x")
        if url == k.LIST:
            return listing(self.cards)
        return self.details[data["tirId"]]


C_CRS = card("ROIL2021050005", "미국", "도금강판(Certain Corrosion-Resistant Steel Products)", "2015.06.30", "2026.10.26", "반덤핑", "규제중")
C_EAEU = card("ROIL2026100002", "EAEU", "폴리머코팅 평판압연(Flat Steel Products with Polymer Coating)", "2026.09.07", "2026.10.27", "세이프가드", "조사중")
C_RICE = card("ROIL2026100006", "마다가스카르", "현미, 반정미(Husked Rice)", "2026.08.31", "2026.10.29", "세이프가드", "조사중")
C_IPA = card("ROIL2026100001", "인도", "이소프로필 알코올(Isopropyl Alcohol)", "2026.09.28", "2026.10.27", "반덤핑", "조사중")
DET = {"ROIL2021050005": CRS, "ROIL2026100002": EAEU, "ROIL2026100006": RICE, "ROIL2026100001": IPA}


class Kita(unittest.TestCase):
    def test_cards_and_detail(self):
        cs = k.parse_cards(listing([C_CRS, C_EAEU]))
        self.assertEqual(cs[0], {"tirId": "ROIL2021050005", "country": "미국", "item": "도금강판(Certain Corrosion-Resistant Steel Products)",
                                 "investigated": "2015-06-30", "updated": "2026-10-26", "type": "반덤핑", "status": "규제중"})
        self.assertEqual((cs[1]["country"], cs[1]["status"]), ("EAEU", "조사중"))
        d = k.parse_detail(CRS)
        self.assertEqual((d["caseNo"], d["country"], d["type"], d["category"], d["status"]), ("A-580-878", "미국", "반덤핑", "철강/금속", "규제중"))
        self.assertEqual([(s["label"], s["date"]) for s in d["stages"]], [("재심 · 예비판정", "2026-10-08"), ("재심 · 최종판정", "2026-05-14")])
        self.assertEqual(d["stages"][0]["firms"][0], {"firm": "KG Dongbu Steel Co., Ltd", "margin": "23.40", "note": None})
        self.assertEqual(d["stages"][0]["link"], "https://www.federalregister.gov/documents/2026/10/08/x")
        self.assertEqual(k.beat_firms("KG Dongbu Steel / Dongkuk Coated Metal / Hyundai Steel Company, POSCO / POSCO Future M"),
                         ["KG스틸", "동국씨엠", "포스코", "현대제철"])

    def test_baseline_then_new_and_progress(self):
        http = Http([C_CRS, C_EAEU], DET)
        s1, ev1, c1 = k.collect(None, NOW, http, sleep=NOSLEEP)
        self.assertEqual((ev1, c1["status"], c1["detailsRead"]), ([], "ok", 0))  # 첫 실행은 기준선(상세 안 읽음)
        # 다음 실행: 새 사건 둘(EAEU 철강 B, 마다가스카르 쌀 C), 미국 도금강판 갱신(출입처 업체 마진 → B, 미국이라 한 단계 낮춰 C)
        old = dict(s1)
        http2 = Http([C_RICE, C_EAEU, C_CRS.replace("2026.10.26", "2026.10.28"), C_IPA], DET)
        s2, ev2, c2 = k.collect(old, NOW + dt.timedelta(days=1), http2, sleep=NOSLEEP)
        got = {e["kitaId"]: (e["kitaKind"], e["tier"]) for e in ev2}
        self.assertEqual(got, {"ROIL2026100006": ("새 대한 수입규제", "C"), "ROIL2026100001": ("새 대한 수입규제", "B"),
                               "ROIL2021050005": ("대한 수입규제 진행", "C")})
        crs = next(e for e in ev2 if e["kitaId"] == "ROIL2021050005")
        self.assertIn("최신 단계 재심 · 예비판정(2026-10-08): KG Dongbu Steel Co., Ltd 23.40%; Dongkuk Coated Metal Co., Ltd./Aju Steel Co., Ltd 19.43%", crs["text"])
        self.assertEqual(crs["companies"], ["KG스틸", "동국씨엠", "포스코", "현대제철"])  # 메모의 Not Selected 목록 포함
        self.assertEqual(crs["url"], "https://www.federalregister.gov/documents/2026/10/08/x")
        self.assertEqual(c2["detailsRead"], 3)  # EAEU는 갱신일이 그대로라 안 읽음
        # 같은 단계로 갱신일만 다시 바뀌면 이벤트 없음
        http3 = Http([C_CRS.replace("2026.10.26", "2026.10.30")], DET)
        _, ev3, _ = k.collect(s2, NOW + dt.timedelta(days=2), http3, sleep=NOSLEEP)
        self.assertEqual(ev3, [])

    def test_new_case_with_beat_firm_is_A_and_old_stage_is_not_progress(self):
        s1, _, _ = k.collect(None, NOW, Http([C_RICE], DET), sleep=NOSLEEP)
        firm_case = detail("C-1", "튀르키예", "반덤핑", "철강/금속", "조사중", [stage("조사개시(2026.10.20)", [("POSCO", "-", ""), ("Hyundai Steel Co.", "-", "")])])
        c_new = card("ROIL2026100010", "튀르키예", "열연강판(Hot-rolled)", "2026.10.20", "2026.10.30", "반덤핑", "조사중")
        _, ev, _ = k.collect(s1, NOW + dt.timedelta(days=1), Http([c_new, C_RICE], {**DET, "ROIL2026100010": firm_case}), sleep=NOSLEEP)
        self.assertEqual([(e["kitaId"], e["tier"]) for e in ev], [("ROIL2026100010", "A")])
        self.assertIn("출입처: 포스코·현대제철", ev[0]["text"])
        # 알고 있던 사건이 갱신됐지만 최신 단계가 60일보다 오래면 진행으로 보지 않는다
        s2, _, _ = k.collect(None, NOW, Http([C_CRS], DET), sleep=NOSLEEP)
        s2["cases"]["ROIL2021050005"]["latestStage"] = "다른|2020-01-01"
        old_stage = detail("A-580-878", "미국", "반덤핑", "철강/금속", "규제중", [stage("재심 · 최종판정(2026.05.14)", [("Hyundai Steel Company", "0.00", "")])])
        _, ev2, _ = k.collect(s2, NOW + dt.timedelta(days=1), Http([C_CRS.replace("2026.10.26", "2026.10.29")], {"ROIL2021050005": old_stage}), sleep=NOSLEEP)
        self.assertEqual(ev2, [])

    def test_failure_is_unconfirmed_and_keeps_state(self):
        s1, _, _ = k.collect(None, NOW, Http([C_CRS], DET), sleep=NOSLEEP)
        s2, ev, c = k.collect(s1, NOW + dt.timedelta(days=1), Http([C_CRS], DET, down=True), sleep=NOSLEEP)
        self.assertEqual((c["status"], ev, s2["stale"], s2["cases"]), ("failed", [], True, s1["cases"]))
        self.assertIn("ConnectTimeout", c["error"])


if __name__ == "__main__":
    unittest.main()
