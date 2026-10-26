"""국내 공식 원천 감시: 공장등록(한국산업단지공단 팩토리온)과 관보 입법예고(행정안전부).

- 공장등록(15087611, getFctryPrdctnService_v2): 출입처 회사명으로 등록 공장 목록을 받아, 이름 규칙(data/factory_watch.json)에 맞는
  공장만 남긴다(계열사 제외). 직전 확인 대비 새 공장·고용인원 변화·주생산품·업종·주소 변화와, 등록일이 최근 120일인 공장을 표시.
- 관보 입법예고(15109162, getApiPblancLgsltList): 최근 발행분에서 출입처 업종 낱말이 제목(또는 소관 부처 + 개정이유)에 있는 것만.
- 결과는 기자 전용 저장소(kr-official)로만. 공개 로그는 건수만. 조회 실패는 0건이 아니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = dt.timezone(dt.timedelta(hours=9))
SCHEMA = "kr_official/v1"
CONFIG = ROOT / "data" / "factory_watch.json"
FACTORY_API = "https://apis.data.go.kr/B550624/fctryRegistInfo/getFctryPrdctnService_v2"
GAZETTE_API = "https://apis.data.go.kr/1741000/ApiPblancLgsltService/getApiPblancLgsltList"
GAZETTE_SITE = "https://gwanbo.go.kr"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
ROWS = 100
MAX_PAGES = 5
RECENT_DAYS = 120
GAZETTE_DAYS = 7
GAZETTE_KEEP = 60
FACTORY_FIELDS = ("fctryManageNo", "cmpnyNm", "rnAdres", "rprsntvNm", "cvplChrgOrgnztNm", "allEmplyCo", "frstFctryRegistDe",
                  "indutyNm", "mainProductCn", "rprsntvIndutyCode", "irsttNm")
LEGAL = re.compile(r"\(주\)|㈜|주식회사|\(유\)|유한회사|\(합\)|\s+")

# 관보 입법예고: 팀별 낱말. 제목에 있으면 남기고, 개정이유에만 있으면 소관 부처가 출입처 관련일 때만 남긴다.
TEAMS = {
    "자동차": r"자동차|타이어|자율주행|운전자|도로교통|배출가스|연비|리콜|모빌리티|전기차|수소차",
    "철강·비철": r"철강|비철|금속|제련|아연|광업|광물|희토류|고철|탄소국경|배출권",
    "전력·에너지": r"전기사업|전력|송전|변전|전력망|에너지|신재생|재생에너지|원자력|원전|수소|석유|가스|해상풍력|태양광|전기공사|ESS",
    "화학": r"화학물질|화학제품|석유화학|플라스틱|화평법|화관법|폐기물|순환경제",
    "공통": r"통상협정|통상조약|통상교섭|무역|관세|공급망|산업안전|중대재해|하도급|외국인투자|조세특례|산업집적|산업단지|공장|첨단전략산업|소재·부품|소재부품",
}
BEAT_MINISTRIES = re.compile(r"산업통상|기후에너지환경부|환경부|국토교통부|고용노동부|기획재정부|재정경제부|관세청|공정거래위원회|"
                             r"원자력안전위원회|중소벤처기업부|산업부")


def call(url, params, *, get=None, sleep=time.sleep, timeout=40):
    if get is None:
        import requests
        get = requests.get
    try:
        r = get(url, params=params, headers=UA, timeout=timeout)
    except Exception as e:
        sleep(0.4)
        if timeout < 60 and type(e).__name__ in ("ReadTimeout", "ConnectTimeout", "ConnectionError"):
            sleep(5.0)
            return call(url, params, get=get, sleep=sleep, timeout=60)  # one slower retry
        return None, type(e).__name__
    sleep(0.4)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    return r.text, None


# ---------- 공장등록 ----------

def parse_factories(text):
    """getFctryPrdctnService_v2 answers XML even with type=json; both are handled."""
    text = text.strip()
    if text.startswith("{"):
        body = json.loads(text)
        resp = body.get("response", body)
        header, b = resp.get("header", {}), resp.get("body", {})
        items = (b.get("items") or {}).get("item") or []
        items = items if isinstance(items, list) else [items]
        return str(header.get("resultCode")), int(b.get("totalCount") or 0), [{k: str(x.get(k) or "").strip() for k in FACTORY_FIELDS} for x in items]
    root = ET.fromstring(text)
    code = (root.findtext(".//resultCode") or root.findtext(".//returnReasonCode") or "").strip()
    total = int((root.findtext(".//totalCount") or "0").strip() or 0)
    items = [{k: (it.findtext(k) or "").strip() for k in FACTORY_FIELDS} for it in root.iter("item")]
    return code, total, items


def norm(name):
    return LEGAL.sub("", name or "")


def ymd(s):
    d = re.sub(r"\D", "", s or "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) >= 8 else None


def emp(s):
    try:
        return int(re.sub(r"[^\d]", "", s or "") or 0) if re.search(r"\d", s or "") else None
    except ValueError:
        return None


def rule_sig(c):
    return "|".join([",".join(c["queries"]), c["accept"], c.get("industryAccept") or ""])


def factories(cfg, key, now, previous, *, get=None, sleep=time.sleep):
    prev = {x["id"]: x for x in (previous or {}).get("factories", []) if isinstance(x, dict) and x.get("id")}
    # A company is compared with the previous run only when its name rules are unchanged; otherwise this run is its new baseline.
    sigs = {c["company"]: rule_sig(c) for c in cfg["companies"]}
    prev_sigs = (previous or {}).get("ruleSigs") or {}
    comparable = {co for co, sig in sigs.items() if prev and prev_sigs.get(co) == sig}
    out, checks, events = {}, [], []
    stamp = now.isoformat(timespec="seconds")
    recent_from = (now.date() - dt.timedelta(days=RECENT_DAYS)).isoformat()
    complete_companies = set()
    rule_counts = {}
    for c in cfg["companies"]:
        accept = re.compile(c["accept"])
        # common names (e.g. 태광산업) are shared by unrelated small firms: an industry rule narrows them
        industry = re.compile(c["industryAccept"]) if c.get("industryAccept") else None
        kept = dropped = 0
        ok = True
        for q in c["queries"]:
            page, total, got = 1, None, 0
            while page <= MAX_PAGES:
                text, err = call(FACTORY_API, {"serviceKey": key, "pageNo": page, "numOfRows": ROWS, "type": "json", "cmpnyNm": q},
                                 get=get, sleep=sleep)
                if err:
                    checks.append({"source": f"공장등록 {q}", "company": c["company"], "status": "failed", "error": err})
                    ok = False
                    break
                try:
                    code, total, items = parse_factories(text)
                except (ET.ParseError, ValueError) as e:
                    checks.append({"source": f"공장등록 {q}", "company": c["company"], "status": "failed", "error": f"형식 오류 {type(e).__name__}"})
                    ok = False
                    break
                if code not in ("00", "0", "NORMAL_SERVICE"):
                    msg = re.search(r"<(?:resultMsg|returnAuthMsg)>([^<]+)", text)
                    checks.append({"source": f"공장등록 {q}", "company": c["company"], "status": "failed",
                                   "error": f"결과코드 {code or '?'} {msg.group(1) if msg else ''}".strip()})
                    ok = False
                    break
                for it in items:
                    got += 1
                    if not it["fctryManageNo"] or not accept.search(norm(it["cmpnyNm"])) or (
                            industry and not industry.search(f"{it['indutyNm']} {it['mainProductCn']}")):
                        dropped += 1
                        continue
                    kept += 1
                    fid = f"fac:{it['fctryManageNo']}"
                    out[fid] = {"id": fid, "company": c["company"], **it, **({"nameCheck": c["nameCheck"]} if c.get("nameCheck") else {}), "registeredOn": ymd(it["frstFctryRegistDe"]),
                                "employees": emp(it["allEmplyCo"]), "firstSeen": prev.get(fid, {}).get("firstSeen") or stamp}
                if got >= total or not items:
                    break
                page += 1
            else:
                checks.append({"source": f"공장등록 {q}", "company": c["company"], "status": "partial", "error": f"{MAX_PAGES}쪽 초과({total}건)"})
                ok = False
            if ok:
                checks.append({"source": f"공장등록 {q}", "company": c["company"], "status": "ok", "returned": got})
        if ok:
            complete_companies.add(c["company"])
        rule_counts[c["company"]] = {"kept": kept, "dropped": dropped}
    # changes against the previous private state
    for fid, f in out.items():
        old = prev.get(fid)
        tags = []
        if f.get("registeredOn") and f["registeredOn"] >= recent_from:
            tags.append(f"[최근 등록 {f['registeredOn']}]")
        if old is None:
            if f["company"] in comparable:
                tags.append("[새로 잡힌 공장]")
                events.append({"id": f"{fid}:new", "kind": "새 공장", "company": f["company"], "factoryId": fid, "name": f["cmpnyNm"],
                               "text": f"{f['cmpnyNm']} · {f['rnAdres']} · 주생산품 {f['mainProductCn'] or '미기재'} · 등록 {f.get('registeredOn') or '미기재'}",
                               "detectedAt": stamp})
        elif f["company"] in comparable:
            changes = []
            oe, ne = old.get("employees"), f.get("employees")
            if oe is not None and ne is not None and oe != ne and abs(ne - oe) >= max(20, round(oe * 0.1)):
                changes.append(f"고용 {oe:,}→{ne:,}명")
            for k, label in (("mainProductCn", "주생산품"), ("indutyNm", "업종"), ("rnAdres", "주소")):
                if (old.get(k) or "") != (f.get(k) or "") and old.get(k) is not None:
                    changes.append(f"{label} '{old.get(k) or '-'}'→'{f.get(k) or '-'}'")
            if changes:
                tags.append("[변경] " + " · ".join(changes))
                events.append({"id": f"{fid}:{stamp[:10]}", "kind": "등록 내용 변경", "company": f["company"], "factoryId": fid,
                               "name": f["cmpnyNm"], "text": " · ".join(changes), "detectedAt": stamp})
        f["tags"] = tags
    # factories that disappeared from a company whose queries all completed
    for fid, old in prev.items():
        if fid not in out and old.get("company") in complete_companies and old.get("company") in comparable:
            events.append({"id": f"{fid}:gone:{stamp[:10]}", "kind": "목록에서 빠짐", "company": old.get("company"), "factoryId": fid,
                           "name": old.get("cmpnyNm"), "text": f"{old.get('cmpnyNm')} · {old.get('rnAdres')} — 이번 조회 목록에 없음(폐업·이전·이름 변경 가능, 확인 필요)",
                           "detectedAt": stamp})
        elif fid not in out and old.get("company") not in complete_companies:
            out[fid] = dict(old, stale=True)  # query failed: keep the last record
    return sorted(out.values(), key=lambda x: (x["company"], x.get("cmpnyNm") or "")), checks, events, sigs, rule_counts


# ---------- 관보 입법예고 ----------

ORG_PREFIX = re.compile(r"^[^()（]*?공고\s*제\s*\d{4}\s*-\s*\d+\s*호\s*[(（]")


def subject_of(title):
    """'산업통상부공고제2026-656호(「…」 입법예고)' → the part in brackets, so the issuing body's own name
    (산업통상부, 원자력안전위원회) does not match beat words like 통상·원자력."""
    t = ORG_PREFIX.sub("", title or "", count=1)
    return t[:-1] if t != title and t.endswith((")", "）")) else t


def teams_of(text):
    return [t for t, rx in TEAMS.items() if re.search(rx, text or "")]


def gazette(key, now, previous, *, get=None, sleep=time.sleep):
    prev = {x["id"]: x for x in (previous or {}).get("gazette", []) if isinstance(x, dict) and x.get("id")}
    had_state = bool(prev) or bool(previous)
    to = now.date()
    fr = to - dt.timedelta(days=GAZETTE_DAYS)
    rows, page, total, err = [], 1, None, None
    while page <= MAX_PAGES:
        text, err = call(GAZETTE_API, {"serviceKey": key, "pageNo": page, "pageSize": ROWS, "type": 1,
                                       "reqFrom": fr.strftime("%Y%m%d"), "reqTo": to.strftime("%Y%m%d")}, get=get, sleep=sleep)
        if err:
            break
        try:
            resp = json.loads(text).get("response", {})
        except ValueError:
            err = "JSON 아님"
            break
        if str(resp.get("resultCode")) not in ("0", "00"):
            err = f"결과코드 {resp.get('resultCode')} {resp.get('resultMsg') or ''}".strip()
            break
        items = (resp.get("items") or {}).get("item") or []
        items = items if isinstance(items, list) else [items]
        rows += items
        total = int(resp.get("totalCount") or 0)
        if len(rows) >= total or not items:
            break
        page += 1
    kept = {}
    for x in rows:
        title = str(x.get("cntntSj") or "")
        org = str(x.get("pblcnInstNm") or "")
        reason = re.sub(r"\s+", " ", str(x.get("rvsnRsnMainCn") or "")).strip()
        in_title = teams_of(subject_of(title))
        in_reason = teams_of(reason) if BEAT_MINISTRIES.search(org) else []
        teams = sorted(set(in_title) | set(in_reason))
        if not teams:
            continue
        gid = f"gz:{x.get('cntntSeqNo')}"
        laws = re.findall(r"「([^」]+)」", title)
        kept[gid] = {"id": gid, "date": str(x.get("hopePblictDt") or "").replace(". ", "-").replace(".", "-").strip("-"),
                     "title": title, "org": org, "laws": laws[:3], "basis": x.get("basisLawNm"), "corrected": x.get("crtnYn") == "예",
                     "teams": teams, "matchedIn": "제목" if in_title else "개정이유(소관 부처)", "summary": reason[:500],
                     "url": GAZETTE_SITE + str(x.get("pdfFilePath") or "") if x.get("pdfFilePath") else None,
                     "firstSeen": prev.get(gid, {}).get("firstSeen") or now.isoformat(timespec="seconds"),
                     "isNew": had_state and gid not in prev}
    keep_from = (now.date() - dt.timedelta(days=GAZETTE_KEEP)).isoformat()
    for gid, old in prev.items():
        if gid in kept or str(old.get("date") or "") < keep_from:
            continue
        # re-check kept notices with the current rules (earlier runs matched issuer names such as 산업통상부)
        teams = sorted(set(teams_of(subject_of(old.get("title")))) |
                       set(teams_of(old.get("summary")) if BEAT_MINISTRIES.search(old.get("org") or "") else []))
        if teams:
            kept[gid] = dict(old, teams=teams, isNew=False)
    check = {"source": "관보 입법예고", "status": "failed" if err else "ok", "returned": len(rows), "kept": len(kept),
             **({"error": err} if err else {})}
    return sorted(kept.values(), key=lambda g: (g["date"], g["id"]), reverse=True), check


def run(cfg, key, *, now, previous=None, get=None, sleep=time.sleep):
    stamp = now.isoformat(timespec="seconds")
    facs, checks, fac_events, sigs, rule_counts = factories(cfg, key, now, previous, get=get, sleep=sleep)
    gz, gcheck = gazette(key, now, previous, get=get, sleep=sleep)
    checks.append(gcheck)
    keep_from = (now - dt.timedelta(days=120)).isoformat()
    events = [e for e in (previous or {}).get("events", []) if isinstance(e, dict) and e.get("detectedAt", "") >= keep_from]
    seen = {e.get("id") for e in events}
    events += [e for e in fac_events if e["id"] not in seen]
    events.sort(key=lambda e: e["detectedAt"], reverse=True)
    failed = [c for c in checks if c["status"] != "ok"]
    return {"schema": SCHEMA, "generatedAt": stamp, "status": "partial" if failed else "complete", "checks": checks,
            "baselineSince": (previous or {}).get("baselineSince") or ((previous or {}).get("generatedAt") if previous else None) or stamp,
            "factories": facs, "ruleSigs": sigs, "ruleCounts": rule_counts, "gazette": gz, "events": events[:400],
            "rules": ["공장등록 정보는 지자체 등록 기준이다. 등록일·고용인원은 신고값이라 실제 가동·채용과 다를 수 있다.",
                      "회사명 검색은 이름 규칙으로 계열사를 거른다. 이름이 비슷한 다른 회사가 섞일 수 있으니 주소·대표자로 확인한다.",
                      "'목록에서 빠짐'은 폐업·이전·이름 변경·등록 정정일 수 있다. 지자체·회사 확인 전 폐쇄로 쓰지 않는다.",
                      "관보 입법예고는 공개 공고다. 보도자료와 같은 날 나오는 경우가 많으니 단독 근거로 쓰지 않는다.",
                      "조회 실패는 0건이 아니라 미확인."],
            "confirmedScoops": 0}


def main():
    argparse.ArgumentParser(description="공장등록·관보 입법예고 감시(기자 전용 저장소로)").parse_args()
    now = dt.datetime.now(KST)
    key = (os.environ.get("DATA_GO_KR_KEY") or os.environ.get("CUSTOMS_API_KEY") or "").strip()
    token = os.environ.get("MCP_ACCESS_TOKEN", "").strip()
    if not key:
        sys.exit("공공데이터포털 키 미설정 — 실행하지 않음(0건 아님)")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    import private_store
    previous = None
    if token:
        try:
            previous = private_store.get("kr-official", token)
        except private_store.StoreError as e:
            print(f"::warning title=kr-official-state::이전 상태 조회 실패({e}) — 변경 비교는 다음 실행부터")
    doc = run(cfg, key, now=now, previous=previous)
    fac_checks = [c for c in doc["checks"] if c["source"].startswith("공장등록 ")]
    ok = sum(1 for c in fac_checks if c["status"] == "ok")
    recent = sum(1 for f in doc["factories"] if any(t.startswith("[최근 등록") for t in f.get("tags", [])))
    new_ev = sum(1 for e in doc["events"] if e["detectedAt"] == doc["generatedAt"])
    rules = " ".join(f"{co}={v['kept']}/{v['kept'] + v['dropped']}" for co, v in doc["ruleCounts"].items())
    errors = sorted({c.get("error") for c in doc["checks"] if c.get("error")})
    g = next(c for c in doc["checks"] if c["source"] == "관보 입법예고")
    print(f"::notice title=kr-official::공장등록 질의 {ok}/{len(fac_checks)} · 출입처 공장 {len(doc['factories'])}곳(최근 등록 {recent}) · "
          f"이번 변경 이벤트 {new_ev} · 관보 입법예고 {g['status']} {g.get('returned', 0)}건 중 관련 {g.get('kept', 0)}건"
          f"{' · 오류 ' + ', '.join(errors)[:300] if errors else ''}")
    print(f"::notice title=kr-official-rules::회사별 채택/조회 {rules}")
    if not token:
        print("::warning title=kr-official-push::MCP_ACCESS_TOKEN 미설정 — 결과를 저장하지 않음")
        return
    if ok == 0 and g["status"] != "ok":
        sys.exit("모든 질의 실패 — 이전 결과 유지(0건 아님)")
    status = private_store.put("kr-official", doc, token)
    print(f"::notice title=kr-official-push::기자 전용 저장소 전송 HTTP {status}")
    if status == 404:
        print(f"::warning title=kr-official-token::토큰 거부 또는 배포 전 — {private_store.token_shape(private_store.normalize_token(token))}")
    if status != 200:
        sys.exit(1)


if __name__ == "__main__":
    main()
