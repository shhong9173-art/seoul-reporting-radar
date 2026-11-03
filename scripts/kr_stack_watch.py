"""출입처 공장 굴뚝 측정(가동 신호) 감시 — 한국환경공단 굴뚝 자동측정기기(TMS, CleanSYS) 실시간 측정결과, 기자 전용 저장소 'kr-stacks'.

- 출입처 사업장(data/stack_watch.json 이름 규칙)의 배출구별 최신 측정값(먼지·SOx·NOx 등 중 가장 큰 값)을 실행마다(3시간 간격)
  쌓는다. API는 지금 값만 주므로 이력은 이 감시가 쌓은 것이다.
- 배출구 멈춤 신호: 평소 값(직전 관측 중앙값)이 1 이상이던 배출구가 연달아 STOP_RUNS번 평소의 10% 아래(또는 0.3 아래)로 떨어지면
  '멈춤'. 사업장에서 평소 움직이던 배출구 절반 이상(2개 이상)이 멈추면 A(사업장 가동 중단 신호). 새로 멈춘 배출구가 평소 움직이던 것의
  5%(최소 2개) 이상이거나, 큰 배출구(평소 값 상위 3)이거나, 평소 값 합이 사업장 전체의 10% 이상이면 B(10-31: 포스코 광양 137개 중 2개가 B로 뜸).
- 새 배출구 번호·새 사업장: 실시간 값만 오는 자료라 쉬던 설비가 다시 측정되기 시작해도 '새 번호'로 보인다. 그 사업장을 14일 넘게
  지켜본 뒤 처음 보인 번호만 A(새 설비 또는 오래 쉬던 설비 재가동), 7~14일 B, 그 전은 C(간헐 가동·자료 지연일 수 있음).
  (10-31 운영: 영풍 석포 5·6번이 감시 하루 만에 A로 떴다.) 목록에서 빠진 배출구(두 번 연속) B. 멈췄던 사업장이 다시 움직이면 B.
- 평일 교대 공장(설정 schedule=weekday: 완성차·타이어·전선·변압기·중공업)은 주말·공휴일·밤(0~7시) 관측을 멈춤 판단과 평소 값에서 빼고,
  그 시간에는 목록에서 빠짐도 세지 않는다(10-31 토요일: 현대차 울산·기아 화성 '멈춤', 기아 광주2공장 '빠짐'이 B로 뜸 — 주말 휴무).
- 측정값 0 근처는 설비 정지·정비·측정기 점검·연료 전환일 수 있다. 어느 설비인지(배출구 이름)는 자료에 없다 — 회사 확인.
- 키는 공공데이터 공유 키(DATA_GO_KR_KEY). 키 값은 출력하지 않는다. 조회 실패는 0이 아니라 미확인.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_stacks/v1"
CONFIG = ROOT / "data" / "stack_watch.json"
HOLIDAYS_FILE = ROOT / "data" / "kr_holidays.json"
API = "https://apis.data.go.kr/B552584/cleansys/rltmMesureResult"
POLLUTANTS = ("tsp", "sox", "nox", "hcl", "hf", "nh3", "co")
OBS_KEEP = 32          # 3시간 간격이면 4일치(평일 교대 공장은 주말을 빼고도 평소 값을 정할 만큼)
MIN_OBS = 6            # 평소 값을 정할 최소 관측 수(첫 실행 뒤 하루쯤)
MATURE_RUNS = 6        # 새 배출구·새 사업장을 '새것'으로 볼 만큼 그 사업장(감시)을 지켜본 실행 수
NEW_A_DAYS = 14        # 새 배출구·새 사업장 A: 그 사업장(새 사업장은 감시)을 이만큼 지켜본 뒤 처음 보인 것
NEW_B_DAYS = 7         # 이만큼~NEW_A_DAYS면 B, 그 전은 C
BURST = 3              # 한 실행에 이만큼 이상 새로 보이면 새 설비가 아니라 목록 보강으로 본다(10-30 고려아연 온산 24개)
STOP_RUNS = 3          # 연달아 이만큼 낮으면 멈춤(3시간 간격이면 9시간)
STOP_B_SHARE = 0.05    # 배출구가 많은 사업장: 새로 멈춘 수가 평소 움직이던 배출구의 이 비율(최소 2개) 이상이어야 B
STOP_B_LOAD = 0.10     # 또는 새로 멈춘 배출구들의 평소 값 합이 사업장 전체 평소 값 합의 이 비율 이상
MEANINGFUL = 1.0       # 평소 값이 이보다 작으면 멈춤 판단을 하지 않는다(원래 거의 0인 배출구)
LOW_ABS = 0.3
LOW_REL = 0.10
MISSING_RUNS = 2
KEEP_EVENTS_DAYS = 60


# 공공데이터포털 게이트웨이 코드 중 일시 오류: 04 HTTP_ERROR, 05 SERVICE_TIMEOUT_ERROR. 키·권한·한도(20·22·30 등)는 다시 부르지 않는다.
TRANSIENT_GATEWAY = {"04", "05"}

class ApiError(RuntimeError):
    pass


def load_holidays(path=HOLIDAYS_FILE):
    try:
        return frozenset(json.loads(Path(path).read_text(encoding="utf-8")).get("dates") or [])
    except (OSError, ValueError):
        return frozenset()


HOLIDAYS = load_holidays()
WORK_FROM_HOUR = 7  # 평일 교대 공장: 이 시각 전(밤)은 쉬는 시간으로 본다


def working(t, holidays=None):
    """평일 교대 공장이 도는 시간인가: 월~금, 공휴일 아님, 7시 이후(KST)."""
    hol = HOLIDAYS if holidays is None else holidays
    t = t.astimezone(KST) if t.tzinfo else t.replace(tzinfo=KST)
    return t.weekday() < 5 and t.date().isoformat() not in hol and t.hour >= WORK_FROM_HOUR


def obs_time(mdt):
    try:
        return dt.datetime.strptime(str(mdt), "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except ValueError:
        return None


def working_hours_between(start, end, judge):
    """start~end 사이 judge가 참인 시간 수(시간 단위로 셈)."""
    hours, t = 0, start
    while t < end and hours < 24 * 14:
        if judge(t):
            hours += 1
        t += dt.timedelta(hours=1)
    return hours


def age_days(since, now):
    try:
        return (now - dt.datetime.fromisoformat(str(since))).total_seconds() / 86400
    except (TypeError, ValueError):
        return 0.0


def new_tier(days):
    return "A" if days >= NEW_A_DAYS else "B" if days >= NEW_B_DAYS else "C"


OFFHOUR_KINDS = ("배출구 멈춤 신호", "사업장 가동 중단 신호", "사업장 목록에서 빠짐(굴뚝 측정)", "배출구 목록에서 빠짐")


def retier_offhours(events, weekday_companies, judge=None):
    """평일 교대 공장의 멈춤·빠짐 이벤트가 쉬는 시간(주말·공휴일·밤)에 잡혔으면 C로 내린다(예전 규칙으로 토요일에 B가 된 것)."""
    judge = judge or working
    for e in events:
        if e.get("company") not in weekday_companies or e.get("kind") not in OFFHOUR_KINDS or e.get("tier") == "C":
            continue
        try:
            at = dt.datetime.fromisoformat(str(e.get("detectedAt")))
        except (TypeError, ValueError):
            continue
        if not judge(at):
            e["tier"] = "C"
            e["text"] = (e.get("text") or "") + " — 평일 교대 공장의 주말·휴일·밤에 잡힌 것이라 휴무일 수 있어 C로 바로잡음"


GONE_KINDS = ("사업장 목록에서 빠짐(굴뚝 측정)", "배출구 목록에서 빠짐")
REST_NOTE = (" — 주말·공휴일·밤(0~7시)에 빠진 것이라 쉬는 동안 측정 값이 없어 목록에 안 나온 것일 수 있음"
             "(평일 일하는 시간에도 2번 연속 빠지면 B로 다시 알림)")


def retier_rest_gone(events, judge=None):
    """목록에서 빠짐(사업장·배출구)이 쉬는 시간에 잡혔으면 회사와 상관없이 C로 내린다(평일 일하는 시간 확인 B는 그대로).
    11-01(일) 운영: 04:22 현대제철 포항1공장 배출구 3개, 09:13 동국제강 포항·KG스틸 당진·세아제강 창원 사업장이 '빠짐' B —
    포스코 포항 135번은 같은 날 다시 나타났다. 이 API는 값이 없는 배출구·사업장을 목록에 싣지 않는다."""
    judge = judge or working
    for e in events:
        if e.get("kind") not in GONE_KINDS or e.get("tier") == "C" or ":work" in str(e.get("id", "")):
            continue
        try:
            at = dt.datetime.fromisoformat(str(e.get("detectedAt")))
        except (TypeError, ValueError):
            continue
        if not judge(at):
            e["tier"] = "C"
            e["text"] = (e.get("text") or "") + REST_NOTE


def retier_new(events, sites, baseline_since):
    """저장된 '새 배출구'·'새 사업장' 이벤트를 지켜본 기간 규칙으로 다시 매긴다(예전 규칙으로 하루 만에 A가 된 것 바로잡기)."""
    for e in events:
        kind, at = e.get("kind"), e.get("detectedAt")
        if kind == "새 배출구":
            sid = ":".join(str(e.get("id", "")).split(":")[2:-1])
            since = (sites.get(sid) or {}).get("firstSeen") or baseline_since
        elif kind == "새 사업장(굴뚝 측정)":
            since = baseline_since
        else:
            continue
        try:
            days = age_days(since, dt.datetime.fromisoformat(str(at)))
        except (TypeError, ValueError):
            continue
        tier = new_tier(days)
        if tier != e.get("tier") and {"A": 0, "B": 1, "C": 2}.get(tier, 2) > {"A": 0, "B": 1, "C": 2}.get(e.get("tier"), 2):
            e["tier"] = tier
            e["text"] = (e.get("text") or "") + f" — 이 사업장을 {days:.1f}일만 지켜본 때라 간헐 가동·측정 자료 지연일 수 있어 {tier}로 바로잡음"


EXCEED_TEXT = re.compile(r"측정값 ([\d.]+)이 배출허용기준 ([\d.]+)을 넘음")


# 상태 글자 전환·해제는 아직 관찰 중 — C. 11-03 11:45 첫 읽기에서 17개 사업장이 한꺼번에 '전환' B로 떴다. 같은 배출구 글자가
# 몇 시간 안에 바뀌었다(S-OIL 온산 8개: 09:20 숫자 → 10:50 탐침 '기기점검' → 11:45 '보수중'; 포스코 광양 '기기점검' 6→13개).
# 최근 측정값에 붙는 잠정 표시일 수 있어, 여러 실행 동안 유지되는지 확인하기 전에는 B로 올리지 않는다.
STATUS_TRANSITION_TIER = "C"
STATUS_OBSERVE_NOTE = (" — 상태 글자는 11-03부터 읽기 시작해 검증 전(같은 배출구 글자가 몇 시간 안에 '기기점검'↔'보수중'으로 바뀐 사례) — "
                       "다음 실행들에도 유지되는지 보고 판단(C)")
STATUS_KINDS = ("배출구 보수·가동중지 전환", "배출구 보수·가동중지 해제")


MAINT_NOTE = " — '보수중'은 측정기 보수 상태로 바로잡음(11-03): 그 배출구는 멈춤 근거가 아닐 수 있음"
STOP_KINDS_ALL = ("배출구 멈춤 신호", "사업장 가동 중단 신호", "배출구 오래 멈춤")


SIZE_RULE_FROM = "2026-10-31T09:30"   # #422(사업장 크기에 맞춘 멈춤 B 문턱) 병합 시각
SIZE_NOTE_RX = re.compile(r" — 평소 움직이던 \d+개 중 \d+개라 일상 정비 수준일 수 있어 C로 바로잡음\(사업장 크기 기준: 5%·상위 3·평소 값 10%\)")


def restore_size_retier(events):
    """사업장 크기 규칙 뒤에 생긴 멈춤 B를 다시 보다가 C로 내린 것(11-03 13:47 실행)을 되돌린다: 설명을 지우고 B로."""
    n = 0
    for e in events:
        text = e.get("text") or ""
        if e.get("kind") == "배출구 멈춤 신호" and str(e.get("detectedAt") or "") >= SIZE_RULE_FROM and SIZE_NOTE_RX.search(text):
            e["text"], e["tier"] = SIZE_NOTE_RX.sub("", text), "B"
            n += 1
    return n


LATE_START_NOTE = " — 멈춤 시작(끝에서부터 연달아 낮은 첫 측정): "
LATE_START_TAIL = " — 상태 글자를 11-03부터 읽어 이때 처음 멈춤으로 잡혔지만 그 전부터 멈춰 있었음"
LATE_START_HOURS = 12   # 3번 연속(6~9시간)·자료 지연(1.5시간)보다 넉넉히


def annotate_late_starts(events, sites, now, hours=48):
    """상태 글자를 읽기 시작한 뒤 처음 멈춤으로 잡힌 저장 알림(멈춤 시작을 안 적던 때)에 실제 멈춤 시작을 한 번 덧붙인다.
    11-03 11:45 현대제철 순천 81~83번 A — 알림은 오늘이지만 숫자는 10-31 13:30·20:30부터 끊겨 있었다.
    멈춤은 3번 연속 낮아야 알리므로 시작은 원래 알림보다 6~9시간 이르다 — LATE_START_HOURS 넘게 이른 것만, 끝 설명은 그 배출구가
    지금 '가동중지'일 때만 상태 글자 이야기를 쓴다."""
    cut = (now - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    for e in events:
        text, eid = e.get("text") or "", str(e.get("id") or "")
        if e.get("kind") not in ("배출구 멈춤 신호", "사업장 가동 중단 신호") or LATE_START_NOTE in text or str(e.get("detectedAt") or "") < cut:
            continue
        m = re.match(r"stk:(?:stop|down):(.+):\d{4}-\d{2}-\d{2}$", eid)
        site = sites.get(m.group(1)) if m else None
        seen = obs_time(str(e.get("detectedAt") or "")[:16].replace("T", " "))
        if not site or seen is None:
            continue
        early, halted, lead = [], True, 0.0
        for code in re.findall(r"(\S+?)번\(평소", text):
            st = site.get("stacks", {}).get(code) or {}
            since = st.get("stoppedSince")
            t = obs_time(since) if since else None
            if t is not None and (seen - t).total_seconds() > LATE_START_HOURS * 3600 and f"멈춤 {str(since)[5:16]}부터" not in text:
                early.append(f"{code}번 {str(since)[5:16]}")
                halted = halted and (st.get("status") or [None])[0] in STOP_STATUS
                lead = max(lead, (seen - t).total_seconds() / 3600)
        if early:
            e["text"] = text + LATE_START_NOTE + ", ".join(early) + (LATE_START_TAIL if halted else f" — 알림보다 최대 {lead:.0f}시간 앞서 멈춰 있었음")


# 사업장 메모(설정 siteNotes): 굴뚝 자료에는 업종이 없다 — 발전 사업장처럼 멈춤의 뜻이 다른 곳은 다른 공식 자료로 확인한 범위만 적어 둔다
# (11-03: SK이노베이션 전남 사업장 배출구 4개 '가동중지' — 공장등록에 같은 회사 광양시 금호동 '화력 발전업'이 있다. 같은 곳인지는 미확인).
NOTE_KINDS = ("배출구 멈춤 신호", "사업장 가동 중단 신호", "배출구 오래 멈춤", "배출구 가동중지 전환", "배출구 가동중지 해제", "사업장 재가동 신호",
              "배출구 목록에서 빠짐", "사업장 목록에서 빠짐(굴뚝 측정)", "배출구 오래 빠짐", "사업장 오래 빠짐(굴뚝 측정)")


def site_note(comp, name, area):
    """설정 siteNotes 가운데 이 사업장(이름 정규식·시도)에 맞는 메모. 없으면 None."""
    for n in comp.get("siteNotes") or []:
        if re.search(n["site"], name or "") and (not n.get("area") or n["area"] == area):
            return n["note"]
    return None


def retier_maintenance_stops(events):
    """#599~#614 동안 '보수중'을 멈춤으로 센 저장 이벤트: 든 배출구가 모두 '보수중'이면 C, 섞였으면 설명만(한 번)."""
    for e in events:
        text = e.get("text") or ""
        if e.get("kind") not in STOP_KINDS_ALL or "상태 '보수중'" not in text or MAINT_NOTE in text:
            continue
        parts = re.findall(r"\S+?번\(평소[^)]*(?:\([^)]*\)[^)]*)*\)", text)
        if parts and all("상태 '보수중'" in x for x in parts):
            e["tier"] = "C"
        e["text"] = text + MAINT_NOTE


# '가동중지' 전환·해제(11-03 저녁부터): 사업장이 보낸 시설 멈춤 신고라 글자가 오래 간다 — 11-03 확인에서 10:30에 '가동중지'로 바뀐
# 17개 중 16개가 12:30에, 17개 모두가 13:00에 그대로였다(측정기 쪽 '보수중'은 42개 중 11~13개가 숫자로 돌아왔다 다시 바뀌기도 했다). 멈춤 신호(3번 연속, 6~9시간 뒤)보다
# 먼저 알 수 있어, 멈춤 B와 같은 사업장 크기 기준(5%·최소 2개, 큰 배출구, 평소 값 합 10%)이면 B. 예전 '보수·가동중지' 이름 이벤트는 그대로 C.
HALT_KINDS = ("배출구 가동중지 전환", "배출구 가동중지 해제")
HALT_NOTE = (" — '가동중지'는 사업장이 보낸 시설 멈춤 신고(11-03 확인: 10:30에 바뀐 17개가 13:00에도 모두 그대로, 측정기 쪽 '보수중'은 42개 중 11~13개가 숫자로 돌아왔다 다시 바뀌기도 함)")
HALT_SMALL_NOTE = " — 사업장 크기 기준(5%·최소 2개, 큰 배출구, 평소 값 합 10%)에 못 미쳐 C"


def size_rule(codes, judged, top_base):
    """멈춤 B와 같은 사업장 크기 기준: 평소 값이 있는 배출구 수의 5%(최소 2개) 이상, 큰 배출구(상위 3), 또는 2개 이상이 평소 값 합의 10% 이상."""
    based = {c: b for c, (_, b) in judged.items() if b is not None and b >= MEANINGFUL}
    load = sum(based.values()) or 1
    return (len(codes) >= max(2, math.ceil(len(based) * STOP_B_SHARE)) or any(c in top_base for c in codes)
            or (len(codes) >= 2 and sum(based.get(c) or 0 for c in codes) >= STOP_B_LOAD * load))


def announced_halts(events, sid, now, hours=24):
    """이 사업장에서 최근 hours시간 안에 B로 알린 '가동중지 전환'의 배출구 → 알린 시각."""
    cut = (now - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    told = {}
    for e in events:
        if e.get("kind") == HALT_KINDS[0] and e.get("tier") == "B" and str(e.get("id", "")).startswith(f"stk:halt:{sid}:") \
                and str(e.get("detectedAt") or "") >= cut:
            for c in re.findall(r"(\S+?)번\(직전 값", e.get("text") or ""):
                told.setdefault(c, str(e.get("detectedAt")))
    return told


def retier_status_transitions(events):
    """예전 규칙으로 B가 된 상태 글자 전환·해제를 C로(한 번만 설명을 붙인다)."""
    for e in events:
        if e.get("kind") in STATUS_KINDS and e.get("tier") != STATUS_TRANSITION_TIER:
            e["tier"] = STATUS_TRANSITION_TIER
            if "검증 전" not in (e.get("text") or ""):
                e["text"] = (e.get("text") or "") + STATUS_OBSERVE_NOTE


def retier_marginal(events):
    """저장된 배출허용기준 초과 이벤트 중 기준을 5% 안쪽으로 넘은 것을 한 단계 내린다(예전 규칙으로 B·A가 된 것 바로잡기)."""
    lower = {"배출허용기준 초과(측정값)": ("B", "C"), "배출허용기준 초과 지속": ("A", "B")}
    for e in events:
        pair = lower.get(e.get("kind"))
        if not pair or e.get("tier") != pair[0] or "한 단계 낮춤" in str(e.get("text")):
            continue
        vals = [(float(a), float(b)) for a, b in EXCEED_TEXT.findall(str(e.get("text") or "")) if float(b) > 0]
        first = re.search(r"\(처음 ([\d.]+)\)", str(e.get("text") or ""))
        ratios = [a / b for a, b in vals] + ([float(first.group(1)) / vals[0][1]] if first and vals else [])
        if ratios and max(ratios) < MARGINAL:
            e["tier"] = pair[1]
            e["text"] = (e.get("text") or "") + f" — 기준을 {MARGINAL - 1:.0%} 안쪽으로 넘은 값이라 {pair[1]}로 바로잡음"


# 11-01 오후 운영: 검색어 30개로 늘린 병합 직후 첫 실행이 API 응답 없이 10분 작업 한도에 걸려 아무것도 저장하지 못했다(15분 뒤 다시 돌리니 36초).
# 검색 한 번은 연결 10초·응답 45초까지, 실행 전체는 RUN_BUDGET초까지만 새 검색을 시작한다 — 남은 검색어는 실패(일부)로 두고 읽은 것은 저장한다.
FETCH_TIMEOUT = (10, 45)
RUN_BUDGET = 360


def fetch(term, key, *, get=None, sleep=time.sleep):
    """사업장명 포함 검색 한 번(이 API는 한 번에 전체를 준다). 실패는 한 번 더."""
    if get is None:
        import requests
        get = requests.get
    err = None
    for attempt in (0, 1):
        if attempt:
            sleep(3.0)
        try:
            r = get(API, params={"serviceKey": key, "type": "json", "numOfRows": 1000, "pageNo": 1, "factManageNm": term}, timeout=FETCH_TIMEOUT)
        except Exception as e:  # noqa: BLE001 — class name only
            err = type(e).__name__
            continue
        code = re.search(r'"returnReasonCode"\s*:\s*"?(\d+)', r.text or "")
        if code and code.group(1) in TRANSIENT_GATEWAY:  # 게이트웨이 시간 초과·연결 오류: 한 번 더
            err = f"코드 {code.group(1)}"
            continue
        if code:
            raise ApiError(f"코드 {code.group(1)}")
        if r.status_code != 200:
            err = f"HTTP {r.status_code}"
            continue
        try:
            d = json.loads(r.text)
        except ValueError:
            err = "비JSON 응답"
            continue
        res = d.get("response") or {}
        rc = str((res.get("header") or {}).get("resultCode") or "")
        if rc not in ("", "0", "00"):
            raise ApiError(f"결과 코드 {rc}")
        items = (res.get("body") or {}).get("items") or []
        items = items.get("item") if isinstance(items, dict) else items
        return items if isinstance(items, list) else ([items] if items else [])
    raise ApiError(err or "응답 없음")


def peak(x):
    """배출구 한 줄의 측정값 중 가장 큰 값(없으면 None)."""
    vals = []
    for p in POLLUTANTS:
        v = x.get(f"{p}_mesure_value")
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    return max(vals) if vals else None


# 측정값 칸에 숫자 대신 오는 상태 글자(11-03 탐침 113: 출입처 932줄 중 176줄).
# '측정자료확인중(가동중지)'만 배출시설이 멈췄다는 신고로 본다. '보수중'·'기기점검'·'미수신'·'측정자료확인중'은 측정기 쪽 상태다 —
# 굴뚝 원격감시 특허(KR100896018B1)는 측정기 상태를 '정상·교정중·동작불량·전원단절·보수중'으로 적고, 11-03 운영에서 S-OIL 온산
# 8개가 09:20 숫자 → '기기점검' → 10:30 측정 '보수중'으로 바뀌었다(측정기 점검·보수 흐름). 처음(#599)엔 '보수중'도 멈춤으로 셌다.
# 예전에는 숫자만 읽어, 가동중지라고 적힌 배출구(포스코 광양 135번 등)가 값 없음(판단 안 함)으로 남았다.
STOP_STATUS = ("가동중지",)
SHOWN_STATUS = ("가동중지", "보수중")   # 설명에 수를 함께 적는 글자
NUM_RX = re.compile(r"^-?\d+(?:\.\d+)?$")


def status_of(x):
    """측정값 칸의 상태 글자 → '가동중지'·'보수중'·'기기점검'·'미수신'·'측정자료확인중' (숫자만 있으면 None)."""
    texts = [str(x.get(f"{p}_mesure_value")).strip() for p in POLLUTANTS
             if x.get(f"{p}_mesure_value") not in (None, "") and not NUM_RX.match(str(x.get(f"{p}_mesure_value")).strip())]
    if not texts:
        return None
    for key in ("가동중지", "보수", "점검", "미수신", "확인중"):
        if any(key in t for t in texts):
            return {"보수": "보수중", "점검": "기기점검", "확인중": "측정자료확인중"}.get(key, key)
    return texts[0][:20]


def reading(x):
    """관측으로 쌓을 값: 숫자 최댓값. 숫자가 없고 '가동중지'면 0(시설이 멈췄다고 사업장이 보냄), 측정기 쪽 상태면 None."""
    v = peak(x)
    if v is None and status_of(x) in STOP_STATUS:
        return 0.0
    return v


def status_note(st):
    """상태 글자와 이 감시가 그 글자를 처음 본 측정 시각(그 전부터였을 수 있다)."""
    stt = st.get("status")
    return f", 상태 '{stt[0]}'(처음 본 측정 {str(stt[1])[5:]})" if stt else ""


def backfill_status_gap(st, stt):
    """'가동중지' 줄이 왔을 때, 바로 앞의 값 없는 관측(예전엔 상태 글자를 못 읽어 None으로 쌓임)을 0으로 바꾼다 —
    멈춤 시작·평소 값이 상태 글자를 읽기 시작한 날(11-03)이 아니라 실제로 숫자가 끊긴 때를 가리키게. 바꾼 수를 돌려준다."""
    if stt not in STOP_STATUS:
        return 0
    n = 0
    for o in reversed(st.get("obs") or []):
        if o[1] is not None:
            break
        o[1] = 0.0
        n += 1
    return n


POL_KO = {"tsp": "먼지", "sox": "황산화물", "nox": "질소산화물", "hcl": "염화수소", "hf": "불화수소", "nh3": "암모니아", "co": "일산화탄소"}
EXCEED_KEEP = 20


def fnum(v):
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


MARGINAL = 1.05  # 측정값/기준이 이 아래면 '조금 넘은 값'


RESTART_NOTE = " — 직전까지 '가동중지'·멈춤이던 배출구가 다시 값을 보내며 넘은 것이라 가동 개시 직후 값일 수 있음(처음 넘은 값은 한 단계 낮춤)"


EXCEED_ID = re.compile(r"^stk:exceed:(.+):([^:]+):(tsp|sox|nox|hcl|hf|nh3|co):(\d{4}-\d{2}-\d{2} \d{2}:\d{2})$")


def retier_restart_exceed(events, sites, now, hours=48):
    """재가동 직후 처음 넘은 값을 B로 저장한 것(규칙 전)을 C로: 그 측정 바로 앞 관측이 0 근처('가동중지'는 0으로 쌓임)면."""
    cut = (now - dt.timedelta(hours=hours)).isoformat(timespec="seconds")
    for e in events:
        if e.get("kind") != "배출허용기준 초과(측정값)" or e.get("tier") != "B" or "가동 개시 직후 값일 수 있음" in str(e.get("text") or "") \
                or str(e.get("detectedAt") or "") < cut:
            continue
        m = EXCEED_ID.match(str(e.get("id") or ""))
        st = ((sites.get(m.group(1)) or {}).get("stacks") or {}).get(m.group(2)) if m else None
        obs = (st or {}).get("obs") or []
        i = next((k for k, o in enumerate(obs) if o[0] == m.group(4)), None) if m else None
        if i and obs[i - 1][1] is not None and obs[i - 1][1] <= LOW_ABS:
            e["tier"] = "C"
            e["text"] = str(e.get("text") or "") + RESTART_NOTE.replace("(처음 넘은 값은 한 단계 낮춤)", "(처음 넘은 값이라 C로 바로잡음)")


def exceedances(x):
    """측정값이 그 배출구의 배출허용기준(같은 줄의 *_exhst_perm_stdr_value)을 넘은 오염물질: [(물질, 측정값, 기준)]."""
    out = []
    for p in POLLUTANTS:
        m, s = fnum(x.get(f"{p}_mesure_value")), fnum(x.get(f"{p}_exhst_perm_stdr_value"))
        if m is not None and s is not None and s > 0 and m > s:
            out.append((p, m, s))
    return out


GONE_BURST_NOTE = (" — 같은 실행에 이 사업장 배출구 {n}개가 한꺼번에 빠져 측정 자료 지연일 수 있어 C로 바로잡음"
                   "(이 API는 멈춘 배출구도 '가동중지' 상태 글자로 싣는다. 11-03 09:20 고려아연 온산 15개가 같은 날 오전 값과 함께 다시 나옴)")


def collapse_gone_bursts(events):
    """배출구 '목록에서 빠짐'이 같은 사업장·같은 실행에 BURST개 이상이면 모두 C로(목록이 한꺼번에 줄어든 것 — 자료 지연)."""
    groups = {}
    for e in events:
        if e.get("kind") == "배출구 목록에서 빠짐":
            groups.setdefault((e.get("company"), e.get("site"), e.get("detectedAt")), []).append(e)
    for es in groups.values():
        if len(es) < BURST:
            continue
        for e in es:
            if "한꺼번에 빠져" not in (e.get("text") or ""):
                e["text"] = (e.get("text") or "") + GONE_BURST_NOTE.format(n=len(es))
            e["tier"] = "C"


def collapse_long_gone(events):
    """같은 사업장·같은 실행에 '배출구 오래 빠짐'이 BURST개 이상이면 첫 줄만 B, 나머지는 C(같은 설비 묶음일 수 있음)."""
    groups = {}
    for e in events:
        if e.get("kind") == "배출구 오래 빠짐":
            groups.setdefault((e.get("company"), e.get("site"), e.get("detectedAt")), []).append(e)
    for es in groups.values():
        if len(es) < BURST:
            continue
        for e in sorted(es, key=lambda e: e.get("id") or "")[1:]:
            if "함께 사흘 넘게 빠짐" not in (e.get("text") or ""):
                e["text"] = (e.get("text") or "") + f" — 같은 실행에 이 사업장 배출구 {len(es)}개가 함께 사흘 넘게 빠짐(한 줄만 B)"
            e["tier"] = "C"


def collapse_bursts(events):
    """저장된 '새 배출구' 이벤트 가운데 같은 사업장·같은 실행에 BURST개 이상이면 C '배출구 목록 보강' 한 줄로 바꾼다
    (10-30 13:36: 고려아연 온산제련소 배출구 24개가 한꺼번에 A로 뜸 — 첫 실행 기준선 때 일부 배출구 값이 아직 없었던 것)."""
    groups = {}
    for e in events:
        if e.get("kind") == "새 배출구":
            groups.setdefault((e.get("company"), e.get("site"), e.get("detectedAt")), []).append(e)
    drop, add = set(), []
    for (company, site, at), es in groups.items():
        if len(es) < BURST:
            continue
        drop |= {e["id"] for e in es}
        codes = sorted((re.search(r"새 배출구 (\S+)번", e.get("text") or "") or [None, "?"])[1] for e in es)
        add.append({"id": f"stk:burst:{company}:{site}:{at}", "kind": "배출구 목록 보강", "tier": "C", "company": company, "site": site, "detectedAt": at,
                    "text": f"{site} 굴뚝 자동측정 목록에 배출구 {len(es)}개가 한꺼번에 새로 보임({', '.join(codes[:12])}{' 외' if len(codes) > 12 else ''}) — "
                            "측정 자료가 늦게 들어온 것일 수 있어 새 설비로 보지 않음(처음엔 A로 띄웠다가 바로잡음)"})
    return [e for e in events if e["id"] not in drop] + add


def norm(name):
    return re.sub(r"\s+", "", str(name or "").replace("（", "(").replace("）", ")").replace("㈜", "(주)"))


def judged_obs(obs, judge):
    """평일 교대 공장은 일하는 시간에 잰 관측만(판단 창·평소 값 모두)."""
    if judge is None:
        return obs
    return [o for o in obs if (lambda t: t is not None and judge(t))(obs_time(o[0]))]


def baseline(obs):
    """멈춤 판단 창(마지막 STOP_RUNS개) 앞의 관측 중앙값. 관측이 모자라면 None."""
    prior = [v for _, v in obs[:-STOP_RUNS] if v is not None]
    return statistics.median(prior) if len(prior) >= MIN_OBS else None


def is_low(v, base):
    return v is not None and v < max(LOW_ABS, base * LOW_REL)


STALE_HOURS = 12
# 오래 멈춘 배출구: 일상 정비는 보통 하루 안이다. 사흘(평일 교대 공장은 일하는 시간 72시간) 넘게 평소의 10% 아래면
# 사업장 크기와 상관없이 B — 11-02 경향 [단독] '포스코, 광양 2고로 전면 개수'(10-30): 광양 129·135번이 10-31부터 멈췄지만
# 137개 중 2개라 '일상 정비 수준' C로만 남았다(어느 설비인지는 자료에 없음).
LONG_STOP_HOURS = 72


# 오래 빠진 배출구·사업장: 멈춘 배출구는 목록에 '가동중지'로 남는다 — 사흘(평일 교대 공장은 일하는 시간 72시간) 넘게 목록에 없으면
# 측정 대상에서 빠진 것(설비 폐쇄·철거·측정 대상 제외)일 가능성이 2번 빠짐보다 훨씬 크다. 한 번만 B로 알린다
# (11-03 롯데케미칼 울산1공장 3·4·129번, 금호석유화학 울산고무공장 — 이틀 안팎 빠짐은 자료 지연과 가르기 어렵다).
LONG_GONE_HOURS = 72


def pre_stop_base(obs):
    """끝의 낮은 관측(STOP_RUNS개 이상)이 시작되기 전 관측의 중앙값 — 멈추기 전 평소 값. 그런 꼴이 아니면 None.
    평소 값을 붙들어 두기 전(11-02 전)에 멈춘 배출구를 되살린다: 포스코 광양 129·135번(10-31부터)이 11-02 11시 목록에서 빠졌다."""
    vals = [v for _, v in obs]
    for k in range(MIN_OBS, len(vals) - STOP_RUNS + 1):
        pre = [v for v in vals[:k] if v is not None]
        if len(pre) < MIN_OBS:
            continue
        b = statistics.median(pre)
        if b >= MEANINGFUL and not is_low(vals[k - 1], b) and all(is_low(v, b) for v in vals[k:]):
            return b
    return None


def stopped_since(st, base, judge=None):
    """끝에서부터 연달아 낮은 관측의 첫 측정 시각(멈춤 판단 창 관측만). 없으면 None."""
    obs = judged_obs(st.get("obs") or [], judge)
    first = None
    for mdt, v in reversed(obs):
        if not is_low(v, base):
            break
        first = mdt
    return obs_time(first) if first else None


# 배출구 멈춤 기록: 멈췄다 다시 움직이면 시작·끝을 남긴다. 같은 배출구가 자주 짧게 멈췄다면 일상 정비·간헐 가동일 수 있어
# 멈춤 알림에 앞선 멈춤을 함께 적는다(11-03: 현대제철 순천 81~83번처럼 처음 보는 멈춤인지 되풀이인지 화면에서 알 수 없었다).
# 관측은 4일치만 쌓여 그 전 멈춤은 이 기록으로만 안다 — 기록은 11-03부터라 그 전 멈춤은 없다고 단정하지 않는다.
STOP_LOG_KEEP = 8
STOP_LOG_DAYS = 90


def log_stop_end(st, end, now):
    """멈춤이 끝난 배출구(running으로 돌아옴): [시작, 끝]을 stopLog에 더한다(최근 STOP_LOG_KEEP번·STOP_LOG_DAYS일). 시작이 없으면 그대로."""
    start = st.get("stoppedSince")
    if not start:
        return False
    cut = f"{now - dt.timedelta(days=STOP_LOG_DAYS):%Y-%m-%d %H:%M}"
    log = [e for e in st.get("stopLog") or [] if isinstance(e, list) and len(e) == 2 and str(e[1]) >= cut]
    if not log or log[-1][0] != start:
        log.append([start, str(end or "")[:16]])
    st["stopLog"] = log[-STOP_LOG_KEEP:]
    return True


def stop_history(st, now, days=30):
    """멈춤 알림에 붙일 앞선 멈춤 문구 — 최근 days일 안에 끝난 멈춤만. 없으면 ''(기록 시작 전은 모름)."""
    cut = f"{now - dt.timedelta(days=days):%Y-%m-%d %H:%M}"
    log = [e for e in st.get("stopLog") or [] if isinstance(e, list) and len(e) == 2 and str(e[1]) >= cut]
    if not log:
        return ""
    def span(e):
        a, b = obs_time(e[0]), obs_time(e[1])
        hours = f" {((b - a).total_seconds() / 3600):.0f}시간" if a and b and b >= a else ""
        end = str(e[1])[11:16] if str(e[1])[:10] == str(e[0])[:10] else str(e[1])[5:16]
        return f"{str(e[0])[5:16]}~{end}{hours}"
    shown = " · ".join(span(e) for e in log[-3:])
    return f", 최근 {days}일 앞선 멈춤 {len(log)}번({shown}{' 등' if len(log) > 3 else ''})"


def stack_state(st, now=None, judge=None):
    """'stopped' | 'running' | 'unknown'(관측 부족·원래 거의 0). 측정 시각이 STALE_HOURS 넘게 그대로면(값이 안 들어옴) 멈춤으로 본다.
    judge가 있으면(평일 교대 공장) 일하는 시간 관측만 보고, 측정 시각 멈춤도 일하는 시간으로 센다."""
    obs = judged_obs(st.get("obs") or [], judge)
    prior = baseline(obs)
    # 멈춤이 이어지는 동안은 멈추기 전 평소 값으로 본다 — 관측이 4일치만 쌓여, 이틀쯤 지나면 낮은 값이 중앙값을 끌어내려
    # '원래 거의 0'(판단 안 함)으로 바뀌고 멈춤 목록에서 조용히 빠졌다.
    usual = st.get("usual") if st.get("stoppedSince") else pre_stop_base(obs)
    if usual is not None and (prior is None or prior < usual):
        prior = usual
    vals = [v for _, v in obs if v is not None]
    base = prior if prior is not None else (statistics.median(vals) if len(vals) >= MIN_OBS else None)
    if base is None or base < MEANINGFUL:
        return "unknown", base
    if now is not None and st.get("lastDt"):
        last_t = obs_time(st["lastDt"])
        if last_t is not None:
            age = working_hours_between(last_t, now, judge) if judge else (now - last_t).total_seconds() / 3600
            if age > STALE_HOURS:
                return "stopped", base
    last = [v for _, v in obs[-STOP_RUNS:]]
    if prior is not None and len(last) == STOP_RUNS and all(is_low(v, base) for v in last):
        return "stopped", base
    if last and last[-1] is not None and not is_low(last[-1], base):
        return "running", base
    return "unknown", base


def run(cfg, *, now, previous=None, key, get=None, sleep=time.sleep, clock=time.monotonic):
    started = clock()
    stamp = now.isoformat(timespec="seconds")
    prev = previous if isinstance(previous, dict) else {}
    first = not prev.get("sites")
    # 새로 넣은 출입처(11-01 석유화학·정유 6곳)는 그 회사의 첫 실행을 기준선으로 — 사업장·배출구가 모두 '새것'으로 뜨지 않게
    known_companies = {s.get("company") for s in (prev.get("sites") or []) if isinstance(s, dict)}
    sites = {s["id"]: s for s in prev.get("sites") or [] if isinstance(s, dict) and s.get("id")}
    keep_from = (now - dt.timedelta(days=KEEP_EVENTS_DAYS)).isoformat()
    events = collapse_bursts([e for e in prev.get("events") or [] if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from])
    retier_new(events, sites, prev.get("baselineSince"))
    weekday_companies = {c["company"] for c in cfg["companies"] if c.get("schedule") == "weekday"}
    restore_size_retier(events)
    retier_offhours(events, weekday_companies)
    retier_rest_gone(events)
    retier_marginal(events)
    retier_restart_exceed(events, sites, now)
    retier_status_transitions(events)
    retier_maintenance_stops(events)
    known = {e["id"] for e in events}
    fresh, errors, ok_terms, seen_sites = [], [], 0, set()
    day = now.date().isoformat()

    def settle(prefix, note, marker="다시 나타남"):
        """목록에서 빠졌다던 것이 다시 나타나면 그 이벤트를 C로 내리고 '다시 나타남'을 붙인다(일시적 누락).
        이미 C인 것(주말·밤에 빠진 것)에도 붙인다 — 11-02 동국제강 포항·KG스틸 당진·세아제강 창원이 다시 측정됐는지 화면에서 안 보였다."""
        for e in fresh + events:
            eid = str(e.get("id", ""))
            if eid == prefix or eid.startswith(prefix + ":"):
                if marker not in (e.get("text") or ""):
                    e["text"] = (e.get("text") or "") + note
                e["tier"] = "C"

    notes = {x["name"]: x["note"] for x in sites.values() if x.get("note") and x.get("name")}

    def emit(eid, kind, tier, company, site, text):
        if kind in NOTE_KINDS and notes.get(site):
            text = f"{text} · ⓘ {notes[site]}"
        if eid not in known:
            known.add(eid)
            fresh.append({"id": eid, "kind": kind, "tier": tier, "company": company, "site": site, "text": text[:1000], "detectedAt": stamp})

    scanned = set()
    for comp in cfg["companies"]:
        own = re.compile(comp["own"])
        comp_first = first or comp["company"] not in known_companies
        judge = working if comp.get("schedule") == "weekday" else None
        off = judge is not None and not judge(now)  # 평일 교대 공장의 쉬는 시간: 빠짐을 세지 않는다
        rows, ok = [], True
        for term in comp["terms"]:
            if clock() - started > RUN_BUDGET:
                errors.append(f"{term}(실행 시간 한도 — 다음 실행에)")
                ok = False
                continue
            try:
                rows += fetch(term, key, get=get, sleep=sleep)
                ok_terms += 1
            except ApiError as e:
                errors.append(f"{term}({e})")
                ok = False
            sleep(0.3)
        if ok:
            scanned.add(comp["company"])
        by_site = {}
        for x in rows:
            name = str(x.get("fact_manage_nm") or "").strip()
            if name and own.search(name):
                by_site.setdefault(name, []).append(x)
        for name, xs in by_site.items():
            sid = f"{comp['company']}:{norm(name)}"
            seen_sites.add(sid)
            s = sites.get(sid)
            if s is None:
                s = {"id": sid, "company": comp["company"], "name": name, "area": xs[0].get("area_nm"), "firstSeen": stamp, "stacks": {}}
                sites[sid] = s
                watched = age_days(prev.get("baselineSince"), now) if prev.get("baselineSince") else 0.0
                if not comp_first:
                    # 감시를 14일 넘게 돌린 뒤 처음 나타난 사업장만 A(초기에는 검색 결과가 덜 차거나 쉬던 사업장일 수 있다)
                    tier = new_tier(watched)
                    emit(f"stk:newsite:{sid}", "새 사업장(굴뚝 측정)", tier, comp["company"], name,
                         f"{name}({xs[0].get('area_nm') or '지역 미상'}) 굴뚝 자동측정 목록에 새로 나타남 — 배출구 {len(xs)}개. 새 공장·설비 가동 또는 이름 변경일 수 있음(회사 확인)"
                         + ("" if tier == "A" else f" · 감시 {watched:.1f}일째라 쉬던 사업장이 다시 측정된 것일 수 있음"))
            s.update(name=name, area=xs[0].get("area_nm") or s.get("area"), lastSeen=stamp)
            note = site_note(comp, name, s.get("area"))
            if note:
                s["note"], notes[name] = note, note
            else:
                s.pop("note", None)
                notes.pop(name, None)
            stacks = s.setdefault("stacks", {})
            # 이 사업장을 본 실행 수(예전 저장본에는 없으니 배출구 관측 수 가운데 가장 큰 값으로 시작)
            s["runs"] = s.get("runs", max([len(v.get("obs") or []) for v in stacks.values()] or [0])) + 1
            present, new_codes, halted, resumed = set(), [], [], []
            for x in xs:
                code = str(x.get("stack_code") or "").strip()
                if not code:
                    continue
                present.add(code)
                st = stacks.get(code)
                if st is not None:  # 빠졌다던 배출구가 지금 있으면(예전 저장본에서 이미 돌아온 것도) 그 이벤트에 '다시 나타남'
                    settle(f"stk:gone:{sid}:{code}", f" — 이후 다시 나타남(측정 {x.get('mesure_dt')}, 일시적 누락)")
                    if st.get("longGoneFor"):
                        settle(f"stk:longgone:{sid}:{code}", f" — 이후 다시 나타남(측정 {x.get('mesure_dt')})")
                        st.pop("longGoneFor", None)
                if st is None:
                    st = {"firstSeen": stamp, "obs": []}
                    stacks[code] = st
                    if not comp_first and not s.get("firstSeen") == stamp:
                        new_codes.append((code, x))
                mdt = x.get("mesure_dt")
                st.pop("workMissing", None)
                stt = status_of(x)
                before = (st.get("status") or [None])[0]
                last_v = (st.get("obs") or [[None, None]])[-1][1]
                if stt is None or (before in STOP_STATUS and stt not in STOP_STATUS):
                    # '가동중지'였던 배출구가 다시 평소 같은 숫자를 보냄 — 재가동일 수 있다(아래에서 사업장 단위로 묶음).
                    # 평일 교대 공장은 세지 않는다(아침마다 가동중지 → 숫자가 일상)
                    cur = peak(x)
                    if before in STOP_STATUS and cur is not None and cur >= MEANINGFUL and judge is None:
                        resumed.append((code, before, str((st.get("status") or [None, ""])[1]), cur))
                if stt is None:
                    st.pop("status", None)
                elif before != stt:
                    st["status"] = [stt, mdt]
                    # 숫자로 돌던 배출구가 이번 측정에 '가동중지'로 바뀐 것(사업장이 보낸 시설 멈춤 신고) — 아래에서 사업장 단위로 묶는다.
                    # 평일 교대 공장은 세지 않는다(교대가 끝난 저녁의 가동중지는 일상). 다른 칸 숫자가 평소처럼 남아 있으면 세지 않는다.
                    cur = peak(x)
                    if (stt in STOP_STATUS and before not in STOP_STATUS and last_v is not None and last_v >= MEANINGFUL
                            and (cur is None or is_low(cur, last_v)) and judge is None):
                        halted.append((code, stt, last_v))
                if st.get("lastDt") == mdt and st.get("obs"):
                    st["missing"] = 0
                    continue  # 측정 시각이 그대로면 같은 관측을 두 번 쌓지 않는다
                if backfill_status_gap(st, stt):
                    st["statusBackfilled"] = True
                st["obs"] = (st.get("obs") or [])[-(OBS_KEEP - 1):] + [[mdt, reading(x)]]
                st["lastDt"], st["missing"] = mdt, 0
                # 배출허용기준 초과: 새 측정 시각마다 한 번. 처음 넘으면 B, 다음 측정(이 감시의 다음 실행)에도 넘으면 A(지속)
                over = {p: (m, lim) for p, m, lim in exceedances(x)}
                runs = st.setdefault("exceed", {})
                for p in list(runs):
                    if p not in over:
                        del runs[p]
                # 직전까지 '가동중지'였거나 멈춤으로 판단하던 배출구가 다시 값을 보내며 넘은 것: 가동 개시 직후 값일 수 있다
                # (11-03 13:47 금호석유화학 여수제1에너지 4번: 10:30 '가동중지' → 12:30 먼지 47.99/20·질소산화물 88.24/59.5)
                restarting = before in STOP_STATUS or bool(st.get("stoppedSince"))
                for p, (m, lim) in over.items():
                    ep = runs.get(p) or {"start": mdt, "count": 0, "first": [m, lim], **({"restart": True} if restarting else {})}
                    ep["count"] += 1
                    runs[p] = ep
                    s.setdefault("exceedLog", [])
                    s["exceedLog"] = (s["exceedLog"] + [{"stack": code, "pollutant": p, "value": m, "limit": lim, "at": mdt}])[-EXCEED_KEEP:]
                    odd = " — 기준의 20배 넘는 값이라 측정기 이상값일 수 있음" if m > lim * 20 else ""
                    what = f"{name} 배출구 {code}번 {POL_KO[p]} 측정값 {m:g}이 배출허용기준 {lim:g}을 넘음(기준의 {m / lim:.1f}배, 측정 {mdt}){odd}"
                    tail = " · 실시간 자동측정 값(확정 전). 측정기 점검·교정 중 값일 수 있음 — 초과 판정·행정처분은 한국환경공단·관할 지자체 확인"
                    if comp_first:
                        continue
                    # 기준을 5% 안쪽으로 넘은 값은 한 단계 낮춘다(처음 C, 지속 B) — 실시간 값의 반올림·교정 오차 범위일 수 있다
                    # (10-31 운영: 고려아연 온산제련소 77번 황산화물 141.58/140, 기준의 1.01배 한 번이 B로 떴다).
                    small = max(m / lim, ep["first"][0] / ep["first"][1]) < MARGINAL
                    note = f" — 기준을 {MARGINAL - 1:.0%} 안쪽으로 넘은 값이라 한 단계 낮춤" if small else ""
                    # 재가동 직후 처음 넘은 값은 한 단계 낮춘다(B→C). 다음 실행에도 넘으면(지속) 그대로 A — 가동 개시 값만으로 설명되지 않는다.
                    if ep.get("restart"):
                        note += RESTART_NOTE
                    if ep["count"] == 1:
                        emit(f"stk:exceed:{sid}:{code}:{p}:{ep['start']}", "배출허용기준 초과(측정값)", "C" if small or ep.get("restart") else "B",
                             comp["company"], name, what + note + tail)
                    elif ep["count"] == 2:
                        emit(f"stk:exceed2:{sid}:{code}:{p}:{ep['start']}", "배출허용기준 초과 지속", "B" if small else "A", comp["company"], name,
                             f"{what} — {ep['start']} 측정부터 이 감시의 실행 2번 연속 초과(처음 {ep['first'][0]:g}){note}" + tail)
            if new_codes:
                days = age_days(s.get("firstSeen"), now)
                tier = new_tier(days)
                if s["runs"] > MATURE_RUNS and len(new_codes) < BURST and tier != "C":
                    for code, x in new_codes:
                        emit(f"stk:newstack:{sid}:{code}", "새 배출구", tier, comp["company"], name,
                             f"{name} 굴뚝 자동측정에 새 배출구 {code}번이 생김(측정 {x.get('mesure_dt')}, 가장 큰 측정값 {peak(x)}, "
                             f"이 사업장을 {days:.0f}일·{s['runs'] - 1}번 지켜보는 동안 없던 번호) — "
                             + ("새 설비 가동 또는 오래 쉬던 설비 재가동 가능성" if tier == "A" else "간헐 가동 설비가 다시 측정된 것일 수 있음(새 설비 여부 미확인)")
                             + ", 어떤 설비인지는 회사 확인")
                else:
                    codes = [c for c, _ in new_codes]
                    emit(f"stk:burst:{comp['company']}:{name}:{stamp}", "배출구 목록 보강", "C", comp["company"], name,
                         f"{name} 굴뚝 자동측정 목록에 배출구 {len(codes)}개가 새로 보임({', '.join(codes[:12])}{' 외' if len(codes) > 12 else ''}) — "
                         + ("한꺼번에 여러 개라 " if len(codes) >= BURST else f"이 사업장을 {days:.1f}일·{s['runs'] - 1}번만 봐서 ")
                         + "간헐 가동·측정 자료 지연일 수 있어 새 설비로 보지 않음")
            # 사업장이 직전 실행에 통째로 목록에서 빠졌다가 돌아왔으면, 그 전에 빠졌던 배출구 횟수를 이어 세지 않는다
            # (11-03 09:20 고려아연 온산 15개: 11-02 18:20 빠짐 → 21:20~06:20 사업장 통째 빠짐 → 09:20 '2번 연속' B. 15시간 사이 두 번이었다)
            came_back = s.get("missingRuns", 0) > 0
            for code, st in stacks.items():
                if code not in present and not off:
                    if came_back:
                        st["missing"], st["workMissing"] = 0, 0
                    st["missing"] = st.get("missing", 0) + 1
                    if working(now):
                        st["workMissing"] = st.get("workMissing", 0) + 1
                    wm = st.get("workMissing", 0)
                    what = f"{name} 배출구 {code}번이 굴뚝 자동측정 목록에서 {MISSING_RUNS}번 연속 빠짐 — 설비 폐쇄·측정 대상 변경일 수 있음(회사 확인)"
                    # 6번 넘게 관측된 배출구만(초기에는 측정 자료가 늦게 들어와 목록이 들쑥날쑥하다).
                    # B는 평일 일하는 시간에 2번 연속 빠졌을 때만 — 쉬는 시간에 빠진 것은 C로 알리고 평일에 다시 본다.
                    if not comp_first and len(st.get("obs") or []) >= MIN_OBS:
                        if st["missing"] == MISSING_RUNS:
                            emit(f"stk:gone:{sid}:{code}:{day}", "배출구 목록에서 빠짐", "B" if wm >= MISSING_RUNS else "C", comp["company"], name,
                                 what + ("" if wm >= MISSING_RUNS else REST_NOTE))
                        elif wm == MISSING_RUNS:
                            emit(f"stk:gone:{sid}:{code}:{day}:work", "배출구 목록에서 빠짐", "B", comp["company"], name,
                                 f"{name} 배출구 {code}번이 쉬는 시간부터 {st['missing']}번 연속 굴뚝 자동측정 목록에서 빠졌고 평일 일하는 시간에도 "
                                 f"{MISSING_RUNS}번 연속 없음 — 설비 폐쇄·측정 대상 변경일 수 있음(회사 확인)")
                    last_t = obs_time(st.get("lastDt"))
                    if not comp_first and len(st.get("obs") or []) >= MIN_OBS and last_t is not None and st["missing"] >= MISSING_RUNS \
                            and st.get("longGoneFor") != st.get("lastDt"):
                        gone_h = working_hours_between(last_t, now, judge) if judge else (now - last_t).total_seconds() / 3600
                        if gone_h >= LONG_GONE_HOURS:
                            st["longGoneFor"] = st.get("lastDt")
                            vals = [v for _, v in st.get("obs") or [] if v is not None]
                            usual = statistics.median(vals) if vals else None
                            emit(f"stk:longgone:{sid}:{code}:{str(st.get('lastDt'))[:10]}", "배출구 오래 빠짐", "B", comp["company"], name,
                                 f"{name} 배출구 {code}번이 사흘 넘게 굴뚝 자동측정 목록에 없음 — 마지막 측정 {st.get('lastDt')}"
                                 + (f"(평소 {usual:.1f})" if usual is not None else "") + f", 그 뒤 {'일하는 시간 ' if judge else ''}{gone_h:.0f}시간. "
                                 "멈춘 배출구는 목록에 '가동중지'로 남으므로 측정 대상에서 빠진 것일 수 있음 — 설비 폐쇄·철거·측정 대상 변경인지 회사·환경공단 확인")

            # 사업장 가동 판단: 평소 움직이던 배출구 가운데 멈춘 것
            judged = {code: stack_state(st, now, judge) for code, st in stacks.items() if code in present}
            meaningful = {c: b for c, (state, b) in judged.items() if state in ("running", "stopped")}
            stopped = sorted((c for c, (state, _) in judged.items() if state == "stopped"), key=lambda c: -(judged[c][1] or 0))
            was = set(s.get("stopped") or [])
            newly = [c for c in stopped if c not in was]
            s["stopped"], s["meaningful"] = stopped, len(meaningful)
            # 오래 멈춘 배출구(사흘 넘게): 사업장 크기와 상관없이 B 한 번. 멈춤 시작 시각은 배출구에 남긴다(관측은 4일치만 쌓여
            # 다시 셀 때마다 시작이 밀린다) — 다시 움직이면 지운다.
            for c, (state, _) in judged.items():
                if state == "running":
                    log_stop_end(stacks[c], stacks[c].get("lastDt"), now)
                    for k in ("stoppedSince", "usual", "longStopFor"):
                        stacks[c].pop(k, None)
            fresh_long = []
            for c in stopped:
                st = stacks[c]
                since = obs_time(st.get("stoppedSince")) if st.get("stoppedSince") else None
                if since is None:
                    since = stopped_since(st, judged[c][1] or 0, judge) or obs_time(st.get("lastDt"))
                    if since is None:
                        continue
                    st["stoppedSince"], st["usual"] = f"{since:%Y-%m-%d %H:%M}", round(judged[c][1] or 0, 3)
                hours = working_hours_between(since, now, judge) if judge else (now - since).total_seconds() / 3600
                if hours >= LONG_STOP_HOURS and st.get("longStopFor") != st["stoppedSince"]:
                    st["longStopFor"] = st["stoppedSince"]
                    fresh_long.append((c, since, hours))
            if fresh_long and not comp_first:
                emit(f"stk:longstop:{sid}:{','.join(c for c, _, _ in fresh_long[:6])}:{day}", "배출구 오래 멈춤", "B", comp["company"], name,
                     f"{name}: 배출구 {len(fresh_long)}개가 사흘 넘게 평소의 10% 아래 — "
                     + ", ".join(f"{c}번(평소 {judged[c][1]:.1f}→최근 {stacks[c]['obs'][-1][1] if stacks[c].get('obs') else '?'}, "
                                 f"{since:%m-%d %H:%M}부터 {'일하는 시간 ' if judge else ''}{h:.0f}시간{status_note(stacks[c])})" for c, since, h in fresh_long[:6])
                     + f" · 사업장 전체 평소 움직이던 {len(meaningful)}개 중 지금 멈춤 {len(stopped)}개. 일상 정비보다 긴 멈춤 — "
                     "설비 정지·개수·연료 전환·측정기 이상 중 무엇인지는 회사 확인(배출구 번호만 있고 설비 이름은 자료에 없음)")
            top = sorted(meaningful, key=lambda c: -(meaningful[c] or 0))[:3]
            # 상태 글자 전환: 한 실행에 3개 이상, 또는 큰 배출구(평소 값 상위 3)가 '보수중'·'가동중지'로 바뀌면 B(11-03 탐침 117:
            # 포스코 광양 배출구 34개 '보수중'·8개 '가동중지' — 예전엔 숫자만 읽어 보이지 않았다. 언제부터인지는 이 감시가 본 뒤부터만 안다)
            # 큰 배출구는 평소 값 기준(방금 바뀐 배출구는 아직 '멈춤' 판단 전이라 meaningful에 없다)
            top_base = sorted((c for c, (_, b) in judged.items() if b is not None and b >= MEANINGFUL), key=lambda c: -(judged[c][1] or 0))[:3]
            halt_b = bool(halted) and size_rule([c for c, _, _ in halted], judged, top_base)
            if halted and not comp_first and not off and (halt_b or len(halted) >= 3):
                now_halt = {k: sum(1 for v in stacks.values() if (v.get("status") or [None])[0] == k) for k in SHOWN_STATUS}
                emit(f"stk:halt:{sid}:{day}:{','.join(c for c, _, _ in halted[:6])}", HALT_KINDS[0], "B" if halt_b else "C", comp["company"], name,
                     f"{name}: 배출구 {len(halted)}개가 이번 측정에서 상태 글자 '가동중지'로 바뀜(사업장이 보낸 시설 멈춤 신고) — "
                     + ", ".join(f"{c}번(직전 값 {v:g}→'{t}')" for c, t, v in halted[:8])
                     + f" · 사업장 전체 지금 가동중지 {now_halt['가동중지']}개(측정기 보수중 {now_halt['보수중']}개). 정기보수·설비 개수·가동 조정 중 무엇인지는 회사 확인"
                     + HALT_NOTE + ("" if halt_b else HALT_SMALL_NOTE))
            resume_b = bool(resumed) and size_rule([c for c, _, _, _ in resumed], judged, top_base)
            if resumed and not comp_first and not off and (resume_b or len(resumed) >= 3):
                now_halt = {k: sum(1 for v in stacks.values() if (v.get("status") or [None])[0] == k) for k in SHOWN_STATUS}
                emit(f"stk:resume:{sid}:{day}:{','.join(c for c, _, _, _ in resumed[:6])}", HALT_KINDS[1], "B" if resume_b else "C", comp["company"], name,
                     f"{name}: '가동중지'였던 배출구 {len(resumed)}개가 다시 측정값을 보냄 — "
                     + ", ".join(f"{c}번('{t}', 처음 본 측정 {since[5:] or '?'} → 지금 {v:g})" for c, t, since, v in resumed[:8])
                     + f" · 사업장 전체 지금 가동중지 {now_halt['가동중지']}개(측정기 보수중 {now_halt['보수중']}개). 재가동인지는 회사 확인"
                     + HALT_NOTE + ("" if resume_b else HALT_SMALL_NOTE))
            share = len(stopped) / len(meaningful) if meaningful else 0
            load = sum(v or 0 for v in meaningful.values()) or 1
            # 예전 규칙(2개 이상이면 B)으로 저장된 작은 멈춤은 사업장 크기 기준으로 다시 본다(10-31 09:17 포스코 광양 137개 중 2개).
            # 사업장 크기 규칙(SIZE_RULE_FROM) 뒤에 생긴 이벤트는 그 규칙으로 이미 판정했다 — 다시 보면 그때그때 평소 움직이던 수가
            # 달라져(배출구가 목록에서 빠지거나 상태 글자로 판단 안 함이 되면) '1개 중 1개'처럼 엉뚱하게 내려간다(11-03 13:47 현대제철 포항1공장 7번).
            for e in events:
                if e.get("tier") != "B" or e.get("kind") != "배출구 멈춤 신호" or not str(e.get("id", "")).startswith(f"stk:stop:{sid}:"):
                    continue
                if str(e.get("detectedAt") or "") >= SIZE_RULE_FROM:
                    continue
                codes = re.findall(r"(\S+?)번\(평소", e.get("text") or "")
                if (codes and len(codes) < max(2, math.ceil(len(meaningful) * STOP_B_SHARE)) and not any(c in top for c in codes)
                        and sum(meaningful.get(c) or 0 for c in codes) < STOP_B_LOAD * load):
                    e["tier"] = "C"
                    e["text"] = (e.get("text") or "") + (f" — 평소 움직이던 {len(meaningful)}개 중 {len(codes)}개라 일상 정비 수준일 수 있어 C로 바로잡음"
                                                         "(사업장 크기 기준: 5%·상위 3·평소 값 10%)")
            if newly:
                # 멈춤 시작(끝에서부터 연달아 낮은 첫 측정)을 함께 적는다 — 상태 글자를 11-03에야 읽기 시작해, 그 전부터 '가동중지'였던
                # 배출구가 오늘 처음 멈춤으로 잡혔다(11-03 11:45 현대제철 순천 81~83번 A: 실제로는 10-31 13:30·20:30부터).
                def desc(c):
                    st = stacks[c]
                    began = f", 멈춤 {str(st['stoppedSince'])[5:16]}부터" if st.get("stoppedSince") and st.get("stoppedSince") != st.get("lastDt") else ""
                    return (f"{c}번(평소 {judged[c][1]:.1f}→최근 {st['obs'][-1][1] if st.get('obs') else '?'}, 측정 {st.get('lastDt')}{began}"
                            f"{status_note(st)}{stop_history(st, now)})")
                if len(stopped) >= 2 and share >= 0.5:
                    emit(f"stk:down:{sid}:{day}", "사업장 가동 중단 신호", "A", comp["company"], name,
                         f"{name}: 평소 움직이던 배출구 {len(meaningful)}개 중 {len(stopped)}개가 {STOP_RUNS}번 연속 평소의 10% 아래 — "
                         + ", ".join(desc(c) for c in stopped[:6]) + " · 설비 정지·정비·측정기 점검일 수 있음(회사 확인)")
                # 배출구 100개 넘는 제철소에서 2개 멈춤은 일상 정비일 수 있다(10-31 포스코 광양 137개 중 2개 B) — 사업장 크기에 맞춘다
                elif (len(newly) >= max(2, math.ceil(len(meaningful) * STOP_B_SHARE)) or any(c in top for c in newly)
                      or (len(newly) >= 2 and sum(judged[c][1] or 0 for c in newly) >= STOP_B_LOAD * (sum(v or 0 for v in meaningful.values()) or 1))):
                    told = announced_halts(fresh + events, sid, now)
                    early = told and all(c in told for c in newly)
                    emit(f"stk:stop:{sid}:{day}", "배출구 멈춤 신호", "C" if early else "B", comp["company"], name,
                         f"{name}: 배출구 {len(newly)}개가 {STOP_RUNS}번 연속 평소의 10% 아래(사업장 전체 평소 움직이던 {len(meaningful)}개 중 멈춤 {len(stopped)}개) — "
                         + ", ".join(desc(c) for c in newly[:6]) + " · 정비·점검일 수 있음(회사 확인)"
                         + (f" — 같은 배출구를 {min(told[c] for c in newly)[5:16].replace('T', ' ')} '가동중지 전환'(B)으로 먼저 알려 C" if early else ""))
            if was and len(was) >= 2 and len(stopped) <= len(was) / 2 and s.get("downFlag"):
                emit(f"stk:up:{sid}:{day}", "사업장 재가동 신호", "B", comp["company"], name,
                     f"{name}: 멈췄던 배출구 {len(was)}개 중 {len(was) - len(stopped)}개 측정값이 평소 수준으로 돌아옴")
            s["downFlag"] = bool(len(stopped) >= 2 and share >= 0.5)

    # 목록에서 사라진 사업장(그 회사 검색을 다 읽었을 때만): 배출구 누락 횟수로 센다
    for sid, s in sites.items():
        if sid not in seen_sites and s["company"] in scanned:
            if s["company"] in weekday_companies and not working(now):
                continue  # 평일 교대 공장은 쉬는 시간에 목록에서 빠져도 세지 않는다(값이 없으면 목록에 안 나온다)
            s["missingRuns"] = s.get("missingRuns", 0) + 1
            if working(now):
                s["workMissing"] = s.get("workMissing", 0) + 1
            wm = s.get("workMissing", 0)
            if s.get("runs", 0) < MATURE_RUNS:  # 예전 규칙으로 B가 된 이른 사업장의 '빠짐'도 C로(10-30 엘에스엠앤엠)
                settle(f"stk:sitegone:{sid}", f" — 이 사업장을 {s.get('runs', 0) or '몇'}번만 봐서 일시적 누락일 수 있음", marker="일시적 누락일 수 있음")
            mature = s.get("runs", 0) >= MATURE_RUNS
            # B는 평일 일하는 시간에 2번 연속 빠졌을 때만. 주말·공휴일·밤에 빠진 것은 C로 먼저 알리고, 평일에도 빠져 있으면 그때 B.
            if s["missingRuns"] == MISSING_RUNS and not first:
                emit(f"stk:sitegone:{sid}:{day}", "사업장 목록에서 빠짐(굴뚝 측정)", "B" if mature and wm >= MISSING_RUNS else "C", s["company"], s["name"],
                     f"{s['name']}이 굴뚝 자동측정 목록에서 {MISSING_RUNS}번 연속 빠짐 — "
                     + (("폐쇄·이름 변경·측정 대상 제외 확인" + ("" if wm >= MISSING_RUNS else REST_NOTE)) if mature
                        else f"이 사업장을 {s.get('runs', 0)}번만 봐서 일시적 누락일 수 있음"))
            elif mature and wm == MISSING_RUNS and s["missingRuns"] > MISSING_RUNS and not first:
                emit(f"stk:sitegone:{sid}:work:{day}", "사업장 목록에서 빠짐(굴뚝 측정)", "B", s["company"], s["name"],
                     f"{s['name']}이 쉬는 시간부터 {s['missingRuns']}번 연속 굴뚝 자동측정 목록에서 빠졌고 평일 일하는 시간에도 {MISSING_RUNS}번 연속 없음 — "
                     "폐쇄·이름 변경·측정 대상 제외 확인")
            seen_t = dt.datetime.fromisoformat(s["lastSeen"]) if s.get("lastSeen") else None
            if mature and not first and seen_t is not None and s["missingRuns"] >= MISSING_RUNS and s.get("longGoneFor") != s.get("lastSeen"):
                weekday = s["company"] in weekday_companies
                gone_h = working_hours_between(seen_t, now, working) if weekday else (now - seen_t).total_seconds() / 3600
                if gone_h >= LONG_GONE_HOURS:
                    s["longGoneFor"] = s.get("lastSeen")
                    emit(f"stk:longsitegone:{sid}:{str(s.get('lastSeen'))[:10]}", "사업장 오래 빠짐(굴뚝 측정)", "B", s["company"], s["name"],
                         f"{s['name']}이 사흘 넘게 굴뚝 자동측정 목록에 없음 — 마지막으로 보인 실행 {str(s.get('lastSeen'))[:16]}, "
                         f"그 뒤 {'일하는 시간 ' if weekday else ''}{gone_h:.0f}시간·{s['missingRuns']}번 연속(배출구 {len(s.get('stacks') or {})}개). "
                         "폐쇄·이름 변경(새 이름 사업장으로 다시 나타났는지)·측정 대상 제외인지 회사·환경공단 확인")
        elif sid in seen_sites:
            # 지금 목록에 있으면 그 사업장의 '빠짐' 이벤트는 모두 풀린 것 — 예전 실행에서 이미 돌아와 표시가 빠진 것도 여기서 붙인다
            settle(f"stk:sitegone:{sid}", f" — 이후 다시 나타남(확인 {stamp[:16]}, 일시적 누락)")
            if s.get("longGoneFor"):
                settle(f"stk:longsitegone:{sid}", f" — 이후 다시 나타남(확인 {stamp[:16]})")
                s.pop("longGoneFor", None)
            s["missingRuns"] = 0
            s.pop("workMissing", None)

    annotate_late_starts(events, sites, now)
    collapse_gone_bursts(fresh + events)
    collapse_long_gone(fresh + events)
    total_terms = sum(len(c["terms"]) for c in cfg["companies"])
    status = "failed" if ok_terms == 0 else ("partial" if errors else "complete")
    checks = [{"source": "굴뚝 자동측정(CleanSYS)", "status": "ok" if not errors else ("failed" if not ok_terms else "partial"),
               "returned": len(seen_sites), "terms": f"{ok_terms}/{total_terms}", **({"error": "; ".join(errors[:5])} if errors else {})}]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "checks": checks,
            "baselineSince": prev.get("baselineSince") or stamp,
            "sites": sorted(sites.values(), key=lambda s: (s["company"], s["name"])), "events": (fresh + events)[:300],
            "rules": ["굴뚝 자동측정(TMS) 실시간 값을 이 감시가 3시간마다 쌓은 이력이다. 배출구 이름·설비 종류는 자료에 없다(번호만).",
                      "측정값이 평소의 10% 아래로 떨어진 것은 설비 정지·정비·측정기 점검·연료 전환일 수 있다. 가동 중단은 회사 확인 전 미확인.",
                      "평소 값이 1 미만인 배출구(원래 거의 0)는 멈춤 판단을 하지 않는다. 관측이 6번 모이기 전에는 판단하지 않는다.",
                      "멈췄다 다시 움직인 배출구는 시작·끝을 남겨(11-03부터, 최근 8번·90일) 다음 멈춤 알림에 최근 30일 앞선 멈춤을 함께 적는다 — 되풀이되는 짧은 멈춤은 일상 정비·간헐 가동일 수 있다. 기록 시작 전 멈춤은 모른다.",
                      "배출구 멈춤 B는 새로 멈춘 배출구가 사업장 평소 움직이던 배출구의 5%(최소 2개) 이상, 큰 배출구(평소 값 상위 3), 또는 평소 값 합의 10% 이상일 때. 큰 제철소의 배출구 한두 개는 일상 정비일 수 있어 화면 목록에만 보인다.",
                      "측정값 칸에 숫자 대신 상태 글자가 오면 그대로 남긴다: '측정자료확인중(가동중지)'는 사업장이 보낸 시설 멈춤 신고(값 0으로 셈), '보수중'·'기기점검'·'미수신'·'측정자료확인중'은 측정기 쪽 상태(판단 안 함).",
                      "숫자로 돌던 배출구가 '가동중지'(사업장이 보낸 시설 멈춤 신고)로 바뀐 순간을 알린다(연속 가동 사업장만): 멈춤 B와 같은 사업장 크기 기준(5%·최소 2개, 큰 배출구, 평소 값 합 10%)이면 B, 아니면 3개 이상일 때 C. 거꾸로 다시 숫자를 보내면 '해제'(같은 기준). 먼저 B로 알린 배출구의 멈춤 신호(3번 연속)는 C. 11-03 확인: '가동중지'는 2시간 뒤에도 17개 중 16개 그대로였다.",
                      "한 사업장 배출구가 같은 실행에 3개 이상 한꺼번에 목록에서 빠지면 측정 자료 지연일 수 있어 C(멈춘 배출구는 목록에 '가동중지'로 남는다).",
                      "배출구·사업장이 사흘(평일 교대 공장은 일하는 시간 72시간) 넘게 목록에 없으면 '오래 빠짐' B 한 번 — 멈춘 배출구는 '가동중지'로 남으므로 측정 대상에서 빠진 것(폐쇄·철거·측정 대상 변경)일 수 있다. 같은 사업장 같은 실행 3개 이상이면 한 줄만 B. 다시 나타나면 C.",
                      f"다만 사흘(평일 교대 공장은 일하는 시간 {LONG_STOP_HOURS}시간) 넘게 멈춘 배출구는 사업장 크기와 상관없이 '배출구 오래 멈춤' B로 한 번 알린다. 멈춤이 이어지는 동안은 멈추기 전 평소 값으로 본다.",
                      "평일 교대 공장(완성차·타이어·전선·변압기·중공업)은 주말·공휴일·밤(0~7시) 관측을 멈춤 판단·평소 값에서 빼고, 그 시간의 목록 빠짐도 세지 않는다. 제철·제련·석유화학 같은 연속 가동 사업장은 주말 멈춤도 그대로 본다.",
                      f"새 배출구 번호·새 사업장은 쉬던 설비가 다시 측정돼도 생긴다. 그 사업장을 {NEW_A_DAYS}일 넘게 지켜본 뒤 처음 보인 것만 A, {NEW_B_DAYS}~{NEW_A_DAYS}일 B, 그 전은 C.",
                      "배출허용기준 초과는 같은 줄에 실린 그 배출구의 물질별 기준과 실시간 측정값을 비교한 것이다. 처음 넘으면 B, 다음 실행에도 넘으면 A(기준을 5% 안쪽으로 넘은 값은 한 단계 낮춰 C·B). 측정기 점검·교정 값일 수 있고 초과 판정·처분은 환경공단·지자체 확인.",
                      "직전까지 '가동중지'·멈춤이던 배출구가 다시 값을 보내며 처음 넘은 값은 가동 개시 직후 값일 수 있어 한 단계 낮춘다(B→C). 다음 실행에도 넘으면 지속 A 그대로.",
                      "조회 실패는 0이 아니라 미확인."],
            "confirmedScoops": 0}


# 실행 간격: '연달아 N번'(멈춤 3번·빠짐 2번)을 실행 수로 세므로, 실행이 몰리면(Cloudflare 예약 요청 뒤 늦게 온 GitHub 예약, 코드 push)
# 몇 분 만에 '2번 연속 빠짐'이 된다. 직전 실행이 이만큼 안이면 건너뛴다(수동 실행 force는 예외).
MIN_GAP_MINUTES = 100
# 코드 병합(push)으로 돈 실행은 정기 실행(3시간 칸)을 밀어내지 않는다 — 11-03 13:47 push 실행 때문에 15:20 정기 실행이 100분 문턱에
# 걸려 건너뛰어져 다음 실행이 18:20(6시간 반 간격)이 될 뻔했다. 직전 실행이 push면 정기 실행은 PUSH_GAP_MINUTES만 지나면 돈다.
PUSH_GAP_MINUTES = 45


def gap_for(previous, event):
    """이번 실행의 최소 간격(분): 직전이 push 실행이고 이번이 정기·수동 실행이면 PUSH_GAP_MINUTES, 아니면 MIN_GAP_MINUTES."""
    prev_trigger = (previous or {}).get("trigger") if isinstance(previous, dict) else None
    return PUSH_GAP_MINUTES if prev_trigger == "push" and event and event != "push" else MIN_GAP_MINUTES


def too_soon(previous, now, gap=MIN_GAP_MINUTES):
    """직전 실행이 gap분 안이면 그 경과 분(int), 아니면 None."""
    stamp = (previous or {}).get("generatedAt") if isinstance(previous, dict) else None
    if not stamp:
        return None
    try:
        last = dt.datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=KST)
    minutes = (now - last).total_seconds() / 60
    return int(minutes) if 0 <= minutes < gap else None


def main():
    argparse.ArgumentParser(description="출입처 공장 굴뚝 측정(가동 신호) 감시(기자 전용 저장소로)").parse_args()
    import private_store
    now = dt.datetime.now(KST)
    key = (os.environ.get("DATA_GO_KR_KEY") or "").strip()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not key:
        print("::warning title=kr-stacks::공공데이터 키(DATA_GO_KR_KEY) 미설정 — 미확인")
        return
    previous = None
    if token:
        try:
            previous = private_store.get("kr-stacks", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-stacks-state::이전 상태 조회 실패({e}) — 이번 실행은 기준선")
    event = os.environ.get("GITHUB_EVENT_NAME", "").strip()
    need = gap_for(previous, event)
    gap = too_soon(previous, now, need)
    if gap is not None and not os.environ.get("STACKS_FORCE", "").strip():
        print(f"::notice title=kr-stacks::직전 실행 {gap}분 전 — 건너뜀(실행 간격 {need}분 이상 유지: '연달아 N번' 판단이 몇 분 만에 차지 않게)")
        return
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    doc = run(cfg, now=now, previous=previous, key=key)
    if event:
        doc["trigger"] = event
    new = [e for e in doc["events"] if e["detectedAt"] == doc["generatedAt"]]
    stacks = sum(len(s.get("stacks") or {}) for s in doc["sites"])
    stopped = sum(len(s.get("stopped") or []) for s in doc["sites"])
    print(f"::notice title=kr-stacks::상태 {doc['status']} · 사업장 {len(doc['sites'])} · 배출구 {stacks} · 지금 멈춤 판단 {stopped} · "
          f"이번 이벤트 {{'A': {sum(1 for e in new if e['tier'] == 'A')}, 'B': {sum(1 for e in new if e['tier'] == 'B')}}}")
    print(f"::notice title=kr-stacks-checks::{doc['checks'][0]}")
    if not token:
        print("::warning title=kr-stacks-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("굴뚝 측정 조회 전체 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("kr-stacks", doc, token)
    print(f"::notice title=kr-stacks-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
