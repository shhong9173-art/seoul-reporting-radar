"""미국 소비자 결함 신고(NHTSA 공개 파일 COMPLAINTS_RECEIVED_<YYYY-YYYY>.zip) — 출입처 차종의 신고 급증.

리콜·결함조사(ODI) 전 단계 신호다. 신고는 소비자가 낸 것이고 결함 확정이 아니다.
탐침(10-31): 2025-2026 파일 43MB·20만9천 줄·51칸(탭), 날마다 갱신(Last-Modified 10-30), 현대·기아·제네시스 2만5천여 줄.
신고 한 건(ODINO)이 부품 칸마다 한 줄씩(최대 3줄) 나온다 — 건수는 신고 번호로 센다.
최근 28일 신고를 그 앞 24주(28일당 평균)와 견줘 부품별로 튀는 차종을 고른다(10-31 탐침: 싼타페 하이브리드
연료·추진 10건/평균 2.3, 전기 11건/3.5, 동력전달 8건/2.7 — 나머지 차종은 문턱 밑).
"""
from __future__ import annotations

import collections
import datetime as dt
import io
import re
import zipfile

URL = "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_{span}.zip"
API = "https://api.nhtsa.gov/complaints/complaintsByVehicle?make={make}&model={model}&modelYear={year}"
WINDOW_DAYS = 28
BASE_DAYS = 168          # 기준: 최근 28일 앞 24주
MIN_RECENT = 8           # 부품별 최근 28일 신고가 이보다 적으면 보지 않음
RATIO = 2.5              # 기준(28일당 평균, 최소 1건) 대비 배수
FIRE_MIN = 3             # 같은 차종 화재 신고(FIRE=Y)가 28일에 이 이상이고 기준의 2배 이상이면 따로 본다(참고 C)
FIRE_B = 5               # 화재 신고만 몰린 차종은 이 이상·기준 3배 이상일 때만 B
FIRE_LABEL = "화재 신고(FIRE=Y)"
RECALL_DAYS = 60         # 같은 차종·같은 부품 리콜이 이 안에 있으면 리콜 뒤 신고일 수 있어 C
KEEP_DAYS = 45
# 칸 번호(0부터, COMPLAINTS_RECEIVED 51칸): 신고번호·제조사명·차명·연식·충돌·화재·부상·사망·부품·접수일·내용
ODINO, MAKE, MODEL, YEAR, CRASH, FIRE, INJURED, DEATHS, COMP, DATEA, TEXT = 1, 3, 4, 5, 6, 8, 9, 10, 11, 15, 19
BRANDS = {"HYUNDAI": ("현대차", "현대차"), "GENESIS": ("현대차", "제네시스"), "KIA": ("기아", "기아")}
GM_KOREA = re.compile(r"^(?:TRAX|TRAILBLAZER|ENVISTA|ENCORE GX)\b", re.I)


def brand_of(make, model):
    """(출입처, 기사에 쓰는 이름) 또는 None. 한국GM은 미국에 파는 한국 생산 차종만."""
    make = make.upper()
    if make in BRANDS:
        return BRANDS[make]
    if make in ("CHEVROLET", "BUICK") and GM_KOREA.match(model):
        return ("한국GM", "한국GM")
    return None


def comp_top(c):
    return (c.split(":")[0].strip().upper() or "UNKNOWN OR OTHER")[:60]


def comp_word(c):
    """리콜 부품 칸과 견줄 첫 낱말(FUEL/PROPULSION SYSTEM → FUEL, POWER TRAIN → POWER)."""
    return re.split(r"[\s/,:]+", comp_top(c))[0]


def spans(now):
    """기준 기간까지 덮는 파일 이름 후보(두 해씩 묶인 파일: 2025-2026)."""
    years = sorted({now.year, (now - dt.timedelta(days=WINDOW_DAYS + BASE_DAYS)).year})
    out = []
    for y in years:
        for s in (f"{y - 1}-{y}", f"{y}-{y + 1}"):
            if s not in out:
                out.append(s)
    return out


def read_rows(blobs):
    """zip 바이트들 → 출입처 차종 줄만(칸 리스트)."""
    rows, bad = [], 0
    for blob in blobs:
        z = zipfile.ZipFile(io.BytesIO(blob))
        with z.open(z.namelist()[0]) as f:
            for line in io.TextIOWrapper(f, encoding="latin-1", newline=""):
                cells = line.rstrip("\r\n").split("\t")
                if len(cells) <= TEXT:
                    bad += 1
                    continue
                if brand_of(cells[MAKE], cells[MODEL].strip()):
                    rows.append(cells)
    return rows, bad


def day(v):
    try:
        return dt.datetime.strptime(v, "%Y%m%d").date()
    except (TypeError, ValueError):
        return None


def aggregate(rows):
    """차종×부품별 최근·기준 신고 번호와 화재·충돌·부상, 연식, 원문 발췌."""
    end = max((d for d in (day(r[DATEA]) for r in rows) if d), default=None)
    if end is None:
        return None, {}
    recent_from = end - dt.timedelta(days=WINDOW_DAYS)
    base_from = recent_from - dt.timedelta(days=BASE_DAYS)
    agg = collections.defaultdict(lambda: {"recent": set(), "base": set(), "fire": set(), "crash": set(), "injured": set(), "deaths": set(),
                                           "yearOf": {}, "samples": {}})
    model_fire = collections.defaultdict(lambda: {"recent": set(), "base": set()})
    for r in rows:
        d = day(r[DATEA])
        if not d or d <= base_from:
            continue
        make, model = r[MAKE].upper(), r[MODEL].strip().upper()
        a = agg[(make, model, comp_top(r[COMP]))]
        odi = r[ODINO]
        fire = r[FIRE] == "Y"
        if d > recent_from:
            a["recent"].add(odi)
            a["yearOf"][odi] = r[YEAR]
            if fire:
                a["fire"].add(odi)
                model_fire[(make, model)]["recent"].add(odi)
            if r[CRASH] == "Y":
                a["crash"].add(odi)
            if (r[INJURED] or "0").strip() not in ("", "0"):
                a["injured"].add(odi)
            if (r[DEATHS] or "0").strip() not in ("", "0"):
                a["deaths"].add(odi)
            if odi not in a["samples"] and len(a["samples"]) < 3:
                a["samples"][odi] = {"odino": odi, "year": r[YEAR], "received": d.isoformat(), "text": short(r[TEXT])}
        else:
            a["base"].add(odi)
            if fire:
                model_fire[(make, model)]["base"].add(odi)
    return (recent_from, end), {"parts": agg, "fire": model_fire}


def short(text, n=220):
    t = re.sub(r"\s+", " ", (text or "").encode("latin-1", "ignore").decode("utf-8", "ignore")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"


def recent_recalls(recall_rows, now):
    """차종(제조사·차명)별 최근 RECALL_DAYS일 리콜: [(캠페인, 접수일, 부품 첫 낱말, 부품)]."""
    since = (now - dt.timedelta(days=RECALL_DAYS)).strftime("%Y%m%d")
    out = collections.defaultdict(dict)
    for x in recall_rows or []:
        if str(x.get("RCDATE") or "") < since:
            continue
        key = (str(x.get("MAKETXT") or "").upper(), str(x.get("MODELTXT") or "").upper())
        if brand_of(*key):
            camp = x.get("CAMPNO")
            out[key].setdefault(camp, {"campaign": camp, "received": f"{x['RCDATE'][:4]}-{x['RCDATE'][4:6]}-{x['RCDATE'][6:8]}",
                                       "component": str(x.get("COMPNAME") or "")[:100], "word": comp_word(str(x.get("COMPNAME") or ""))})
    return {k: sorted(v.values(), key=lambda r: r["received"], reverse=True) for k, v in out.items()}


def fire_only(parts):
    """화재 신고만으로 걸렸고 FIRE_B건·기준 3배에 못 미치면 True."""
    return all(c == FIRE_LABEL for c, *_ in parts) and not any(n >= FIRE_B and n >= 3 * max(b, 0.5) for _, n, b, _ in parts)


def spikes(window, agg, recalls):
    """부품별로 튄 것을 차종 하나로 묶는다(신고 한 건이 부품 여러 칸에 걸리므로 차종당 한 줄)."""
    by_model = collections.defaultdict(list)
    for (make, model, comp), a in agg["parts"].items():
        n, base = len(a["recent"]), len(a["base"]) / (BASE_DAYS / WINDOW_DAYS)
        if n >= MIN_RECENT and n >= RATIO * max(base, 1.0):
            by_model[(make, model)].append((comp, n, base, a))
    for (make, model), f in agg["fire"].items():
        n, base = len(f["recent"]), len(f["base"]) / (BASE_DAYS / WINDOW_DAYS)
        if n >= FIRE_MIN and n >= 2 * max(base, 0.5):
            parts = [(c, a) for (mk, md, c), a in agg["parts"].items() if (mk, md) == (make, model) and a["fire"]]
            merged = {"recent": f["recent"], "base": f["base"], "fire": f["recent"], "crash": set(), "injured": set(), "deaths": set(),
                      "yearOf": {k: v for _, a in parts for k, v in a["yearOf"].items() if k in f["recent"]},
                      "samples": {k: v for _, a in parts for k, v in a["samples"].items() if k in f["recent"]}}
            by_model[(make, model)].append((FIRE_LABEL, n, base, merged))
    out = []
    for (make, model), parts in by_model.items():
        beat, name = brand_of(make, model)
        parts.sort(key=lambda p: (-p[1], -p[1] / max(p[2], 1.0)))
        ids = set().union(*(p[3]["recent"] for p in parts))
        years = collections.Counter({**{k: v for p in parts for k, v in p[3]["yearOf"].items()}}.values())
        top_year = years.most_common(1)[0][0] if years else ""
        rec = recalls.get((make, model), [])
        words = {comp_word(p[0]) for p in parts}
        same = [r for r in rec if r["word"] in words]
        samples = []
        for p in parts:
            for s in p[3]["samples"].values():
                if s["odino"] not in {x["odino"] for x in samples} and len(samples) < 3:
                    samples.append(s)
        out.append({
            "id": f"cmpl:{make}:{model}", "make": make, "model": model, "beat": beat, "brand": name,
            "window": [window[0].isoformat(), window[1].isoformat()], "complaints": len(ids),
            "parts": [{"component": c, "recent": n, "baselinePer28": round(b, 1), "fire": len(a["fire"]), "crash": len(a["crash"]),
                       "injured": len(a["injured"]), "deaths": len(a["deaths"])} for c, n, b, a in parts],
            "fire": len(set().union(*(p[3]["fire"] for p in parts))), "crash": len(set().union(*(p[3]["crash"] for p in parts))),
            "injured": len(set().union(*(p[3]["injured"] for p in parts))), "deaths": len(set().union(*(p[3]["deaths"] for p in parts))),
            "years": "·".join(f"{y}({c})" for y, c in years.most_common(3)), "samples": samples,
            "recentRecalls": rec[:4], "sameComponentRecall": [r["campaign"] for r in same],
            # 같은 부품 리콜이 60일 안에 있으면 리콜 공지를 보고 낸 신고일 수 있어 참고(C). 신고는 결함 확정이 아니라 A로 올리지 않는다.
            # 화재 신고만 몰린 차종은 참고(C) — 10-31 첫 실행: 싼타페(2018·2019·2023년형)·포르테(2011·2017·2023년형, 한 건은
            # 타이어 파열 뒤 배선 마찰) 각 3건이 B로 떴다. 연식이 흩어진 화재 몇 건은 원인이 서로 다를 수 있다.
            "tier": "C" if same or fire_only(parts) else "B",
            "url": API.format(make=make, model=model.replace(" ", "%20"), year=top_year),
        })
    return sorted(out, key=lambda x: (x["tier"], -x["complaints"]))


def collect(now, previous, recall_rows, *, get):
    """(결과, 점검). 결과는 지난 결과를 이어받아 처음 본 날·신규를 매긴다."""
    stamp = now.isoformat(timespec="seconds")
    prev = {x["id"]: x for x in (previous or {}).get("spikes", []) if isinstance(x, dict) and x.get("id")}
    blobs, names, modified = [], [], None
    try:
        for s in spans(now):
            r = get(URL.format(span=s), headers={"User-Agent": "seoul-reporting-radar (github.com/shhong9173-art/seoul-reporting-radar)"}, timeout=240)
            if r.status_code == 404:
                continue
            if r.status_code != 200:
                raise RuntimeError(f"{s} HTTP {r.status_code}")
            blobs.append(r.content)
            names.append(s)
            modified = modified or getattr(r, "headers", {}).get("Last-Modified")
        if not blobs:
            raise RuntimeError("파일 없음(" + ", ".join(spans(now)) + ")")
        rows, bad = read_rows(blobs)
        window, agg = aggregate(rows)
        if window is None:
            raise RuntimeError("출입처 차종 신고 0줄")
    except Exception as e:  # noqa: BLE001
        keep = [dict(x, isNew=False) for x in prev.values()]
        return ({**(previous or {}), "spikes": keep, "stale": True},
                {"source": "NHTSA 소비자 결함 신고", "status": "failed", "error": str(e)[:80] or type(e).__name__})
    found = spikes(window, agg, recent_recalls(recall_rows, now))
    keep_from = (now - dt.timedelta(days=KEEP_DAYS)).isoformat()
    out = []
    for x in found:
        old = prev.get(x["id"]) or {}
        # 같은 차종이 계속 튀면 처음 본 날을 이어받는다(날마다 새 항목으로 뜨지 않게). 28일 넘게 쉬었다 다시 튀면 새로.
        cont = old.get("active", True) and str(old.get("lastSeen") or "") >= (now - dt.timedelta(days=WINDOW_DAYS)).isoformat()
        x["firstSeen"] = old.get("firstSeen") if old and cont else stamp
        x["lastSeen"], x["active"] = stamp, True
        x["isNew"] = previous is not None and "spikes" in previous and x["firstSeen"] == stamp
        out.append(x)
    ids = {x["id"] for x in out}
    out += [dict(x, active=False, isNew=False) for x in prev.values() if x["id"] not in ids and str(x.get("lastSeen") or "") >= keep_from]
    doc = {"checkedAt": stamp, "files": names, "fileModified": modified, "window": [window[0].isoformat(), window[1].isoformat()],
           "windowDays": WINDOW_DAYS, "baselineDays": BASE_DAYS, "rows": len(rows), "badRows": bad, "spikes": out, "rules": RULES}
    return doc, {"source": "NHTSA 소비자 결함 신고", "status": "ok", "rows": len(rows), "spikes": sum(1 for x in out if x["active"]),
                 "fileModified": modified}


RULES = ["소비자 결함 신고는 소비자가 NHTSA에 낸 것이고 결함 확정이 아니다. 최근 28일 신고를 그 앞 24주(28일당 평균)와 견줘 부품별로 "
         f"{MIN_RECENT}건 이상·{RATIO}배 이상 튄 차종만 본다(신고 한 건이 부품 여러 칸에 걸려 부품별 합은 신고 수보다 크다).",
         f"같은 차종·같은 부품 리콜이 {RECALL_DAYS}일 안에 있으면 리콜 공지를 보고 낸 신고일 수 있어 참고(C). 화재 신고만 몰린 차종은 "
         f"{FIRE_B}건·평소 3배 넘을 때만 B, 그 밖에는 참고(C) — 연식이 흩어진 화재 몇 건은 원인이 다를 수 있다.",
         "신고 원문 발췌는 소비자 서술이다. 사실 확인·국내 판매 차량 해당 여부는 회사·국토부(자동차리콜센터) 확인 대상이다."]
