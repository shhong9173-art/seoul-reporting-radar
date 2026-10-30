"""완성차 모델별·공장별 판매(현대차·기아 IR 엑셀): 10-30 탐침 모양 그대로의 엑셀(openpyxl로 만든 가짜 파일)로
열 위치(현대차 B·C열, 기아 차종별 D열·기아 공장 C열), 아직 안 나온 달, 기아 제목 NFD, 세대 교체(아반떼 CN7→CN8),
판매 끊김 A(앨라배마 싼타페), 공장 출고 멈춤 A, 급감·급증 B, 계절 변동(전년 같은 달), 첫 실행 기준선, 같은 달 반복 없음, 304 재사용,
조회 실패는 직전 값 유지·미확인."""
import datetime as dt
import io
import json
import sys
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import carsales as cs  # noqa: E402
import kr_stats_watch as w  # noqa: E402

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 10, 30, 7, 30, tzinfo=KST)
MON = ["Jan.", "Feb.", "Mar.", "Apr.", "May.", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."]


def pad(vals, upto):
    v = [x if i < upto else None for i, x in enumerate(vals)]
    return v + [None] * (12 - len(v))


def hmc_rows(data, upto, kind):
    """현대차 모양: A 비움, B 구획·하위·합계, C 모델, D~O 1~12월, P 합계."""
    rows = [[None, f"Y2026 {'Unit Sales by Model' if kind == 'model' else 'Global Plant Sales'}"], [],
            [None, "Model" if kind == "model" else "Overseas Plants", None, *MON, "Total"], [], []]
    groups = []
    for (g, sub, label), vals in data.items():
        if g not in groups:
            groups.append(g)
    for g in groups:
        rows.append([None, g])
        rows.append([])
        last_sub, sums = None, [0] * 12
        for (gg, sub, label), vals in data.items():
            if gg != g:
                continue
            v = pad(vals, upto)
            sums = [a + (b or 0) for a, b in zip(sums, v)]
            if label is None:  # HTBC: 모델 없이 구분만
                rows.append([None, sub, None, *v, None])
                continue
            rows.append([None, sub if sub != last_sub else None, label, *v, None])
            last_sub = sub
        rows.append([None, None, "Sub-total", *pad(sums, upto), None])
        rows.append([None, "Total", None, *pad(sums, upto), None])
        rows.append([])
    rows.append([None, "Grand Total", None, *pad([1] * 12, upto), None])
    return rows


def kia_model_rows(data, upto):
    """기아 차종별: D열 모델, F열 합계, G~R 1~12월, 아래쪽 소계·구획 합계."""
    rows = [[None] * 15 + ["Kia IR"], [None, "Domestic+Export Sales by Model (Sales from Korean plants)"],
            [None, "CY 2026", None, None, None, "Total", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], []]
    for section in ("Domestic", "Export(excl CKD)"):
        for kind in ("Ordinary", "Special"):
            for (sec, k, label), vals in data.items():
                if sec == section and k == kind:
                    rows.append([None, None, None, f" {label}", None, sum(vals[:upto]), *pad(vals, upto)])
            rows.append([None, None, None, f"{kind} Vehicle", None, 0, *pad([0] * 12, upto)])
        rows.append([None, section, None, None, None, 0, *pad([0] * 12, upto)])
    rows.append([None, "Total(excl. CKD)", None, None, None, 0, *pad([0] * 12, upto)])
    return rows


def kia_plant_rows(data, upto):
    rows = [[None] * 15 + ["Kia IR"]]
    for plant in dict.fromkeys(p for p, _ in data):
        rows += [[], [None, f"{plant} Plant Sales (Ex-factory)"], [None, "CY 2026", None, None, "Total", *[m[:3] for m in MON]], []]
        sums = [0] * 12
        for (p, label), vals in data.items():
            if p == plant:
                v = pad(vals, upto)
                sums = [a + (b or 0) for a, b in zip(sums, v)]
                rows.append([None, None, label, None, sum(vals[:upto]), *v])
        rows.append([None, f"{plant} Plant", None, None, sum(sums), *[s if i < upto else 0 for i, s in enumerate(sums)]])  # 미래 달 0
    return rows


def xlsx(rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


HMC_MODEL_26 = {("Domestic", "PC", "Avante (CN7)"): [4287, 2975, 4612, 4678, 3417, 3255, 2239, 560, 12, 0],
                ("Domestic", "PC", "Avante (CN8)"): [0, 0, 0, 0, 0, 0, 0, 607, 6945, 7100],
                ("Domestic", "PC", "Sonata (DN8)"): [2766, 2564, 2833, 3025, 2241, 2804, 2788, 1642, 2163, 400],
                ("Domestic", "RV", "Grandeur (GN7)"): [2448, 1868, 3229, 2457, 3321, 2974, 2914, 900, 2376, 2400],
                ("Export", "RV", "Casper EV (AX EV)"): [4152, 3297, 3650, 4096, 2071, 3709, 4755, 3645, 4457, 11000]}
HMC_MODEL_25 = {("Domestic", "PC", "Avante (CN7)"): [3000] * 12, ("Domestic", "PC", "Avante (CN8)"): [0] * 12,
                ("Domestic", "PC", "Sonata (DN8)"): [2500] * 12,
                ("Domestic", "RV", "Grandeur (GN7)"): [2500] * 7 + [1000] + [2500] * 4,  # 지난해 8월도 낮음(휴가)
                ("Export", "RV", "Casper EV (AX EV)"): [4000] * 12}
HMC_PLANT_26 = {("HMMA", "Domestic", "GV70 (JKa)"): [2434, 3240, 2990, 2939, 3200, 2978, 399, 0, 0, 0],
                ("HMMA", "Domestic", "Santa-Fe (MX5a)"): [6629, 7210, 8181, 6031, 5937, 6303, 6767, 8272, 7538, 100],
                ("HTBC", "Domestic", None): [5, 5, 10, 2, 4, 4, 4, 4, 4, 4]}
HMC_PLANT_25 = {k: [3000] * 12 if "GV70" in str(k[2]) else [7000] * 12 if "Santa" in str(k[2]) else [5] * 12 for k in HMC_PLANT_26}
KIA_MODEL_26 = {("Domestic", "Ordinary", "Morning"): [2087, 1141, 1428, 3186, 2234, 1919, 3408, 1410, 2000],
                ("Domestic", "Ordinary", "Tasman"): [300, 320, 310, 330, 300, 350, 442, 378, 90],
                ("Domestic", "Special", "Tasman"): [0, 0, 0, 0, 0, 0, 0, 0, 0],
                ("Export(excl CKD)", "Ordinary", "Tasman"): [200, 210, 220, 230, 240, 250, 342, 252, 260]}
KIA_PLANT_26 = {("U.S.", "Sportage"): [9302, 9501, 9510, 10000, 9570, 9000, 7300, 8500, 8800],
                ("Mexico", "Tucson (HMC)"): [2008, 351, 0, 0, 0, 0, 0, 0, 0]}


class R:
    def __init__(self, status=200, payload=None, content=b"", lm=None):
        self.status_code, self._p, self.content = status, payload, content
        self.headers = {"Last-Modified": lm} if lm else {}

    def json(self):
        return self._p


class FakeHttp:
    """현대차 목록 POST·기아 목록 GET·엑셀 GET. month: 현대차가 올린 마지막 달, kia_month: 기아 마지막 달."""

    def __init__(self, month=9, kia_month=8, kia_down=False):
        self.month, self.kia_month, self.kia_down, self.calls = month, kia_month, kia_down, []

    def files(self):
        name = ["", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "september", "october"][self.month]
        return {f"/c/2026/hmc-sales-by-model-{name}-y2026.xlsx": (hmc_rows(HMC_MODEL_26, self.month, "model"), f"LM-26m-{self.month}"),
                f"/c/2026/hmc-global-plant-sales-{name}-y2026.xlsx": (hmc_rows(HMC_PLANT_26, self.month, "plant"), f"LM-26p-{self.month}"),
                "/c/2025/hmc-sales-by-model-dec-y2025.xlsx": (hmc_rows(HMC_MODEL_25, 12, "model"), "LM-25m"),
                "/c/2025/hmc-global-plant-sales-dec-y2025.xlsx": (hmc_rows(HMC_PLANT_25, 12, "plant"), "LM-25p"),
                f"k/{self.kia_month}/model.xlsx": (kia_model_rows(KIA_MODEL_26, self.kia_month), f"LM-k{self.kia_month}"),
                f"k/{self.kia_month}/plant.xlsx": (kia_plant_rows(KIA_PLANT_26, self.kia_month), f"LM-kp{self.kia_month}")}

    def call(self, method, url, *, timeout=40, ok=(200,), **kw):
        self.calls.append((method, url, (kw.get("headers") or {}).get("If-Modified-Since")))
        if url == cs.HMC_LIST:
            year = kw["data"]["year"]
            paths = [p for p in self.files() if f"/{year}/" in p]
            return R(payload={"data": {"list": [{"year": year, "attrSalesModelValue": next(p for p in paths if "model" in p),
                                                 "attrGlobalPlantValue": next(p for p in paths if "plant" in p)}]}}), None
        if url == cs.KIA_LIST:
            if self.kia_down:
                return None, "ReadTimeout"
            nfd = lambda t: unicodedata.normalize("NFD", t)  # noqa: E731 — 기아 목록 제목은 NFD로 온다(10-30 탐침)
            return R(payload={"data": {"list": [{"type": "sales", "year": 2026, "files": [
                {"title": nfd("2026 차종별판매실적.xlsx"), "path": f"k/{self.kia_month}/model.xlsx"},
                {"title": nfd("2026 해외공장판매실적.xlsx"), "path": f"k/{self.kia_month}/plant.xlsx"},
                {"title": nfd("2026 지역별수출실적.xlsx"), "path": "k/region.xlsx"}]},
                {"type": "business", "year": 2026, "files": []}]}}), None
        path = url.replace(cs.HMC_HOST, "").replace(cs.KIA_FILES, "")
        rows, lm = self.files()[path]
        if (kw.get("headers") or {}).get("If-Modified-Since") == lm and 304 in ok:
            return R(304), None
        return R(content=xlsx(rows), lm=lm), None


def series(block, label, scope=None):
    return next(s for s in block["series"] if s["label"] == label and (scope is None or s["scope"] == scope))


class Parsing(unittest.TestCase):
    def test_hmc_model_and_plant_columns(self):
        rows = cs.parse_hmc(hmc_rows(HMC_MODEL_26, 9, "model"), "model")
        self.assertEqual([(x["group"], x["label"]) for x in rows][:3], [("Domestic", "Avante (CN7)"), ("Domestic", "Avante (CN8)"), ("Domestic", "Sonata (DN8)")])
        self.assertFalse(any(x["label"] in ("Sub-total", "Total", "Grand Total") for x in rows))
        self.assertEqual(cs.last_month(rows), 9)
        self.assertEqual(rows[1]["values"][9], 6945)
        plant = cs.parse_hmc(hmc_rows(HMC_PLANT_26, 9, "plant"), "plant")
        self.assertIn(("HMMA", "Domestic", "GV70 (JKa)", False), [(x["group"], x["sub"], x["label"], x["total"]) for x in plant])
        self.assertIn(("HTBC", "Domestic", "전체", False), [(x["group"], x["sub"], x["label"], x["total"]) for x in plant])
        tot = next(x for x in plant if x["total"] and x["group"] == "HMMA")
        self.assertEqual(tot["values"][9], 7538)
        self.assertEqual(cs.scope_of("hmc", "plant", tot), "미국 앨라배마 공장")
        self.assertEqual(cs.scope_of("hmc", "plant", {"group": "HMMA", "sub": "Domestic"}), "미국 앨라배마 공장 현지 판매")

    def test_kia_model_sections_come_after_rows(self):
        rows = cs.parse_kia_model(kia_model_rows(KIA_MODEL_26, 8))
        got = {(x["group"], x["label"]): x["values"].get(8) for x in rows}
        self.assertEqual(got[("Domestic", "Tasman")], 378)
        self.assertEqual(got[("Domestic", "Tasman (특수)")], 0)
        self.assertEqual(got[("Export(excl CKD)", "Tasman")], 252)
        self.assertEqual(cs.last_month(rows), 8)
        self.assertEqual(cs.scope_of("kia", "model", {"group": "Export(excl CKD)", "sub": ""}), "국내 공장 수출(CKD 제외)")

    def test_kia_plant_future_zero_in_total_is_not_a_month(self):
        rows = cs.parse_kia_plant(kia_plant_rows(KIA_PLANT_26, 8))
        us = next(x for x in rows if x["total"] and x["group"] == "U.S.")
        self.assertEqual(us["values"][9], 0)  # 합계 행은 9월에 0을 채운다
        self.assertEqual(cs.last_month(rows), 8)  # 그래도 마지막 달은 모델 행 기준 8월
        self.assertEqual(cs.scope_of("kia", "plant", us), "미국 조지아 공장 출고")

    def test_family(self):
        self.assertEqual(cs.family("Avante (CN7)"), cs.family("Avante (CN8)"))
        self.assertEqual(cs.family("Avante (CN7 HEV)"), cs.family("Avante (CN8 HEV)"))
        self.assertNotEqual(cs.family("Avante (CN8)"), cs.family("Avante (CN8 HEV)"))
        self.assertNotEqual(cs.family("IONIQ 5 (NE)"), cs.family("IONIQ 5 N (NE N)"))


def ser(scope, label, vals, start="2025-08", total=False, maker="hmc", kind="model"):
    months, ym = {}, start
    for v in vals:
        months[ym] = v
        ym = cs.ym_add(ym, 1)
    return {"id": f"{maker}:{kind}:{scope}:{label}", "maker": maker, "kind": kind, "scope": scope, "label": label, "total": total, "months": months}


class Signals(unittest.TestCase):
    """10-30 실제 엑셀로 돌려 본 결과(현대차 8월 수출 모델 17건 등)에서 고친 규칙."""

    def test_whole_scope_drop_is_one_line_and_only_clearly_worse_models_stand_out(self):
        # 2025-08~2026-08 13개월. 2026-08에 수출 전체가 절반으로(파업·휴가 등) — 모델마다 띄우지 않는다
        norm = [3000] * 12
        rows = [ser("국내 공장 수출", "Tucson (NX4 HEV)", norm + [1500]), ser("국내 공장 수출", "Venue (QX)", norm + [1400]),
                ser("국내 공장 수출", "Sonata (DN8)", norm + [1450]), ser("국내 공장 수출", "Palisade (LX3)", norm + [400])]
        got = {(x["label"], x["signal"]) for x in cs.signals(rows, "hmc", "model", "2026-08")}
        self.assertEqual(got, {("전체", "구분 전체 급감"), ("Palisade (LX3)", "급감")})
        whole = next(x for x in cs.signals(rows, "hmc", "model", "2026-08") if x["signal"] == "구분 전체 급감")
        self.assertEqual(whole["text"], "현대차 국내 공장 수출 전체(모델 4개 합) 2026-08 4,750대 — 직전 3개월 평균 12,000대의 40%, 전년 같은 달 12,000대(40%). "
                                        "모델 대부분이 함께 줄었다(파업·휴가·선적 일정 여부는 회사 확인)")
        pal = next(x for x in cs.signals(rows, "hmc", "model", "2026-08") if x["label"] == "Palisade (LX3)")
        self.assertIn("· 같은 구분 전체는 40%", pal["text"])

    def test_stop_tier_and_tiny_sibling_is_not_a_generation_change(self):
        rows = [ser("인도 공장 수출", "i20 (BI3 5DR)", [700] * 12 + [30], kind="plant"),
                ser("인도 공장 현지 판매", "Creta (SU2i)", [15000] * 12 + [300], kind="plant"),
                ser("인도 공장 현지 판매", "Venue (QU2i)", [11000] * 13, kind="plant"),
                ser("국내 공장 수출", "Avante (CN7)", [14000] * 12 + [4700]), ser("국내 공장 수출", "Avante (CN8)", [0] * 12 + [1]),
                ser("국내 공장 수출", "Kona (SX2)", [9000] * 13)]
        got = {(x["label"], x["signal"], x["tier"]) for x in cs.signals(rows, "hmc", "plant", "2026-08")}
        self.assertIn(("i20 (BI3 5DR)", "판매 끊김", "B"), got)  # 수출·소량: B
        self.assertIn(("Creta (SU2i)", "판매 끊김", "A"), got)    # 현지 판매·평균 1,000대 이상: A
        m = {(x["label"], x["signal"]) for x in cs.signals(rows, "hmc", "model", "2026-08")}
        self.assertIn(("Avante (CN7)", "급감"), m)  # CN8 1대는 세대 교체 근거가 아니다
        self.assertNotIn(("Avante (CN7)", "세대 교체로 보임"), m)

    def test_plant_total_deep_drop_is_a(self):
        # 운영 10-30: 현대차 HMGMA 2026-09 1,121대 — 직전 3개월 평균 3,707·전년 같은 달 4,027
        hmgma = ser("미국 조지아(HMGMA) 공장", "공장 합계", [4027] + [3700] * 9 + [3600, 3821, 1121], start="2025-09", total=True, kind="plant")
        mild = ser("체코 공장", "공장 합계", [25000] * 12 + [15000], start="2025-09", total=True, kind="plant")
        got = {(x["scope"], x["signal"], x["tier"]) for x in cs.signals([hmgma, mild], "hmc", "plant", "2026-09")}
        self.assertIn(("미국 조지아(HMGMA) 공장", "공장 급감", "A"), got)
        self.assertIn(("체코 공장", "공장 급감", "B"), got)  # 60%: 30% 넘게 줄었지만 40% 아래는 아님
        a = next(x for x in cs.signals([hmgma], "hmc", "plant", "2026-09"))
        self.assertTrue(a["text"].endswith("공장 합계가 평소의 40% 아래"))

    def test_ramp_up_of_last_years_new_model_is_not_a_surge(self):
        rows = [ser("국내 공장 수출", "Palisade (LX3 HEV)", [229] + [5000] * 11 + [11484]), ser("국내 공장 수출", "GV70 (JK)", [1700] * 12 + [3797])]
        got = {(x["label"], x["signal"]) for x in cs.signals(rows, "hmc", "model", "2026-08")}
        self.assertEqual(got, {("GV70 (JK)", "급증")})


class Collect(unittest.TestCase):
    def run_cs(self, prev, http, now=NOW, baseline=False):
        return cs.collect(prev, now, http, baseline=baseline)

    def test_first_run_baseline_then_new_month_events_once(self):
        b1, ev1, c1 = self.run_cs(None, FakeHttp(9, 8))
        self.assertEqual(ev1, [])  # 첫 실행은 기준선
        self.assertEqual(c1["status"], "ok")
        self.assertEqual(b1["latest"], {"hmc:model": "2026-09", "hmc:plant": "2026-09", "kia:model": "2026-08", "kia:plant": "2026-08"})
        self.assertEqual(series(b1, "Avante (CN8)", "국내 판매")["months"]["2026-09"], 6945)
        self.assertNotIn("2026-10", series(b1, "Avante (CN8)", "국내 판매")["months"])
        self.assertEqual(series(b1, "Avante (CN7)", "국내 판매")["months"]["2025-09"], 3000)
        # 9월에는 새 신호가 없다: 아반떼 CN7(8월에 이미 줄어듦)·앨라배마 GV70(7월 급감, 8월부터 0)은 낮게 머무는 달마다 다시 띄우지 않는다
        self.assertEqual(b1["signals"], [])
        jul = {(x["label"], x["signal"], x["tier"]) for x in cs.signals(b1["series"], "hmc", "plant", "2026-07")}
        self.assertIn(("GV70 (JKa)", "급감", "B"), jul)
        self.assertEqual(cs.signals(b1["series"], "hmc", "plant", "2026-08"), [])
        # 같은 달 다시: 이벤트 없음, 지난해 파일은 304로 다시 받지 않음
        h = FakeHttp(9, 8)
        b2, ev2, _ = self.run_cs(b1, h)
        self.assertEqual(ev2, [])
        self.assertEqual(b2["unchangedFiles"], 6)
        # 10월 엑셀이 올라옴(새 주소): 그 달 신호만 이벤트로
        b3, ev3, _ = self.run_cs(b2, FakeHttp(10, 8), now=NOW + dt.timedelta(days=20))
        got = {(e["text"].split(" · ")[1].split(" 2026")[0], e["signal"], e["tier"]) for e in ev3}
        self.assertIn(("Santa-Fe (MX5a)", "판매 끊김", "A"), got)
        self.assertIn(("공장 합계", "공장 출고 멈춤", "A"), got)
        self.assertIn(("Sonata (DN8)", "급감", "B"), got)
        self.assertIn(("Casper EV (AX EV)", "급증", "B"), got)
        self.assertFalse(any(lab.startswith("Avante (CN7)") for lab, _, _ in got))  # 9월에 이미 끊긴 계열은 10월에 다시 안 뜸
        self.assertFalse(any(lab.startswith("GV70") for lab, _, _ in got))
        santa = next(e for e in ev3 if "Santa-Fe" in e["text"])
        self.assertEqual(santa["text"], "현대차 미국 앨라배마 공장 현지 판매 · Santa-Fe (MX5a) 2026-10 100대 — 직전 3개월 평균 7,526대, 전년 같은 달 7,000대. "
                                        "판매(출고)가 거의 끊김 — 단종·생산 중단·물량 조정 여부는 회사 확인 (IR 엑셀)")
        self.assertEqual((santa["kind"], santa["company"], santa["url"]), ("모델별 판매", "현대차", cs.HMC_PAGE))
        b4, ev4, _ = self.run_cs(b3, FakeHttp(10, 8), now=NOW + dt.timedelta(days=21))
        self.assertEqual(ev4, [])

    def test_kia_september_tasman_drop_and_seasonal_august(self):
        b1, _, _ = self.run_cs(None, FakeHttp(9, 8))
        b2, ev, _ = self.run_cs(b1, FakeHttp(9, 9), now=NOW + dt.timedelta(days=5))
        tas = [e for e in ev if "Tasman" in e["text"]]
        self.assertEqual([(e["signal"], e["tier"]) for e in tas], [("급감", "B")])
        self.assertIn("기아 국내 판매 · Tasman 2026-09 90대 — 직전 3개월 평균 390대의 23%, 전년 같은 달 값 없음", tas[0]["text"])
        # 8월 그랜저(GN7) 900대: 직전 평균의 34%지만 지난해 8월도 1,000대 → 급감 아님(계절)
        aug = cs.signals(b1["series"], "hmc", "model", "2026-08")
        self.assertFalse(any(x["label"] == "Grandeur (GN7)" for x in aug))
        # 같은 8월 아반떼 CN7 560대는 급감 조건이지만 CN8이 막 늘어 세대 교체로 보임
        cn7 = next(x for x in aug if x["label"] == "Avante (CN7)")
        self.assertEqual(cn7["signal"], "세대 교체로 보임")
        self.assertIn("같은 이름 Avante (CN8)이 607대로 늘어남", cn7["text"])

    def test_failures_keep_previous_values_and_are_unconfirmed(self):
        b1, _, _ = self.run_cs(None, FakeHttp(9, 8))
        b2, ev, c = self.run_cs(b1, FakeHttp(9, 9, kia_down=True))
        self.assertEqual(c["status"], "partial")
        self.assertIn("기아 목록: ReadTimeout", c["error"])
        self.assertEqual(b2["latest"]["kia:model"], "2026-08")  # 직전 값 유지
        self.assertEqual(series(b2, "Tasman", "국내 판매")["months"]["2026-08"], 378)
        self.assertEqual(ev, [])

    def test_kr_stats_run_carries_car_events(self):
        cfg = {"signals": {}, "ecos": [], "kosis": [], "census": [], "kaida": {"beats": {}}}

        class Both(FakeHttp):
            def call(self, method, url, **kw):
                if "kaida" in url:
                    return None, "HTTP 503"
                return super().call(method, url, **kw)
        d1 = w.run(cfg, now=NOW, previous={"series": []}, http=Both(9, 8))
        self.assertEqual(d1["carSales"]["latest"]["hmc:model"], "2026-09")
        d2 = w.run(cfg, now=NOW + dt.timedelta(days=20), previous=d1, http=Both(10, 8))
        car = [e for e in d2["events"] if e["kind"] == "모델별 판매"]
        self.assertTrue(car and all(e["tier"] in ("A", "B") for e in car))
        self.assertEqual(next(c for c in d2["checks"] if c["source"].startswith("완성차"))["status"], "ok")
        json.dumps(d2, ensure_ascii=False)  # 저장 가능한 모양


if __name__ == "__main__":
    unittest.main()
