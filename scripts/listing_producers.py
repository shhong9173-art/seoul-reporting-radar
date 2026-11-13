"""해외 무역구제 목록 새 줄(한국산) → 그 품목 낱말이 나온 출입처 사업보고서 'II. 사업의 내용'(11-14).

인도 DGTR·캐나다·인도네시아 등 해외 조사 목록은 영문 품목 이름만 준다('Acetone', 'Toluene Di-isocyanate'). 한국 수출자 이름은 목록에 없다.
단독 데스크는 이 줄에 '그 품목을 만드는 출입처가 있는지부터'라고만 적었다(11-13). 여기서는
① 영문 품목 이름을 사업보고서가 쓰는 한글·약어로 옮기고(아래 용어 표 — 번역일 뿐 '누가 만든다'는 주장이 아니다)
② 그 낱말이 출입처 최근 사업보고서 'II. 사업의 내용'에 나오는 회사를 원문 문맥과 함께 붙인다(ktc_producers.py와 같은 원문·같은 한도).

지킬 것
- 보고서에 낱말이 있다 = 그 회사가 그 품목(또는 같은 낱말을 쓰는 다른 품목)을 다룬다는 원문 단서일 뿐이다. 조사 대상 수출자인지,
  그 나라로 수출하는지는 미확인 — 회사 확인.
- 낱말이 없다 = 보고서에 안 적었을 수 있다(안 만든다는 뜻 아님) → 줄을 붙이지 않는다. 용어 표에 없는 품목도 붙이지 않는다.
- 약어(TDI·PVC·SBR…)는 앞뒤가 영문자가 아닐 때만 센다('SSBR' 속 'SBR'은 다른 품목).
- 사업보고서는 회사마다 한 해에 한 번만 받는다: 받은 보고서에서 용어 표의 낱말을 모두 세어 '낱말 색인'(producerIndex)으로 저장하고,
  목록 줄은 그 색인으로만 대조한다(DART를 다시 부르지 않는다). 색인 만들기는 한 실행에 TIME_BUDGET초까지 — 남은 회사는 다음 실행.
  색인 만들기(fetch=True)는 무역구제 결과를 저장한 **뒤에** 돌린다(trade_remedy_watch.main) — 보고서 받기가 느려도 본 결과 저장을 막지 않는다.
  (11-14 첫 운영: 줄마다 보고서를 받게 짰더니 19곳을 한 실행에 받느라 평소 2분인 무역구제 감시가 길어졌다 — 20분 상한을 넘기면 그 실행의
  무역구제 결과 전체가 저장되지 않는다.)
- 결과는 기자 전용 저장소(trade-remedy)의 listingProducers·producerIndex에만. 공개 로그엔 건수만.
"""
from __future__ import annotations

import re
import time
from datetime import timedelta

import ktc_producers as kp

EV_VERSION = 3
INDEX_VERSION = 3      # 낱말 세는 규칙이 바뀌면 올린다 — 예전 규칙으로 만든 색인은 버리고 보고서를 다시 받는다
TIME_BUDGET = 540      # 한 실행에 보고서를 받는 데 쓰는 시간(초). 넘으면 남은 회사는 다음 실행. 11-14 운영: 보고서 한 곳에 50초쯤(8곳 6분 반)
FETCH_TRIES = 3        # 보고서를 못 받은 회사는 이 횟수까지 다시(그 뒤로는 7일에 한 번)
WINDOW_DAYS = 45
KEEP_DAYS = 120
SNIPPET = 36
SKIP_PAGES = {"ktc", "kita", "edis", "trafile", "taric"}   # 국내 무역위(ktc_producers가 봄)·수입규제DB·EDIS·영국 공개기록(당사자 이름이 직접 나옴)·EU 쿼터
# 사업보고서 목록(digests/business_content_latest.json)의 회사 이름 → 출입처 표기
SHOW = {"엘에스일렉트릭": "LS일렉트릭", "현대자동차": "현대차", "한국타이어앤테크놀로지": "한국타이어", "S-Oil": "S-OIL"}
GROUPS = {**kp.GROUPS, "전력기기": ("HD현대일렉트릭", "엘에스일렉트릭"), "전선": ("대한전선",), "타이어": ("한국타이어앤테크놀로지", "금호타이어")}

# (표시 이름, 영문 품목 규칙(대소문자 무시), 영문 약어(대문자 그대로일 때만 — 'pet food'·'goes'를 세지 않는다), 사업보고서에서 찾을 낱말, 묶음).
# 찾을 낱말은 그 품목을 가리키는 것만 — 흔한 말('수지'·'강판'·'아연')은 넣지 않는다.
GLOSSARY = [
    ("아세톤", r"\bacetone\b", (), ["아세톤"], "화학"),
    ("페놀", r"(?<![a-z])phenol\b", (), ["페놀"], "화학"),
    ("비스페놀A", r"bisphenol[\s-]*a\b", ("BPA",), ["비스페놀", "BPA"], "화학"),
    ("TDI", r"toluene\s+di-?\s?isocyanate", ("TDI",), ["TDI", "톨루엔디이소시아네이트"], "화학"),
    ("MDI", r"methylene\s+di-?\s?phenyl\s+di-?\s?isocyanate", ("MDI",), ["MDI"], "화학"),
    # CPVC(염소화 PVC)는 PVC와 다른 품목이다 — 11-14 운영: 인도 DGTR 'Chlorinated Polyvinyl Chloride (CPVC)' 줄에 PVC 낱말로 세 회사가 붙었다
    ("PVC", r"(?<!chlorinated )poly\s?vinyl\s+chloride", ("PVC", "S-PVC"), ["PVC", "폴리염화비닐"], "화학"),
    ("CPVC", r"chlorinated\s+poly\s?vinyl\s+chloride", ("CPVC",), ["CPVC", "염소화 PVC", "염소화PVC"], "화학"),
    ("가성소다", r"caustic\s+soda|sodium\s+hydroxide", (), ["가성소다", "수산화나트륨"], "화학"),
    ("ECH", r"epichlorohydrin", (), ["에피클로로히드린", "ECH"], "화학"),
    ("에폭시 수지", r"epoxy\s+resin", (), ["에폭시"], "화학"),
    ("SBR", r"styrene[\s-]+butadiene\s+rubber", ("SBR",), ["SBR", "스티렌부타디엔"], "화학"),
    ("NBR", r"nitrile[\s-]+butadiene|acrylonitrile[\s-]+butadiene\s+rubber", ("NBR",), ["NBR"], "화학"),
    ("부타디엔고무", r"poly\s?butadiene\s+rubber|(?<!styrene[\s-])(?<!nitrile[\s-])butadiene\s+rubber", ("PBR",), ["부타디엔고무", "PBR"], "화학"),
    ("ABS", r"acrylonitrile[\s-]+butadiene[\s-]+styrene", ("ABS",), ["ABS"], "화학"),
    ("폴리카보네이트", r"polycarbonate", (), ["폴리카보네이트"], "화학"),
    ("PET", r"polyethylene\s+terephthalate", ("PET",), ["PET", "폴리에틸렌테레프탈레이트"], "화학"),
    ("PTA", r"purified\s+terephthalic\s+acid", ("PTA",), ["PTA", "테레프탈산"], "화학"),
    ("MEG", r"mono\s?-?ethylene\s+glycol", ("MEG",), ["MEG", "에틸렌글리콜"], "화학"),
    ("파라자일렌", r"para-?\s?xylene", (), ["파라자일렌"], "화학"),
    ("스티렌모노머", r"styrene\s+monomer", (), ["스티렌모노머", "스티렌 모노머"], "화학"),
    ("폴리에틸렌", r"polyethylene(?!\s+terephthalate)", ("LLDPE", "LDPE", "HDPE"), ["폴리에틸렌", "LLDPE", "LDPE", "HDPE"], "화학"),
    ("폴리프로필렌", r"polypropylene", (), ["폴리프로필렌"], "화학"),
    ("EVA", r"ethylene[\s-]+vinyl\s+acetate", ("EVA",), ["EVA"], "화학"),
    ("가소제", r"plastici[sz]er|dioctyl", ("DOTP", "DOP"), ["가소제", "DOTP", "DOP"], "화학"),
    ("옥탄올(2-EH)", r"2-?\s?ethyl\s?hexanol|\boctanol\b", ("2-EH", "2EH"), ["옥탄올", "2-EH", "에틸헥산올"], "화학"),
    ("2-EHA", r"2-?\s?ethyl\s?hexyl\s+acrylate", ("2-EHA", "2EHA"), ["2-EHA", "에틸헥실"], "화학"),
    ("부탄올", r"\bn-?\s?butanol\b|normal\s+butanol|butyl\s+alcohol", (), ["부탄올"], "화학"),
    ("IPA", r"isopropyl\s+alcohol|isopropanol", ("IPA",), ["IPA", "이소프로필알코올", "이소프로필알콜"], "화학"),
    ("아크릴로니트릴", r"acrylonitrile(?![\s-]+butadiene)", (), ["아크릴로니트릴"], "화학"),
    ("고흡수성수지(SAP)", r"super\s?-?absorbent\s+polymer", ("SAP",), ["SAP", "고흡수성수지", "고흡수성 수지"], "화학"),
    ("카본블랙", r"carbon\s+black", (), ["카본블랙"], "화학"),
    ("폴리실리콘", r"polysilicon", (), ["폴리실리콘"], "화학"),
    ("흄드실리카", r"fumed\s+silica", (), ["흄드실리카", "흄드 실리카"], "화학"),
    ("과산화수소", r"hydrogen\s+peroxide", (), ["과산화수소"], "화학"),
    ("라텍스", r"\blatex\b", (), ["라텍스"], "화학"),
    ("태양전지·모듈", r"solar\s+(?:cells?|modules?|panels?)|photovoltaic", (), ["태양전지", "태양광 모듈"], "화학"),
    ("윤활기유", r"\bbase\s+oils?\b", (), ["윤활기유"], "화학"),
    ("열연", r"hot[\s-]+rolled", (), ["열연"], "철강"),
    ("냉연", r"cold[\s-]+rolled", (), ["냉연"], "철강"),
    ("후판", r"\bquarto\b|cut[\s-]+to[\s-]+length|(?:steel|carbon|alloy)[\w\s,-]{0,30}\bplates?\b", (), ["후판"], "철강"),
    ("도금·컬러강판", r"galvani[sz]ed|galvalume|(?:zinc|alumin(?:i)?um)[\s-]+(?:and[\s-]+zinc[\s-]+)?coated|colou?r[\s-]+coated|pre-?painted", (), ["도금강판", "컬러강판", "아연도금"], "철강"),
    ("석도강판", r"tin\s?plate|tin[\s-]+mill", (), ["석도"], "철강"),
    ("전기강판", r"electrical\s+steel|grain[\s-]+oriented", ("CRGO", "CRNO", "GOES"), ["전기강판"], "철강"),
    ("스테인리스", r"stainless", (), ["스테인리스"], "철강"),
    ("강관", r"line\s+pipes?|(?:welded|seamless|steel)\s+(?:pipes?|tubes?)", ("OCTG",), ["강관"], "철강"),
    ("선재", r"wire\s+rods?", (), ["선재"], "철강"),
    ("철근", r"\brebars?\b|reinforcing\s+bars?", (), ["철근"], "철강"),
    ("형강", r"h[\s-]?beams?|steel\s+sections?|structural\s+steel", (), ["형강"], "철강"),
    ("아연괴", r"\bzinc\b(?![\s-]+(?:and\b|coated))", (), ["아연괴"], "철강"),
    ("변압기", r"transformers?", (), ["변압기"], "전력기기"),
    ("전력 케이블", r"(?:power|electric|submarine|high[\s-]+voltage)[\w\s-]{0,20}cables?", (), ["케이블"], "전선"),
    ("타이어", r"\bty(?:re|er)s?\b|\btires?\b", (), ["타이어"], "타이어"),
]
_GLOSS = [(label, re.compile(rx, re.I), [re.compile(rf"(?<![A-Za-z0-9]){re.escape(a)}(?![A-Za-z0-9])") for a in abbr], terms, group)
          for label, rx, abbr, terms, group in GLOSSARY]


def products_in(text):
    """영문 목록 줄 → 용어 표에 맞은 품목 [(표시 이름, 찾을 낱말들, 묶음)]. 한국 관련 줄인지는 수집기(korea_lines)가 이미 걸렀다."""
    t = str(text or "")
    out = []
    for label, rx, abbr, terms, group in _GLOSS:
        if rx.search(t) or any(a.search(t) for a in abbr):
            out.append((label, terms, group))
    return out[:3]


# 한글 낱말 뒤에 이 말이 이어지면 다른 품목이다: 폴리에틸렌테레프탈레이트(PET)·폴리프로필렌글리콜(PPG)·아크릴로니트릴부타디엔스티렌(ABS)
NOT_FOLLOWED = {"폴리에틸렌": r"\s?테레프탈", "폴리프로필렌": r"\s?글리콜", "아크릴로니트릴": r"[\s·-]?부타디엔"}


def term_rx(term):
    """약어·영문 낱말은 앞뒤가 영문자·숫자가 아닐 때만('SSBR' 속 'SBR'을 세지 않는다).
    한글 낱말은 바로 앞이 한글이 아닐 때만 — 11-14 첫 운영에서 '페놀'이 롯데케미칼 보고서의 '비스페놀A'에 걸려 다른 품목을 가리켰다
    ('분석도구' 속 '석도', '메타아크릴산'·'디에틸렌글리콜' 같은 앞가지 붙은 다른 품목도 같은 이유로 뺀다). 붙여 쓴 같은 품목('저밀도폴리에틸렌')은
    놓칠 수 있다 — 틀린 회사를 가리키는 것보다 빠지는 쪽을 택한다."""
    if re.fullmatch(r"[A-Za-z0-9-]+", term):
        return re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])")
    tail = f"(?!{NOT_FOLLOWED[term]})" if term in NOT_FOLLOWED else ""
    return re.compile(rf"(?<![가-힣]){re.escape(term)}{tail}")


def find(text, terms):
    """(나온 횟수, 문맥 한 줄). 여러 낱말 가운데 가장 많이 나온 낱말의 첫 문맥."""
    best = (0, "", "")
    for term in terms:
        ms = list(term_rx(term).finditer(text))
        if len(ms) > best[0]:
            m = ms[0]
            seg = re.sub(r"\s+", " ", text[max(0, m.start() - SNIPPET):min(len(text), m.end() + SNIPPET)]).strip()
            best = (len(ms), seg, term)
    return best


def fetch_section(name, key, year, codes, *, list_fetch=None, doc_fetch=None, plain=None):
    """회사 최근 사업보고서 'II. 사업의 내용' 글을 받는다. {'status', 'receiptNo'?, 'text'?}"""
    import business_content as bc
    code = codes.get(name)
    if not code:
        return {"status": "no_code"}
    try:
        rec = bc.annual_receipt(key, code, year, fetch=list_fetch or bc.api_json)
        if not rec.get("receiptNo"):
            return {"status": rec.get("status") or "no_report"}
        rep = bc.fetch_report(key, rec["receiptNo"], fetch=doc_fetch or bc.api_bytes)
        return {"status": rep["status"], "receiptNo": rec["receiptNo"], "text": (plain or bc.plain)(rep["section"]) if rep.get("section") else ""}
    except Exception as e:  # noqa: BLE001 — 한 회사 실패가 다른 회사를 막지 않는다(미확인으로 남김)
        return {"status": "error", "error": type(e).__name__}


def index_text(text):
    """보고서 글에서 용어 표의 낱말을 모두 센다 → {낱말: [횟수, 첫 문맥]} (나온 낱말만)."""
    out = {}
    for _, _, _, terms, _ in GLOSSARY:
        for term in terms:
            if term in out:
                continue
            ms = list(term_rx(term).finditer(text))
            if ms:
                m = ms[0]
                out[term] = [len(ms), re.sub(r"\s+", " ", text[max(0, m.start() - SNIPPET):min(len(text), m.end() + SNIPPET)]).strip()]
    return out


def build_index(previous_index, needed, key, now, *, clock=time.monotonic, fetch=True, **kw):
    """회사별 낱말 색인. 올해 볼 보고서 연도의 색인이 이미 있으면 그대로 쓰고, 없는 회사만 TIME_BUDGET 안에서 받는다.
    돌려줌: (색인, 이번에 받은 보고서 수)."""
    year = kp.report_year(now)
    stamp = now.isoformat(timespec="seconds")
    idx = {k: v for k, v in (previous_index or {}).items() if isinstance(v, dict) and v.get("year") == year and v.get("iv") == INDEX_VERSION}
    if not key or not fetch:
        return idx, 0
    codes, start, fetched = kp.corp_codes(), clock(), 0
    for name in needed:
        cur = idx.get(name)
        if cur and cur.get("status") in ("found", "section_not_found", "no_annual_report", "no_matching_report", "not_due"):
            continue                                   # 받았거나, 받을 보고서가 없다는 답을 받았다
        if cur and (cur.get("tries") or 0) >= FETCH_TRIES and str(cur.get("checkedAt") or "") >= (now - timedelta(days=7)).isoformat():
            continue                                   # 여러 번 실패한 회사는 7일 뒤에 다시
        if clock() - start > TIME_BUDGET:
            break                                      # 남은 회사는 다음 실행(색인에 없으면 '대기')
        got = fetch_section(name, key, year, codes, **kw)
        row = {"year": year, "iv": INDEX_VERSION, "status": got["status"], "checkedAt": stamp}
        if got["status"] == "found":
            row.update(receiptNo=got["receiptNo"], terms=index_text(got["text"]))
            fetched += 1
        else:
            row.update(tries=((cur or {}).get("tries") or 0) + 1, **({"error": got["error"]} if got.get("error") else {}),
                       **({"receiptNo": got["receiptNo"]} if got.get("receiptNo") else {}))
        idx[name] = row
    return idx, fetched


def event_evidence(event, idx, now):
    out = {"v": EV_VERSION, "eventId": event["id"], "year": kp.report_year(now), "checkedAt": now.isoformat(timespec="seconds"), "products": []}
    for label, terms, group in products_in(event.get("text")):
        rows = []
        for name in GROUPS.get(group, ()):
            got = idx.get(name)
            row = {"company": SHOW.get(name, name)}
            if not got:
                rows.append({**row, "status": "pending"})          # 아직 보고서를 못 받음(다음 실행)
                continue
            if got.get("status") != "found":
                rows.append({**row, "status": got.get("status") or "error"})
                continue
            best = max(((got["terms"][t][0], got["terms"][t][1], t) for t in terms if t in got.get("terms", {})), default=None)
            rows.append({**row, "status": "found" if best else "none", "receiptNo": got["receiptNo"],
                         **({"hits": best[0], "snippet": best[1], "term": best[2]} if best else {})})
        out["products"].append({"label": label, "group": group, "companies": rows})
    out["line"] = line(out)
    return out


def line(ev):
    """오늘의 레이더 한 줄. 낱말이 어느 보고서에도 없으면 ''(없다는 게 안 만든다는 뜻이 아니어서 줄을 붙이지 않는다)."""
    parts = []
    for p in (ev or {}).get("products") or []:
        found = sorted((c for c in p["companies"] if c.get("status") == "found"), key=lambda c: -c["hits"])
        if not found:
            continue
        bad = sum(1 for c in p["companies"] if c.get("status") not in ("found", "none"))
        shown = [f"{c['company']} {c['hits']}곳 「{c['snippet']}」(접수 {c['receiptNo']})" for c in found[:3]]
        more = [f"외 {len(found) - 3}곳({'·'.join(c['company'] for c in found[3:])})"] if len(found) > 3 else []
        parts.append(f"{p['label']} — " + " · ".join(shown + more + ([f"미확인 {bad}곳"] if bad else [])))
    if not parts:
        return ""
    return (f"품목 낱말이 나온 출입처 {ev.get('year')} 사업보고서(II. 사업의 내용): " + " / ".join(parts)
            + " — 보고서에 낱말이 있다는 것뿐, 조사 대상 수출자인지·그 나라 수출 여부는 미확인(회사 확인)")


def attach(doc, previous, key, now, **kw):
    """doc['listingProducers'][줄 id]와 doc['producerIndex'][회사]. 최근 WINDOW_DAYS일 해외 조사 목록 줄 가운데 용어 표에 맞는 줄을
    회사별 낱말 색인으로 대조한다(줄 대조는 DART를 부르지 않는다 — 실행마다 다시 계산). 반환: (대조한 줄 수, 이번에 받은 보고서 수).
    fetch=False면 저장된 색인으로만 대조하고 보고서를 받지 않는다(본 결과를 저장하기 전 단계)."""
    old = (previous or {}).get("listingProducers") or {}
    keep_from = (now - timedelta(days=KEEP_DAYS)).isoformat()
    store = {k: v for k, v in old.items() if isinstance(v, dict) and str(v.get("checkedAt") or "") >= keep_from}
    since = (now - timedelta(days=WINDOW_DAYS)).isoformat()
    events = [e for e in doc.get("events") or [] if e.get("pageId") not in SKIP_PAGES and not e.get("renumbered")
              and str(e.get("detectedAt") or "") >= since and products_in(e.get("text"))]
    needed = []
    for e in sorted(events, key=lambda e: str(e.get("detectedAt")), reverse=True):      # 새 줄의 품목 묶음부터 받는다
        for _, _, group in products_in(e.get("text")):
            for name in GROUPS.get(group, ()):
                if name not in needed:
                    needed.append(name)
    idx, fetched = build_index((previous or {}).get("producerIndex"), needed, key, now, **kw)
    doc["producerIndex"] = idx
    if key or idx:
        for e in events:
            store[e["id"]] = event_evidence(e, idx, now)
    doc["listingProducers"] = store
    return len(events) if (key or idx) else 0, fetched
