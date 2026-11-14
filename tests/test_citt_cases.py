"""캐나다 CITT 진행 사건 일정: 사건마다 표 하나(탐침 242·243에서 본 꼴) → 한국 사건만, 기준선, 새 사건·문서 나옴·일정 바뀜·목록에서 빠짐."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import citt_cases as c  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 15, 7, 40, tzinfo=KST)
DEC = "https://decisions.citt-tcce.gc.ca/citt-tcce/ra/en/item"


def table(caption, rows):
    # 탐침 244(2026-11-15)에서 본 실제 마크업: 문서 칸은 <th scope="row">, 날짜 칸은 <td>, 머리줄은 th 두 칸
    body = "".join(f"<tr><th scope=\"row\">{f'<a href=\"{href}\">{doc}</a>' if href else doc}</th><td>{when}</td></tr>" for doc, when, href in rows)
    return f'<table class="table" style="width:100%;"><caption>{caption}</caption><thead><tr><th scope="row">Document</th><th scope="col">Date issued or updated</th></tr></thead><tbody>{body}</tbody></table>'


# 탐침 243(2026-11-15): 표 제목과 일정 줄 그대로(13건 중 일부)
TIRES = table("PI-2026-005&mdash;Truck and Bus Tires: dumping and subsidizing (China)",
              [("Notice of commencement of preliminary injury inquiry", "September 1, 2026", ""), ("Determination", "October 30, 2026", f"{DEC}/521608/index.do")])
POTATO = table("RR-2026-001—Certain Whole Potatoes: dumping (United States)", [("Notice of expiry review of order", "April 1, 2026", f"{DEC}/18674/index.do")])
SPT_ROWS = [("Notice of expiry review of finding", "October 1, 2026", f"{DEC}/18710/index.do"), ("Questionnaires", "March 1, 2027", ""),
            ("Public hearing", "Week of May 25, 2027", "/en/anti-dumping-injury-inquiries/public-hearings-anti-dumping-injury-inquiries#toc-id-2"), ("Order and reasons", "August 5, 2027", "")]
SPT = "RR-2026-007—Certain Small Power Transformers: dumping (Chinese Taipei and Korea)"


def page(tables_by_group):
    return ("<html><body><main><h1>Active dumping and subsidizing cases</h1><h2>Table of contents</h2><p>This page was last updated on November 12, 2026.</p>"
            + "".join(f"<h2>{g}</h2>" + "".join(ts) for g, ts in tables_by_group) + "</main></body></html>")


BASE = page([("Preliminary injury inquiries", [TIRES]), ("Expiry reviews", [POTATO, table(SPT, SPT_ROWS)])])


class Resp:
    def __init__(self, text="", status=200):
        self.text, self.status_code = text, status


def get_of(text, status=200):
    return lambda url, headers=None, timeout=None: Resp(text, status)


def run(prev, text, days=0, status=200):
    return c.collect(prev, NOW + dt.timedelta(days=days), get=get_of(text, status), sleep=lambda x: None)


class Citt(unittest.TestCase):
    def test_parse(self):
        cases, updated = c.parse(BASE)
        self.assertEqual(updated, "2026-11-12")
        self.assertEqual([(x["no"], x["group"], x["korea"]) for x in cases],
                         [("PI-2026-005", "Preliminary injury inquiries", False), ("RR-2026-001", "Expiry reviews", False), ("RR-2026-007", "Expiry reviews", True)])
        spt = cases[2]
        self.assertEqual(spt["title"], "Certain Small Power Transformers: dumping (Chinese Taipei and Korea)")
        self.assertEqual(spt["rows"], [
            {"doc": "Notice of expiry review of finding", "when": "October 1, 2026", "date": "2026-10-01", "url": f"{DEC}/18710/index.do"},
            {"doc": "Questionnaires", "when": "March 1, 2027", "date": "2027-03-01", "url": ""},
            {"doc": "Public hearing", "when": "Week of May 25, 2027", "date": "2027-05-25", "url": ""},      # 공청회 안내 쪽 링크는 문서가 나온 것이 아니다
            {"doc": "Order and reasons", "when": "August 5, 2027", "date": "2027-08-05", "url": ""}])
        self.assertEqual(cases[0]["title"], "Truck and Bus Tires: dumping and subsidizing (China)")
        self.assertEqual((c.iso_date("The week of October 26, 2026"), c.iso_date("TBD"), c.group_ko("Expiry reviews"), c.group_ko("Something")),
                         ("2026-10-26", "", "종료재심", "Something"))

    def test_first_read_is_baseline_and_only_korea_is_kept(self):
        sec, ev, chk = run(None, BASE)
        self.assertEqual(ev, [])
        self.assertEqual((chk["status"], chk["returned"], chk["total"], chk["baseline"], chk["updated"]), ("ok", 1, 3, True, "2026-11-12"))
        self.assertEqual(list(sec["cases"]), ["RR-2026-007"])
        sec2, ev2, chk2 = run(sec, BASE, days=1)
        self.assertEqual((ev2, chk2["baseline"], sec2["baselineAt"]), ([], False, sec["baselineAt"]))

    def test_td_only_rows_still_parse_and_header_row_is_skipped(self):
        old_style = BASE.replace('<th scope="row">', "<td>").replace("</th><td>", "</td><td>")
        self.assertEqual(c.parse(old_style)[0][2]["rows"], c.parse(BASE)[0][2]["rows"])
        self.assertNotIn("Document", [x["doc"] for x in c.parse(BASE)[0][2]["rows"]])

    def test_stored_case_without_rows_takes_rows_as_baseline(self):
        # 11-15 첫 운영 기준선은 줄을 못 읽어 rows가 비어 있었다 — 고친 뒤 첫 실행에서 '일정 줄이 새로 생김'을 내면 안 된다
        sec, _, _ = run(None, BASE)
        sec["cases"]["RR-2026-007"]["rows"] = []
        sec2, ev, chk = run(sec, BASE, days=1)
        self.assertEqual((ev, chk["moved"], chk["issued"]), ([], 0, 0))
        self.assertEqual(len(sec2["cases"]["RR-2026-007"]["rows"]), 4)
        moved = BASE.replace("August 5, 2027", "August 19, 2027")
        _, ev3, _ = run(sec2, moved, days=2)
        self.assertEqual([(e["id"], e["tier"]) for e in ev3], [("citt:RR-2026-007:moved:Order and reasons:2027-08-19", "B")])

    def test_changes(self):
        sec, _, _ = run(None, BASE)
        rows = [SPT_ROWS[0], ("Questionnaires", "March 15, 2027", ""), SPT_ROWS[2], ("Order and reasons", "August 19, 2027", ""),
                ("Notice of change of hearing", "November 20, 2026", f"{DEC}/18750/index.do")]
        pipe = table("NQ-2026-009—Carbon Steel Welded Pipe: dumping (Korea and Vietnam)", [("Notice of commencement of inquiry", "November 16, 2026", f"{DEC}/18760/index.do"),
                                                                                         ("Findings", "March 16, 2027", "")])
        sec2, ev, chk = run(sec, page([("Final injury inquiries", [pipe]), ("Expiry reviews", [POTATO, table(SPT, rows)])]), days=2)
        got = {e["id"]: e for e in ev}
        self.assertEqual(sorted(got), ["citt:NQ-2026-009:new", "citt:RR-2026-007:issued:Notice of change of hearing", "citt:RR-2026-007:moved:Order and reasons:2027-08-19",
                                       "citt:RR-2026-007:moved:Questionnaires:2027-03-15"])
        new = got["citt:NQ-2026-009:new"]
        self.assertEqual((new["tier"], new["label"], new["url"]), ("B", "캐나다 CITT 최종 피해 조사 NQ-2026-009", f"{DEC}/18760/index.do"))
        self.assertIn("새 한국산 사건 — Carbon Steel Welded Pipe: dumping (Korea and Vietnam) · 일정: Notice of commencement of inquiry 2026-11-16(나옴) · Findings 2027-03-16", new["text"])
        # 결정 예정일이 바뀐 것은 B, 질문서 날짜는 C, 결정이 아닌 문서가 나온 것은 C
        self.assertEqual(got["citt:RR-2026-007:moved:Order and reasons:2027-08-19"]["tier"], "B")
        self.assertIn("일정 바뀜: 「Order and reasons」 August 5, 2027 → August 19, 2027", got["citt:RR-2026-007:moved:Order and reasons:2027-08-19"]["text"])
        self.assertEqual(got["citt:RR-2026-007:moved:Questionnaires:2027-03-15"]["tier"], "C")
        self.assertEqual(got["citt:RR-2026-007:issued:Notice of change of hearing"]["tier"], "C")
        self.assertEqual((chk["newCases"], chk["issued"], chk["moved"], chk["gone"], chk["returned"]), (1, 1, 2, 0, 2))
        # 결정문이 나옴: 일정 줄에 결정 사이트 링크가 붙는다 → B. 그 뒤 진행 목록에서 빠지면 B 한 번
        done = [SPT_ROWS[0], ("Questionnaires", "March 15, 2027", ""), SPT_ROWS[2], ("Order and reasons", "August 19, 2027", f"{DEC}/19000/index.do"), rows[4]]
        sec3, ev3, _ = run(sec2, page([("Final injury inquiries", [pipe]), ("Expiry reviews", [POTATO, table(SPT, done)])]), days=280)
        self.assertEqual([(e["id"], e["tier"], e["url"]) for e in ev3], [("citt:RR-2026-007:issued:Order and reasons", "B", f"{DEC}/19000/index.do")])
        self.assertIn("문서 나옴: 「Order and reasons」(2027-08-19)", ev3[0]["text"])
        sec4, ev4, chk4 = run(sec3, page([("Final injury inquiries", [pipe]), ("Expiry reviews", [POTATO])]), days=290)
        self.assertEqual([(e["id"], e["tier"]) for e in ev4], [("citt:RR-2026-007:gone", "B")])
        self.assertIn("진행 사건 목록에서 빠짐: 결정이 나왔을 수 있음", ev4[0]["text"])
        self.assertEqual((list(sec4["cases"]), [g["no"] for g in sec4["gone"]], chk4["gone"]), (["NQ-2026-009"], ["RR-2026-007"], 1))
        _, ev5, _ = run(sec4, page([("Final injury inquiries", [pipe]), ("Expiry reviews", [POTATO])]), days=291)
        self.assertEqual(ev5, [])

    def test_failures_keep_previous(self):
        sec, _, _ = run(None, BASE)
        for text, status, why in [("", 503, "HTTP 503"), ("<main><p>maintenance</p></main>", 200, "사건 표 없음")]:
            sec2, ev, chk = run(sec, text, days=1, status=status)
            self.assertEqual((ev, chk["status"], sec2["status"], list(sec2["cases"])), ([], "failed", "failed", ["RR-2026-007"]))
            self.assertIn(why, chk["error"])
        self.assertEqual(run(None, "", status=503)[0], None)
        # 실패한 다음 실행에서 되살아나도 그사이 사건이 빠진 것으로 알리지 않는다
        sec3, ev3, _ = run(run(sec, "", days=1, status=503)[0], BASE, days=2)
        self.assertEqual((ev3, sec3["status"]), ([], "ok"))


if __name__ == "__main__":
    unittest.main()
