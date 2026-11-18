"""국회 회의록 — 출입 업종 상임위(산자중기위·기후에너지환경노동위·국토위·재경위·정무위, 소위 포함) 회의록과 국정감사 회의록에
출입처 이름이 나온 대목(기자 전용 저장소 assembly-minutes).

- 왜: 11-18 기자 '자료 더 긁어올 곳'. 지방의회 회의록(council_watch.py)은 있었지만 국회 회의록은 없었다. 상임위·소위 회의록에는
  장관·차관·증인의 답변이 그대로 남고, 기사로 다 나오지 않는다(11-09 산자중기위 회의록: 현대자동차그룹 새만금 9조원 투자와 로봇 실증 질의).
- 원천: 열린국회정보 Open API(키 ASSEMBLY_API_KEY — 국회 법안 감시와 같은 키).
  · 위원회 회의록 `ncwgseseafwbuheph`(DAE_NUM=22·CONF_DATE=날짜, 안건(SUB_NAME)마다 한 줄 — CONFER_NUM으로 묶음)
  · 국정감사 회의록 `VCONFAPIGCONFLIST`(ERACO=제22대, 최신이 앞)
  · 회의록 PDF `record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id=…`(robots.txt 없음 — 11-18 탐침: 404)
  11-18 탐침: 회의일 뒤 며칠 안에 올라온다(11-13 회의가 11-18에 보임). 화면(xml.do)은 그림이라 글자가 없고, PDF는 pdfminer로 띄어쓰기까지 뽑힌다
  (pypdf는 띄어쓰기가 사라졌다). 발언자는 '◯' 표시 뒤(◯산업통상부장관 김정관).
- 날마다 최근 21일 회의일을 하루씩 묻고(21번), 국정감사 회의록 최신 100줄을 한 번 묻는다. 지켜보는 위원회의 새 회의록만 PDF를 받아
  출입처 이름(지방의회 회의록과 같은 이름 규칙 + '현대차·기아')의 앞뒤 150자를 발언자·쪽과 함께 3곳까지 남긴다(한 실행 30개).
- 등급: 회사 이름 앞뒤 60자 안에 불법·과징금·고발·수사·담합·오염·사고·사망·산재·폐쇄·철수·매각·감산·가동 중단·구조조정·하청·리콜·결함·증설·이전 등이
  있고 회의일이 14일 안이면 A, 아니면 C(화면에서 접음 — show_all=true). 국정감사처럼 늦게 읽은 옛 회의는 사건 낱말이 있어도 C.
- 의원 질의는 주장이다 — 정부 답변·회사 확인. 회의록 공개일과 회의일이 다르다. 조회 실패는 미확인(0건 아님).
"""
from __future__ import annotations

import datetime as dt
import io
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import council_watch as cw  # noqa: E402  (출입처 이름 규칙 TERMS)

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "assembly_minutes/v1"
API = "https://open.assembly.go.kr/portal/openapi/"
COMMITTEE = "ncwgseseafwbuheph"     # 위원회 회의록
AUDIT = "VCONFAPIGCONFLIST"         # 국정감사 회의록
PDF = "https://record.assembly.go.kr/assembly/viewer/minutes/download/pdf.do?id={}"
UA = {"User-Agent": "Mozilla/5.0 seoul-reporting-radar (reporter research; National Assembly minutes)"}
DAE, ERACO = "22", "제22대"
# 출입 업종 상임위(소위원회는 이름이 '위원회 이름 + 소위 이름'으로 온다 — 앞이 같으면 같이 본다)
WATCH = ("산업통상자원중소벤처기업위원회", "기후에너지환경노동위원회", "국토교통위원회", "재정경제기획위원회", "정무위원회")
LOOKBACK_DAYS = 21
AUDIT_DAYS = 75
DETAIL_BUDGET = 30
RECENT_DAYS = 14
KEEP_DAYS = 180
SNIPS = 3
WIDTH = 150
NEAR = 60
PAUSE = 0.5
NO_DATA = "INFO-200"
RULES_V = 2   # 2(11-18): 줄바꿈을 붙여 이름 찾기 — 바뀌면 받은 회의록을 다시 읽는다
NOT_POSTED = "등록되지 않았습니다"   # 회의록 PDF 주소가 파일 대신 돌려주는 알림(원본 파일 아직 안 올라옴)
# 출입처 이름: 지방의회 회의록과 같은 규칙 + 국회에서 흔한 '현대차·기아'
# HL만도: 지방의회 규칙의 '만도' 홀로 쓰기는 국회 회의록에서 조사 '~만도'(11-18 첫 실행 'AIDC만도 18.4GW')를 잡았다 —
# 'HL만도·에이치엘만도'와, 앞이 글자·숫자가 아니고 뒤에 공장·노조 같은 낱말이 붙은 '만도'만.
MANDO = r"(?:HL|에이치엘)\s?만\s?도|(?<![가-힣A-Za-z0-9])만도(?=\s?(?:평택|익산|원주|공장|노조|지회|하청|사측|노동자|협력사|모빌리티))"
TERMS = [(c, re.compile(MANDO if c == "HL만도" else p)) for _t, c, p in cw.TERMS]
TERMS.append(("기아", re.compile(r"(?:현대차|현대자동차)\s?[·,및와과]\s?기아(?![가-힣])")))
A_WORDS = re.compile(r"불법|위반|행정처분|과징금|과태료|고발|수사|압수수색|담합|특혜|오염|(?<!우수)유출|누출|악취|사고|사망|산재|산업재해|중대재해|화재|폭발"
                     r"|폐쇄|철수|매각|감산|가동\s?중단|생산\s?중단|구조조정|희망퇴직|불법\s?파견|하청|체불|리콜|결함|증설|신설"
                     r"|(?:공장|본사|사업장|라인|설비|생산)\s?이전|특별\s?(?:감독|감사|점검)")
SPEAKER = re.compile(r"◯\s*(\S+(?:[ \t]+\S+)?)")


def tidy(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def watched(name):
    return any(str(name or "").startswith(w) for w in WATCH)


def pdf_id(url):
    m = re.search(r"[?&]id=(\d+)", str(url or ""))
    return m.group(1) if m else None


def call(get, key, code, **params):
    """(줄들, 전체 건수, 오류). '해당하는 데이터가 없습니다'(INFO-200)는 오류가 아니라 0줄."""
    try:
        r = get(API + code, params={"KEY": key, "Type": "json", "pIndex": params.pop("pIndex", 1), "pSize": params.pop("pSize", 100), **params},
                headers=UA, timeout=40)
        j = r.json()
    except Exception as e:  # noqa: BLE001 — 주소에 키가 있어 주소는 찍지 않는다
        return [], 0, type(e).__name__
    blk = j.get(code) if isinstance(j, dict) else None
    if not blk:
        res = (j or {}).get("RESULT") or {}
        return ([], 0, None) if res.get("CODE") == NO_DATA else ([], 0, f"{res.get('CODE') or '?'} {str(res.get('MESSAGE') or '')[:30]}")
    head = blk[0].get("head", []) if blk else []
    total = next((h.get("list_total_count") for h in head if isinstance(h, dict) and "list_total_count" in h), 0)
    rows = blk[1].get("row", []) if len(blk) > 1 else []
    return [x for x in rows if isinstance(x, dict)], int(total or 0), None


def meetings(get, key, now, sleep=time.sleep):
    """지켜보는 위원회의 회의록 [{pid, kind, committee, meeting, date, agenda, url}], 오류 목록."""
    out, errors = {}, []
    for back in range(LOOKBACK_DAYS):
        day = (now.date() - dt.timedelta(days=back)).isoformat()
        page = 1
        while True:
            rows, total, err = call(get, key, COMMITTEE, DAE_NUM=DAE, CONF_DATE=day, pIndex=page)
            sleep(PAUSE)
            if err:
                errors.append(f"{day[5:]}:{err}")
                break
            for x in rows:
                pid = pdf_id(x.get("PDF_LINK_URL"))
                if not pid or not watched(x.get("COMM_NAME")):
                    continue
                m = out.setdefault(pid, {"pid": pid, "kind": "위원회 회의록", "committee": tidy(x.get("COMM_NAME")), "meeting": tidy(x.get("TITLE")),
                                         "date": str(x.get("CONF_DATE") or day).replace("-", ""), "agenda": [], "url": PDF.format(pid)})
                sub = tidy(x.get("SUB_NAME"))
                if sub and sub not in m["agenda"] and len(m["agenda"]) < 6:
                    m["agenda"].append(sub)
            if page * 100 >= total or not rows:
                break
            page += 1
    rows, _total, err = call(get, key, AUDIT, ERACO=ERACO)
    if err:
        errors.append(f"국정감사:{err}")
    since = (now.date() - dt.timedelta(days=AUDIT_DAYS)).isoformat()
    for x in rows:
        pid = pdf_id(x.get("DOWN_URL"))
        if not pid or not watched(x.get("CMIT_NM")) or str(x.get("CONF_DT") or "") < since:
            continue
        out.setdefault(pid, {"pid": pid, "kind": "국정감사 회의록", "committee": tidy(x.get("CMIT_NM")),
                             "meeting": tidy(f"{x.get('ERACO') or ''} {x.get('SESS') or ''} 국정감사"), "date": str(x.get("CONF_DT") or "").replace("-", ""),
                             "agenda": [], "url": PDF.format(pid)})
    return sorted(out.values(), key=lambda m: (m["kind"] != "위원회 회의록", -int(m["date"] or 0))), errors   # 위원회 회의록 최신부터, 그다음 국정감사


def pdf_text(raw):
    """PDF → 글자(쪽 사이 \\f). pdfminer — pypdf는 이 회의록의 띄어쓰기를 잃는다(11-18 탐침)."""
    from pdfminer.high_level import extract_text
    return extract_text(io.BytesIO(raw))


def speaker_at(text, pos):
    k = text.rfind("◯", 0, pos)
    if k < 0:
        return None, -1, -1
    m = SPEAKER.match(text, k)
    return (tidy(m.group(1))[:24], k, m.end()) if m else (None, k, k + 1)


def name_spans(text, rx, cap=80):
    """회사 이름 자리 [(시작, 끝)] — 회의록 PDF는 줄 끝에서 낱말 가운데를 끊는다('포스코이\n앤씨', '현대제\n철', 11-18 첫 실행).
    그래서 줄바꿈을 붙인 글자에서도 찾고, 찾은 자리마다 줄바꿈을 붙인 글자에서 다시 맞춰 본다 —
    '포스코이\n앤씨'(계열사 포스코이앤씨)는 빠지고 '현대제\n철'은 잡힌다."""
    keep = [i for i, ch in enumerate(text) if ch != "\n"]
    flat = "".join(text[i] for i in keep)
    fidx, n = [], 0
    for ch in text:
        fidx.append(n)
        n += ch != "\n"
    starts = {m.start() for m in rx.finditer(text)} | {keep[m.start()] for m in rx.finditer(flat)}
    out, last = [], -1
    for st in sorted(starts):
        if st < last:
            continue
        f0 = fidx[st]
        mm = rx.match(flat[f0: f0 + 60])
        if not mm or not mm.end():
            continue
        last = keep[f0 + mm.end() - 1] + 1
        out.append((st, last))
        if len(out) >= cap:
            break
    return out


def hits(text, rx, n=SNIPS):
    """회사 이름 대목 n곳 [(대목, 사건 낱말 여부)] — 사건 낱말 있는 대목 먼저. 대목은 '쪽 · 발언자 · 글'."""
    near_a, plain = [], []
    for a, b in name_spans(text, rx):
        who, at, label_end = speaker_at(text, a)
        start = max(0, a - WIDTH)
        if at >= start:   # 앞 발언자의 말은 자르고 이 발언자 말부터
            start = label_end
        body = tidy(text[start: b + WIDTH])
        page = text.count("\f", 0, a) + 1
        s = f"{page}쪽 · {who or '발언자 미상'} · {body}"
        (near_a if A_WORDS.search(re.sub(r"\n", "", text[max(0, a - NEAR): b + NEAR])) else plain).append((s, body))
    out, keys = [], []
    for s, body in near_a + plain:
        key = re.sub(r"\s", "", body)[:50]
        if any(key in o or o in key for o in keys):
            continue
        keys.append(key)
        out.append(s)
        if len(out) >= n:
            break
    return out, bool(near_a)


def run(now, previous=None, *, key=None, get=None, sleep=time.sleep, extract=pdf_text):
    if get is None:
        import requests
        get = requests.get
    key = key if key is not None else os.environ.get("ASSEMBLY_API_KEY", "").strip()
    prev = previous if isinstance(previous, dict) and previous.get("schema") == SCHEMA else {}
    stamp = now.isoformat(timespec="seconds")
    if not key:
        return {**prev, "schema": SCHEMA, "generatedAt": stamp, "status": "not_configured",
                "checks": [{"source": "열린국회정보 회의록", "status": "unset", "error": "ASSEMBLY_API_KEY 미설정"}],
                "items": prev.get("items") or [], "events": prev.get("events") or []}
    seen = dict(prev.get("seen") or {})
    rebuild = prev.get("rulesV") != RULES_V
    if rebuild:   # 이름 찾기 규칙이 바뀌면 받은 회의록을 한 번 다시 읽는다(한 실행 30개씩)
        seen = {}
        prev = {**prev, "items": [], "events": []}
    tries = {k: v for k, v in (prev.get("tries") or {}).items() if isinstance(v, int)}
    known = {x["id"]: x for x in prev.get("items") or [] if isinstance(x, dict) and x.get("id")}
    # 이름 규칙을 고치면 앞서 남긴 대목도 지금 규칙으로 다시 본다(대목에 회사 이름이 안 맞으면 뺀다 — 11-18 HL만도)
    rx_of = {}
    for c, rx in TERMS:
        rx_of.setdefault(c, []).append(rx)
    known = {k: v for k, v in known.items() if any(rx.search(str(sn)) for rx in rx_of.get(v.get("company"), []) for sn in v.get("snippets") or [])}
    events = [e for e in prev.get("events") or [] if isinstance(e, dict) and (e.get("id") in known or not str(e.get("id", "")).startswith("nam:"))]
    found, errors = meetings(get, key, now, sleep)
    fresh = [m for m in found if m["pid"] not in seen]
    opened, read_ok = 0, 0
    recent = (now.date() - dt.timedelta(days=RECENT_DAYS)).strftime("%Y%m%d")
    waiting, left = 0, 0
    for m in fresh:
        if opened >= DETAIL_BUDGET:
            left += 1
            continue
        counted = False
        try:
            r = get(m["url"], headers=UA, timeout=120)
            raw = getattr(r, "content", b"") or b""
            if not raw.startswith(b"%PDF") and NOT_POSTED in raw[:600].decode("utf-8", "ignore"):
                # 11-18 첫 실행: 국정감사 회의록 12개가 '내려받을 원본 회의록 파일이 등록되지 않았습니다' 알림(HTML 135바이트) —
                # 목록에는 있지만 파일이 아직 안 올라온 것. 실패로 세지 않고(세 번 넘김 없음) 다음 실행에 다시 본다.
                waiting += 1
                tries.pop(m["pid"], None)
                sleep(PAUSE)
                continue
            opened, counted = opened + 1, True
            if not raw.startswith(b"%PDF"):
                raise ValueError(f"PDF 아님 HTTP {getattr(r, 'status_code', '?')}")
            text = extract(raw)
            if len(text or "") < 500:
                raise ValueError("글자 없음")
        except Exception as e:  # noqa: BLE001
            opened += 0 if counted else 1   # 받기 자체가 실패한 것도 한 개로 센다
            tries[m["pid"]] = tries.get(m["pid"], 0) + 1
            why = f"({str(e)[:24]})" if isinstance(e, ValueError) else ""
            errors.append(f"회의록 {m['pid']}:{type(e).__name__}{why}{'(3번째, 넘김)' if tries[m['pid']] >= 3 else ''}")
            if tries[m["pid"]] >= 3:
                seen[m["pid"]] = m["date"]
                tries.pop(m["pid"], None)
            sleep(PAUSE)
            continue
        sleep(PAUSE)
        read_ok += 1
        tries.pop(m["pid"], None)
        seen[m["pid"]] = m["date"]
        per = {}
        for comp, rx in TERMS:
            if comp in per:
                sn, near = hits(text, rx)
                if sn and not per[comp][0]:
                    per[comp] = (sn, near)
                continue
            per[comp] = hits(text, rx)
        old = m["date"] < recent
        for comp, (snips, near) in per.items():
            if not snips:
                continue
            tier = "A" if near and not old else "C"
            rid = f"nam:{m['pid']}:{comp}"
            rec = {"id": rid, "company": comp, "kind": m["kind"], "committee": m["committee"], "meeting": m["meeting"], "date": m["date"],
                   "agenda": " / ".join(m["agenda"])[:200], "snippets": [s[:420] for s in snips], "tier": tier, "pid": m["pid"], "url": m["url"],
                   "firstSeen": stamp, **({"old": True} if old and near else {})}
            known[rid] = rec
            if tier == "A":
                d = m["date"]
                events.append({"id": rid, "tier": "A", "kind": "국회 회의록", "company": comp, "committee": m["committee"], "detectedAt": stamp, "url": m["url"],
                               "text": (f"{m['committee']} {m['kind']}({d[:4]}-{d[4:6]}-{d[6:]}) · {comp} 대목 「{snips[0][:260]}」"
                                        + (f" · 안건 {rec['agenda'][:80]}" if rec["agenda"] else "")
                                        + " · 열린국회정보 회의록 PDF · 의원 질의는 주장 — 정부 답변·회사 확인")})
    pending = left
    keep = (now - dt.timedelta(days=KEEP_DAYS)).isoformat(timespec="seconds")
    api_failed = sum(1 for e in errors if not e.startswith("회의록 "))
    status = "failed" if api_failed >= LOOKBACK_DAYS else "partial" if errors else "complete"
    return {"schema": SCHEMA, "generatedAt": stamp, "status": status, "rulesV": RULES_V,
            "checks": [{"source": "열린국회정보 회의록(위원회·국정감사)", "status": "failed" if status == "failed" else "partial" if errors else "ok",
                        "meetings": len(found), "returned": len(fresh), "opened": opened, "read": read_ok, **({"pending": pending} if pending else {}),
                        **({"notPosted": waiting} if waiting else {}),
                        "committees": list(WATCH), **({"error": "; ".join(errors[:4]) + (f" 외 {len(errors) - 4}" if len(errors) > 4 else "")} if errors else {})}],
            "seen": dict(sorted(seen.items(), key=lambda kv: kv[1], reverse=True)[:3000]),
            **({"tries": tries} if tries else {}),
            "items": sorted((x for x in known.values() if str(x.get("firstSeen")) >= keep), key=lambda x: (str(x.get("date")), x.get("tier") == "A"), reverse=True)[:500],
            "events": sorted((e for e in events if str(e.get("detectedAt")) >= keep), key=lambda e: e["detectedAt"], reverse=True)[:200],
            "rules": ["열린국회정보 위원회 회의록(최근 21일 회의일)·국정감사 회의록 중 출입 업종 상임위(산자중기위·기후에너지환경노동위·국토위·재경위·정무위, 소위 포함)의 새 회의록 PDF에서 출입처 이름 대목(앞뒤 150자, 발언자·쪽).",
                      f"회사 이름 앞뒤 60자 안에 불법·과징금·고발·수사·담합·오염·사고·사망·산재·폐쇄·철수·매각·감산·가동 중단·구조조정·하청·리콜·결함·증설·이전 낱말이 있고 회의일이 {RECENT_DAYS}일 안이면 A, 아니면 C.",
                      "의원 질의는 주장 — 정부 답변·회사 확인. 회의록은 회의 며칠 뒤 공개(회의일과 공개일이 다르다). PDF 글자 뽑기에서 줄바꿈 자리 띄어쓰기가 틀릴 수 있다(대목에 '현대제 철'처럼 보임) — 회사 이름은 줄바꿈을 붙여 찾는다(포스코이앤씨 같은 계열사 거르기 포함).",
                      "조회 실패·PDF 받기 실패는 미확인(0건 아님). 원본 파일이 아직 안 올라온 회의록은 날마다 다시 본다(위원회 회의록은 회의일 21일, 국정감사는 75일 안). 한 실행 30개 — 넘으면 다음 실행."]}


def main():
    import private_store
    now = dt.datetime.now(KST).replace(microsecond=0)
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    previous = None
    if token:
        try:
            previous = private_store.get("assembly-minutes", token)
        except private_store.StoreError as e:
            print(f"::warning title=assembly-minutes-state::이전 상태 조회 실패({e}) — 처음부터")
        if private_store.late_scheduled_duplicate(previous, now):
            return
    doc = run(now, previous)
    c = doc["checks"][0]
    new = [e for e in doc.get("events") or [] if e["detectedAt"] == doc["generatedAt"]]
    print(f"::notice title=assembly-minutes::상태 {doc['status']} · 지켜보는 회의록 {c.get('meetings', 0)} · 새 {c.get('returned', 0)} · 읽음 {c.get('read', 0)}/{c.get('opened', 0)}"
          f" · 남음 {c.get('pending', 0)} · 이번 A {len(new)}")
    if not token:
        print("::warning title=assembly-minutes-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if doc["status"] == "failed":
        sys.exit("국회 회의록 조회 실패 — 이전 결과 유지(0 아님)")
    status = private_store.put("assembly-minutes", doc, token)
    print(f"::notice title=assembly-minutes-push::기자 전용 저장소 전송 HTTP {status}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
