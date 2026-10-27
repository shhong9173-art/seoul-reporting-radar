"""Assembly bills: name matching, newest-first paging to the lookback, baseline, stage events, failures not zero."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import assembly_watch as aw  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 28, 8, 40, tzinfo=KST)
CFG = json.loads(aw.CONFIG.read_text(encoding="utf-8"))


def bill(no, name, date, **extra):
    row = {"BILL_ID": f"PRC_{no}", "BILL_NO": str(no), "BILL_NAME": name, "COMMITTEE": None, "PROPOSE_DT": date,
           "PROC_RESULT": None, "AGE": "22", "DETAIL_LINK": f"https://likms.assembly.go.kr/bill/billDetail.do?billId=PRC_{no}",
           "PROPOSER": "홍길동의원 등 10인", "RST_PROPOSER": "홍길동"}
    row.update(extra)
    return row


class R:
    def __init__(self, body, code=200):
        self.body, self.status_code = body, code

    def json(self):
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def page(rows, total=20126):
    return {aw.SERVICE: [{"head": [{"list_total_count": total}, {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상 처리되었습니다."}}]},
                         {"row": rows}]}


PAGE1 = [bill(2222114, "조세특례제한법 일부개정법률안", "2026-10-26"),
         bill(2222113, "전기사업법 일부개정법률안", "2026-10-26"),
         bill(2222112, "자동차손해배상 보장법 일부개정법률안", "2026-10-25"),
         bill(2222111, "철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법 일부개정법률안", "2026-10-24"),
         bill(2222110, "산업안전보건법 일부개정법률안", "2026-10-23")]
PAGE2 = [bill(2222000, "전력망 확충 특별법 일부개정법률안", "2026-10-15"),
         bill(2221999, "자동차관리법 일부개정법률안", "2026-10-10")]   # older than 14 days → stop


class Fake:
    def __init__(self, pages, by_id=None, fail=None):
        self.pages, self.by_id, self.fail, self.calls = pages, by_id or {}, fail, []

    def __call__(self, url, params=None, timeout=None):
        self.calls.append(dict(params))
        if self.fail:
            return self.fail
        if "BILL_ID" in params:
            row = self.by_id.get(params["BILL_ID"])
            return R(page([row], 1) if row else {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}})
        i = int(params["pIndex"]) - 1
        return R(page(self.pages[i]) if i < len(self.pages) else {"RESULT": {"CODE": "INFO-200"}})


def go(fake, previous=None, now=NOW, key="SECRET"):
    return aw.run(CFG, now=now, previous=previous, key=key, get=fake, sleep=lambda s: None)


class Bills(unittest.TestCase):
    def test_name_matching_core_keyword_and_exclusions(self):
        self.assertEqual(aw.match("전기사업법 일부개정법률안", CFG)[0], "전력·에너지")
        self.assertEqual(aw.match("철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법안", CFG)[0], "철강·비철")
        self.assertEqual(aw.match("산업안전보건법 일부개정법률안", CFG), (None, ["산업안전"]))
        self.assertEqual(aw.match("자동차손해배상 보장법 일부개정법률안", CFG), (None, []))
        self.assertEqual(aw.match("조세특례제한법 일부개정법률안", CFG), (None, []))
        self.assertEqual(aw.law_of("철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법안"), "철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법")
        self.assertEqual(aw.law_of("전기사업법 일부개정법률안"), "전기사업법")

    def test_baseline_reads_to_lookback_and_keeps_only_beat_bills(self):
        fake = Fake([PAGE1, PAGE2])
        doc = go(fake)
        lst = doc["checks"][0]
        self.assertEqual((lst["status"], lst["pages"], lst["listed"], lst["kept"]), ("ok", 2, 7, 4))
        names = {b["law"] for b in doc["bills"]}
        self.assertIn("전력망 확충 특별법", names)
        self.assertNotIn("자동차관리법", names)  # 2026-10-10 is outside the 14-day window
        self.assertNotIn("조세특례제한법", names)
        self.assertEqual(doc["events"], [])
        self.assertFalse(any(b["isNew"] for b in doc["bills"]))
        self.assertTrue(doc["baselineSince"])
        self.assertTrue(all(c.get("KEY") == "SECRET" and c.get("AGE") == "22" for c in fake.calls))
        self.assertNotIn("SECRET", json.dumps(doc, ensure_ascii=False))

    def test_new_bill_and_stage_changes_become_events(self):
        first = go(Fake([PAGE1, PAGE2]))
        new = bill(2222200, "분산에너지 활성화 특별법 일부개정법률안", "2026-10-28")
        moved = bill(2222111, "철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법 일부개정법률안", "2026-10-24",
                     COMMITTEE="산업통상자원중소벤처기업위원회", COMMITTEE_DT="2026-10-27", CMT_PRESENT_DT="2026-10-28")
        later = NOW + dt.timedelta(hours=9)
        doc = go(Fake([[new] + [moved if r["BILL_NO"] == "2222111" else r for r in PAGE1], PAGE2]), previous=first, now=later)
        kinds = {(e["law"], e["kind"]) for e in doc["events"]}
        self.assertIn(("분산에너지 활성화 특별법", "발의"), kinds)
        self.assertIn(("철강산업 경쟁력 강화 및 탄소중립 전환을 위한 특별법", "소관위 상정"), kinds)
        ev = next(e for e in doc["events"] if e["kind"] == "소관위 상정")
        self.assertEqual((ev["core"], ev["from"], ev["date"]), ("철강·비철", "발의", "2026-10-28"))
        self.assertTrue(next(b for b in doc["bills"] if b["no"] == "2222200")["isNew"])

    def test_tracked_bill_outside_list_is_rechecked_by_id(self):
        first = go(Fake([PAGE1, PAGE2]))
        passed = bill(2222000, "전력망 확충 특별법 일부개정법률안", "2026-10-15", COMMITTEE_DT="2026-10-16", CMT_PRESENT_DT="2026-11-05",
                      CMT_PROC_DT="2026-11-06", LAW_SUBMIT_DT="2026-11-07", LAW_PRESENT_DT="2026-11-10", LAW_PROC_DT="2026-11-11",
                      PROC_DT="2026-11-12", PROC_RESULT="원안가결")
        later = dt.datetime(2026, 11, 13, 8, 40, tzinfo=KST)
        fake = Fake([[bill(2230000, "주택법 일부개정법률안", "2026-11-12")], [bill(2229000, "주택법 일부개정법률안", "2026-10-01")]],
                    by_id={"PRC_2222000": passed})
        doc = go(fake, previous=first, now=later)
        self.assertIn({"pIndex": 1, "pSize": 1, "AGE": "22", "BILL_ID": "PRC_2222000"},
                      [{k: v for k, v in c.items() if k not in ("KEY", "Type")} for c in fake.calls])
        ev = next(e for e in doc["events"] if e["billId"] == "PRC_2222000")
        self.assertEqual(ev["kind"], "본회의 원안가결")
        b = next(x for x in doc["bills"] if x["id"] == "PRC_2222000")
        self.assertEqual(b["stageIndex"], len(aw.STAGES))
        # Decided bills are not re-checked again.
        fake2 = Fake([[]], by_id={"PRC_2222000": passed})
        again = go(fake2, previous=doc, now=later + dt.timedelta(hours=9))
        self.assertNotIn("PRC_2222000", [c.get("BILL_ID") for c in fake2.calls])
        self.assertEqual(again["checks"][1]["tracked"], sum(1 for x in again["bills"] if x["stageIndex"] < len(aw.STAGES)))

    def test_failures_are_not_zero(self):
        doc = go(Fake([], fail=R({}, 500)))
        self.assertEqual(doc["checks"][0]["status"], "failed")
        self.assertIsNone(doc["baselineSince"])
        bad_key = go(Fake([], fail=R({"RESULT": {"CODE": "ERROR-290", "MESSAGE": "인증키가 유효하지 않습니다."}})))
        self.assertEqual(bad_key["checks"][0]["error"], "코드 ERROR-290")
        unset = go(Fake([]), key="")
        self.assertEqual(unset["status"], "unset")

    def test_page_cap_is_partial(self):
        recent = [bill(2222114 - i, "전기사업법 일부개정법률안", "2026-10-27") for i in range(3)]
        cfg = {**CFG, "maxPages": 2}
        doc = aw.run(cfg, now=NOW, key="k", get=Fake([recent, recent, recent]), sleep=lambda s: None)
        self.assertEqual(doc["checks"][0]["status"], "partial")
        self.assertIn("쪽 한도", doc["checks"][0]["error"])

    def test_stage_labels(self):
        self.assertEqual(aw.stage_of({"PROPOSE_DT": "2026-10-01"})[1], "발의")
        self.assertEqual(aw.stage_of({"COMMITTEE_DT": "2026-10-02", "CMT_PRESENT_DT": "2026-10-05", "CMT_PROC_DT": "2026-10-06",
                                      "CMT_PROC_RESULT_CD": "대안반영폐기"})[1], "소관위 처리(대안반영폐기)")
        self.assertEqual(aw.stage_of({"PROC_RESULT": "철회"})[1:], ("철회", ""))


if __name__ == "__main__":
    unittest.main()
