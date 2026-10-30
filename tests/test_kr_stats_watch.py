"""KR monthly statistics: ECOS/KOSIS response layouts (live, 2026-10-27), KAIDA brand table parsing (unpublished month = zeros),
record statements with dates, year-on-year moves and streaks, KAIDA rank changes and overtakes, baseline (no events on the first run),
events only for a newly published month, unset keys kept as 미설정, failures kept as failures."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kr_stats_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 27, 7, 30, tzinfo=KST)
CFG = json.loads((Path(__file__).resolve().parents[1] / "data" / "kr_stats.json").read_text(encoding="utf-8"))


def months(start, end):
    out, p = [], start
    while p <= end:
        out.append(p)
        y, m = int(p[:4]), int(p[5:7]) + 1
        p = f"{y + (m > 12):04d}-{(m - 1) % 12 + 1:02d}"
    return out


def ecos_body(values, item="30712502AA", name="열연강대및강판", unit="2020=100", variants=(None,)):
    rows = []
    for p, v in values:
        for var in variants:
            rows.append({"STAT_CODE": "404Y016", "STAT_NAME": "4.1.1.3. 생산자물가지수(품목별)", "ITEM_CODE1": item, "ITEM_NAME1": name,
                         "ITEM_CODE2": var, "ITEM_NAME2": {"W": "원화기준", "C": "계약통화기준"}.get(var), "ITEM_CODE3": None, "ITEM_NAME3": None,
                         "ITEM_CODE4": None, "ITEM_NAME4": None, "UNIT_NAME": unit, "WGT": "1.1", "TIME": p.replace("-", ""),
                         "DATA_VALUE": str(v if var != "C" else v * 2)})
    return {"StatisticSearch": {"list_total_count": len(rows), "row": rows}}


def kosis_body(values, c1="조강", itm="16363AAA0", itm_nm="생산량", unit="천톤"):
    return [{"C1": "15363AA1AA", "C1_NM": c1, "DT": f"{v:g}", "ITM_ID": itm, "ITM_NM": itm_nm, "ORG_ID": "363", "PRD_DE": p.replace("-", ""),
             "PRD_SE": "M", "TBL_ID": "TX_36301_A000", "TBL_NM": "철강 생산량", "UNIT_NM": unit} for p, v in values]


def kaida_html(rows, total):
    cells = "".join(f'<tr>\r\n<td class="first leftnone"><a href="javascript:detailViewClick(\'{i:03d}\');">{b}</a></td>\r\n<td class="">{u:,}</td>\r\n'
                    f'<td class="">{(u / total * 100 if total else 0):.2f}</td>\r\n<td class="">0</td>\r\n</tr>\r\n' for i, (b, u) in enumerate(rows))
    return json.dumps({"newRegistVO": {"searchStart": "202609"}, "statisticsPopup":
                       f'<table class="statictics_list01 btmnone"><tr><th>Brand</th></tr></table><table>{cells}'
                       f'<tr>\r\n<td class="first leftnone">Total</td>\r\n<td class="">{total:,}</td>\r\n</tr></table>'})



def run(*a, **k):
    # 완성차 판매 엑셀은 test_carsales에서 따로 본다(여기 가짜 HTTP는 통계 원천만 흉내 낸다)
    return w.run(*a, car_sales=False, **k)


class Resp:
    def __init__(self, text="", status=200, payload=None):
        self.text, self.status_code, self._p = text, status, payload

    def json(self):
        return json.loads(self.text) if self._p is None else self._p


class Session:
    def __init__(self, fn):
        self.fn, self.calls = fn, []

    def request(self, method, url, *, timeout=None, **kw):
        self.calls.append((method, url, kw.get("params") or kw.get("data")))
        out = self.fn(method, url, kw)
        if isinstance(out, Exception):
            raise out
        return out


def http(fn):
    return w.Http(Session(fn), sleep=lambda s: None, gap=0)


def kaida_months(table):
    """table: {period: [(brand, units), …]} → route answering NewRegistListAjax by searchStart."""
    def fn(method, url, kw):
        if url == w.KAIDA_PAGE:
            return Resp("<html></html>")
        p = kw["data"]["searchStart"]
        rows = table.get(f"{p[:4]}-{p[4:]}")
        if rows is None:
            return Resp(kaida_html([("BMW", 0), ("Mercedes-Benz", 0)], 0))  # not yet published: zeros
        return Resp(kaida_html(rows, sum(u for _, u in rows)))
    return fn


class Signals(unittest.TestCase):
    def test_record_since_with_months_and_yoy_and_streak(self):
        ps = months("2023-01", "2026-09")
        vals = [100 + i for i in range(len(ps))]          # steady rise
        vals[ps.index("2024-02")] = 200                    # an old peak above today
        vals[-1] = 190
        pts = [{"p": p, "v": v} for p, v in zip(ps, vals)]
        summary, sig = w.series_signals(pts, CFG["signals"], 10)
        texts = {s["kind"]: s["text"] for s in sig}
        self.assertEqual(texts["최고(기간)"], "2024-02(200) 이후 최고 — 31개월 만")
        self.assertEqual(texts["전년 대비 큰 변동"], "전년 같은 달(2025-09, 132) 대비 +43.9%")
        self.assertTrue(texts["연속 증감"].startswith("전년 같은 달 대비"))
        self.assertIn("개월 연속 증가", texts["연속 증감"])
        self.assertEqual((summary["period"], summary["value"], summary["lastYear"]), ("2026-09", 190, 132))

    def test_no_record_when_last_higher_value_is_recent(self):
        pts = [{"p": p, "v": 100} for p in months("2024-01", "2026-08")] + [{"p": "2026-09", "v": 99}]
        pts[-2]["v"] = 98  # last month was lower → '최저' only if the low gap is long
        _, sig = w.series_signals(pts, CFG["signals"], 10)
        self.assertEqual([s["kind"] for s in sig], [])


class Sources(unittest.TestCase):
    def test_ecos_variant_filter_unit_and_name(self):
        vals = [(p, 100 + i) for i, p in enumerate(months("2025-01", "2026-09"))]
        h = http(lambda m, u, kw: Resp(payload=ecos_body(vals, variants=("W", "C", "D"))))
        s = {"stat": "402Y016", "item": "30712502AA", "variant": "W"}
        pts, unit, name = w.ecos_series(s, "k", "2016-01", NOW, h)
        self.assertEqual((len(pts), pts[-1], unit, name), (21, {"p": "2026-09", "v": 120.0}, "2020=100", "열연강대및강판"))

    def test_ecos_no_data_message_is_an_error(self):
        h = http(lambda m, u, kw: Resp(payload={"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}))
        with self.assertRaisesRegex(RuntimeError, "INFO-200"):
            w.ecos_series({"stat": "404Y016", "item": "X"}, "k", "2016-01", NOW, h)

    def test_kosis_rows_and_error(self):
        h = http(lambda m, u, kw: Resp(payload=kosis_body([("2026-07", 5600), ("2026-08", 5721)])))
        pts, unit, name = w.kosis_series({"org": "363", "tbl": "TX_36301_A000", "obj": "15363AA1AA", "itm": "16363AAA0"}, "k", "2016-01", NOW, h)
        self.assertEqual((pts[-1], unit, name), ({"p": "2026-08", "v": 5721.0}, "천톤", "조강 생산량"))
        h2 = http(lambda m, u, kw: Resp(payload={"err": "20", "errMsg": "필수요청변수값이 누락되었습니다."}))
        with self.assertRaisesRegex(RuntimeError, "필수요청변수"):
            w.kosis_series({"org": "363", "tbl": "T", "obj": "1", "itm": "2"}, "k", "2016-01", NOW, h2)

    def test_kaida_table_and_unpublished_month(self):
        t = w.parse_kaida(kaida_html([("BMW", 6066), ("Mercedes-Benz", 6500), ("BYD", 2614)], 34904))
        self.assertEqual(t["total"], 34904)
        self.assertEqual(t["brands"]["BMW"]["units"], 6066)
        self.assertIsNone(w.parse_kaida(kaida_html([("BMW", 0)], 0)))
        self.assertIsNone(w.parse_kaida("not json"))


class KaidaWatch(unittest.TestCase):
    def table(self):
        t = {}
        for i, p in enumerate(months("2022-10", "2026-08")):
            t[p] = [("Mercedes-Benz", 7000), ("BMW", 6500 + (i % 3)), ("Audi", 1500), ("Volkswagen", 1200), ("Honda", 300), ("BYD", 200), ("Volvo", 1300)]
        t["2026-09"] = [("Mercedes-Benz", 6000), ("BMW", 6066), ("Audi", 900), ("Volkswagen", 1100), ("Honda", 24), ("BYD", 2614), ("Volvo", 1250)]
        return t

    def test_rank_change_overtake_and_record_low_with_dates(self):
        cfg = json.loads(json.dumps(CFG))
        months_, check = w.kaida(cfg, NOW, None, http(kaida_months(self.table())))
        self.assertEqual(check["status"], "ok")
        self.assertEqual((check["latest"], check["months"]), ("2026-09", 48))
        self.assertEqual(check["notPublished"], ["2022-09"])  # asked 49 months back; the fixture starts a month later
        brands, sig = w.kaida_signals(months_, cfg, cfg["signals"])
        top = {r["brand"]: r for r in brands}
        self.assertEqual((top["BMW"]["rank"], top["BMW"]["prevRank"]), (1, 2))
        texts = [s["text"] for s in sig]
        self.assertIn("BMW 순위 2위 → 1위(2026-08 → 2026-09)", texts)
        self.assertIn("Mercedes-Benz 순위 1위 → 2위(2026-08 → 2026-09)", texts)
        self.assertIn("순위 역전: BYD 3위 · Audi 6위(2026-09) — 직전 달은 Audi 3위 · BYD 7위", texts)
        self.assertTrue(any(t.startswith("Honda 신규등록 24대 · 2022-10 이후 최저(조회 범위 안)") for t in texts), texts)
        self.assertFalse(any(s["brand"] == "Volvo" for s in sig))  # not a beat brand: only context for beat brands

    def test_next_runs_read_only_the_newest_two_months(self):
        cfg = json.loads(json.dumps(CFG))
        m1, _ = w.kaida(cfg, NOW, None, http(kaida_months(self.table())))
        s = Session(kaida_months(self.table()))
        w.kaida(cfg, NOW + dt.timedelta(days=1), {"kaidaMonths": m1}, w.Http(s, sleep=lambda x: None, gap=0))
        asked = [c[2]["searchStart"] for c in s.calls if c[1] == w.KAIDA_API]
        self.assertEqual(asked, ["202609", "202608"])  # no re-asking of old months the source never had


class RunDoc(unittest.TestCase):
    def route(self, ecos_vals, kosis_vals, kaida_table):
        kfn = kaida_months(kaida_table)

        def fn(method, url, kw):
            if url.startswith(w.ECOS_API):
                return Resp(payload=ecos_body(ecos_vals))
            if url.startswith(w.KOSIS_API):
                return Resp(payload=kosis_body(kosis_vals))
            return kfn(method, url, kw)
        return fn

    def small_cfg(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["ecos"], cfg["kosis"], cfg["census"] = cfg["ecos"][:1], cfg["kosis"][:1], cfg["census"][:1]
        return cfg

    def test_first_run_is_baseline_then_events_only_for_a_new_month(self):
        cfg = self.small_cfg()
        ps = months("2016-01", "2026-08")
        ecos_vals = [(p, 100.0) for p in ps]
        kosis_vals = [(p, 5000.0) for p in ps]
        table = {p: [("BMW", 6000), ("Mercedes-Benz", 6500)] for p in months("2022-10", "2026-08")}
        d1 = run(cfg, now=NOW, previous=None, http=http(self.route(ecos_vals, kosis_vals, table)), ecos_key="e", kosis_key="k")
        self.assertEqual(d1["events"], [])
        self.assertEqual(d1["status"], "complete")
        self.assertEqual([c["source"] for c in d1["checks"]], ["ECOS 통계", "KOSIS 통계", "CENSUS 통계", "KAIDA 수입 승용차 신규등록"])
        # same month again: nothing new
        d2 = run(cfg, now=NOW + dt.timedelta(days=1), previous=d1, http=http(self.route(ecos_vals, kosis_vals, table)), ecos_key="e", kosis_key="k")
        self.assertEqual(d2["events"], [])
        # September published: a drop to a record low and a rank swap
        ecos2 = ecos_vals + [("2026-09", 80.0)]
        table2 = {**table, "2026-09": [("BMW", 7000), ("Mercedes-Benz", 6500)]}
        d3 = run(cfg, now=NOW + dt.timedelta(days=2), previous=d2, http=http(self.route(ecos2, kosis_vals, table2)), ecos_key="e", kosis_key="k")
        texts = [e["text"] for e in d3["events"]]
        self.assertTrue(any(t.startswith("생산자물가 열연강대및강판 2026-09 80(2020=100) · 2016-01 이후 최저(조회 범위 안)") for t in texts), texts)
        self.assertTrue(any("전년 같은 달(2025-09, 100) 대비 -20.0%" in t for t in texts), texts)
        self.assertIn("KAIDA 2026-09 · BMW 순위 2위 → 1위(2026-08 → 2026-09)", texts)
        d4 = run(cfg, now=NOW + dt.timedelta(days=3), previous=d3, http=http(self.route(ecos2, kosis_vals, table2)), ecos_key="e", kosis_key="k")
        self.assertEqual(len(d4["events"]), len(d3["events"]))  # no repeats

    def test_unset_keys_and_failures(self):
        cfg = self.small_cfg()
        table = {p: [("BMW", 6000)] for p in months("2022-10", "2026-08")}
        d = run(cfg, now=NOW, previous=None, http=http(self.route([], [], table)), ecos_key="", kosis_key="")
        st = {c["source"]: c["status"] for c in d["checks"]}
        self.assertEqual((st["ECOS 통계"], st["KOSIS 통계"]), ("unset", "unset"))
        self.assertEqual(d["status"], "complete")  # unset is not a failure, and it is not zero either

        def broken(method, url, kw):
            if url.startswith(w.ECOS_API):
                return Resp("", 500)
            if url.startswith(w.KOSIS_API):
                return Resp(payload=kosis_body([("2026-08", 5721)]))
            return kaida_months(table)(method, url, kw)
        prev = {"series": [{"id": cfg["ecos"][0]["id"], "label": "old", "summary": {"period": "2026-07"}}]}
        d2 = run(cfg, now=NOW, previous=prev, http=http(broken), ecos_key="e", kosis_key="k")
        ecos = next(c for c in d2["checks"] if c["source"] == "ECOS 통계")
        self.assertEqual((ecos["status"], ecos["failed"]), ("failed", 1))
        self.assertIn("HTTP 500", ecos["error"])
        self.assertTrue(next(s for s in d2["series"] if s["id"] == cfg["ecos"][0]["id"])["stale"])


def census_rows(values, cty="5800", hs="8504"):
    head = ["GEN_VAL_MO", "CTY_CODE", "I_COMMODITY", "time", "CTY_CODE", "COMM_LVL", "I_COMMODITY"]
    return [head] + [[str(v), cty, hs, p, cty, "HS4", hs] for p, v in values]


class Census(unittest.TestCase):
    def test_monthly_value_in_million_dollars(self):
        vals = [("2026-07", 173209330), ("2026-08", 169833727)]  # live probe 2026-10-28 (HS 8504, KOREA, SOUTH)
        sess = Session(lambda m, u, kw: Resp(json.dumps(census_rows(vals))))
        pts, unit, name = w.census_series({"hs": "8504"}, "key", "2016-01", NOW, w.Http(sess, sleep=lambda s: None, gap=0))
        self.assertEqual(pts, [{"p": "2026-07", "v": 173.21}, {"p": "2026-08", "v": 169.83}])
        self.assertEqual(unit, "백만달러")
        self.assertIn("KOREA, SOUTH", name)
        params = sess.calls[0][2]
        self.assertEqual((params["CTY_CODE"], params["COMM_LVL"], params["I_COMMODITY"], params["time"]), ("5800", "HS4", "8504", "from 2016-01"))

    def test_empty_and_html_replies_are_errors(self):
        for body, msg in (("", "값 없음"), ("<html>Invalid Key</html>", "JSON 아님")):
            h = http(lambda m, u, kw, b=body: Resp(b))
            with self.assertRaisesRegex(RuntimeError, msg):
                w.census_series({"hs": "8504"}, "k", "2016-01", NOW, h)

    def test_series_added_to_an_existing_feed_starts_as_baseline(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["ecos"], cfg["kosis"], cfg["census"] = [], [], cfg["census"][:1]
        table = {p: [("BMW", 6000)] for p in months("2022-10", "2026-08")}
        ps = months("2016-01", "2026-07")
        vals = [(p, 100_000_000) for p in ps] + [("2026-08", 400_000_000)]  # a jump that would be a record

        def route(values):
            def fn(method, url, kw):
                if url.startswith(w.CENSUS_API):
                    return Resp(json.dumps(census_rows(values)))
                return kaida_months(table)(method, url, kw)
            return fn
        before = run(cfg | {"census": []}, now=NOW, previous=None, http=http(route(vals)))
        added = run(cfg, now=NOW + dt.timedelta(days=1), previous=before, http=http(route(vals)), census_key="c")
        self.assertEqual([e for e in added["events"] if e["series"] == cfg["census"][0]["id"]], [])
        row = next(s for s in added["series"] if s["id"] == cfg["census"][0]["id"])
        self.assertEqual((row["kind"], row["unit"], row["summary"]["value"]), ("trade", "백만달러", 400.0))
        nxt = run(cfg, now=NOW + dt.timedelta(days=30), previous=added, http=http(route(vals + [("2026-09", 500_000_000)])), census_key="c")
        texts = [e["text"] for e in nxt["events"] if e.get("series") == cfg["census"][0]["id"]]
        self.assertTrue(any(t.startswith("미국 수입(한국산) 변압기·전력변환기(HS 8504) 2026-09 500(백만달러) · 2016-01 이후 최고") for t in texts), texts)


if __name__ == "__main__":
    unittest.main()
