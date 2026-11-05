"""공식 제재 기록 — 금융감독원 제재내용공개(기관·임원 조치)와 개인정보보호위원회 '결과의 공표'(개인정보보호법 제66조).

문제 임원 점검(kr_exec_check.py)이 임원 경력 칸의 회사(대표·사장 등 최고 경영 자리)와 이어 본다(11-05 기자 승인 — 선배 매의눈 롯데카드 사례:
'해킹 사고 당시 대표가 지금 다른 회사 이사'). 기사가 아니라 공식 처분 기록이라 오탐이 적다. 다만 공개안에는 개인 이름이 없다(임원 ○명) —
그 사람이 제재를 받았는지는 확인 대상이고, 여기서는 '그 사람이 그 회사 최고 경영 자리에 있던 기간에 그 회사가 받은 공식 제재'까지만 잇는다.

탐침 178~181(11-05)
- 금감원: https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476&sdate=YYYY-MM-DD&edate=…&pageIndex=N — 한 쪽 10줄
  (번호 | 제재대상기관 | 제재조치요구일 YYYYMMDD | 내용보기(view.do?…examMgmtNo=…&emOpenSeq=…) | 관련부서 | 조회수). 2020-01-01 이후 2,320건(232쪽).
  상세의 '제재내용 공개안' PDF(/fss.hpdownload?path=/dtm/opn/&file=….pdf): '1. 금융기관명 : … 2. 제재조치일 : … 3. 제재조치내용 기 관 … 임 원 … 직 원 등 … 4. 제재대상사실'.
- 개인정보위: 결과의 공표 게시판(BS258) — 제목은 모두 '개인정보보호법 제66조에 따른 결과의 공표', 회사 이름은 첨부에만.
"""
from __future__ import annotations

import datetime as dt
import io
import re
from urllib.parse import urljoin

FSS_LIST = "https://www.fss.or.kr/fss/job/openInfo/list.do?menuNo=200476"
FSS_SINCE = "2016-01-01"
UA = {"User-Agent": "Mozilla/5.0 (compatible; ReporterRadar/1.0; public sanction records)", "Accept-Language": "ko-KR,ko;q=0.9"}
LATIN = {"A": "에이", "B": "비", "C": "씨", "D": "디", "E": "이", "F": "에프", "G": "지", "H": "에이치", "I": "아이", "J": "제이", "K": "케이",
         "L": "엘", "M": "엠", "N": "엔", "O": "오", "P": "피", "Q": "큐", "R": "알", "S": "에스", "T": "티", "U": "유", "V": "브이",
         "W": "더블유", "X": "엑스", "Y": "와이", "Z": "지"}


def pdf_text(raw, pages=4):
    from pypdf import PdfReader
    pdf = PdfReader(io.BytesIO(raw))
    return "\n".join((pg.extract_text() or "") for pg in pdf.pages[:pages])


def text(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(h or ""))).replace("&amp;", "&").strip()


def org_keys(name):
    """회사 이름 비교 키들: 주식회사·㈜·보험대리점 등 떼고, 앞 영문 약자는 한글 읽기도(KB증권 ↔ 케이비증권)."""
    k = re.sub(r"\s+|㈜|\(주\)|주식회사|\(유\)|유한회사|보험대리점|\(구\s*[^)]*\)", "", str(name or "")).upper()
    k = re.sub(r"[·.,\-]", "", k)
    keys = {k}
    m = re.match(r"([A-Z]{1,5})(.+)", k)
    if m:
        keys.add("".join(LATIN[c] for c in m.group(1)) + m.group(2))
    return {x for x in keys if len(x) >= 2}


# ---------- 금감원 ----------

def fss_rows(html, base=FSS_LIST):
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        href = re.search(r'href="([^"]*openInfo/view\.do[^"]+)"', tr)
        if len(tds) < 3 or not href:
            continue
        d = re.sub(r"\D", "", text(tds[2]))
        if len(d) != 8:
            continue
        url = urljoin(base, href.group(1).replace("&amp;", "&"))
        key = re.search(r"examMgmtNo=(\d+).*?emOpenSeq=(\d+)", url)
        if not key:
            continue
        # 저장은 짧게(4천 줄): 기관·날짜·키만, 주소는 키로 다시 만든다
        out.append({"id": f"fss:{key.group(1)}-{key.group(2)}", "org": text(tds[1])[:40], "date": f"{d[:4]}-{d[4:6]}-{d[6:]}"})
    return out


def fss_url(rec_id):
    m = re.match(r"fss:(\d+)-(\d+)$", rec_id or "")
    return f"https://www.fss.or.kr/fss/job/openInfo/view.do?menuNo=200476&examMgmtNo={m.group(1)}&emOpenSeq={m.group(2)}" if m else None


def fss_records(state):
    return [{"agency": "금감원", **r, "url": fss_url(r["id"])} for r in (state or {}).get("rows", {}).values()]


def refresh_fss(state, *, get, now, backfill_pages=60, new_pages=5, pause=None):
    # 11-05 실제: 한 실행 200쪽(쪽당 약 0.6MB)을 받은 다음 실행에서 금감원 연결 시간 초과 — 실행당 60쪽·쪽 사이 0.5초로 줄인다(남은 채우기 약 2~3일)
    """앞쪽(새 공개) 몇 쪽 + 뒤쪽 채우기 몇 쪽. state: {"rows": {id: row}, "nextPage": n, "done": bool, "since": …}.
    반환: (state, {"status", "pages", "new", "error"?})"""
    state = dict(state or {})
    rows = dict(state.get("rows") or {})
    since = state.get("since") or FSS_SINCE
    edate = now.date().isoformat()
    fresh, pages, err = 0, 0, None

    def page(n):
        if pause:
            pause(0.5)                                  # 공개 누리집 — 쪽 사이 잠깐 쉰다
        r = get(f"{FSS_LIST}&sdate={since}&edate={edate}&pageIndex={n}", headers=UA, timeout=30)
        if getattr(r, "status_code", 200) != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        return fss_rows(r.text)

    try:
        for n in range(1, new_pages + 1):             # 새로 공개된 것: 이미 아는 줄이 나오면 멈춘다
            got = page(n)
            pages += 1
            new = [x for x in got if x["id"] not in rows]
            for x in new:
                rows[x["id"]] = x
            fresh += len(new)
            if len(new) < len(got) or not got:
                break
        if not state.get("done"):                       # 처음엔 2016년부터 뒤쪽을 실행마다 몇 쪽씩
            n = int(state.get("nextPage") or 1)
            for _ in range(backfill_pages):
                got = page(n)
                pages += 1
                if not got:
                    state["done"] = True
                    break
                for x in got:
                    rows.setdefault(x["id"], x)
                n += 1
            state["nextPage"] = n
    except Exception as e:                              # 실패는 0건이 아니라 미확인 — 앞 상태 유지
        err = f"{type(e).__name__}: {str(e)[:60]}"
    state.update(rows=rows, since=since, checkedAt=now.isoformat(timespec="seconds"))
    return state, {"source": "금감원 제재내용공개", "status": "partial" if err else "ok", "pages": pages, "new": fresh,
                   "rows": len(rows), "backfillDone": bool(state.get("done")), **({"error": err} if err else {})}


def fss_summary(pdf_text):
    """'제재내용 공개안' 앞부분: 기관·임원·직원 조치와 제재대상사실 첫 줄. 사람 이름은 공개안에 없다."""
    t = re.sub(r"[ \t]+", " ", pdf_text or "")
    flat = re.sub(r"\s*\n\s*", " / ", t)
    body = flat[flat.find("제재조치내용"):] if "제재조치내용" in flat else flat   # '금융기관명'의 '기관'을 피한다

    def part(label, nxt):
        m = re.search(r"(?:^|[/\s])" + label + r"\s+(.*?)\s*(?:/\s*)?(?<![가-힣])" + nxt, body)
        return re.sub(r"\s*/\s*", " ", m.group(1)).strip(" /")[:160] if m else None
    inst = part(r"기\s*관", r"임\s*원")
    exe = part(r"임\s*원", r"직\s*원")
    fact = re.search(r"4\.\s*제재대상사실\s*/?\s*(.{0,200})", flat)
    ceo = bool(re.search(r"(?:前|전|현)?\s*대표\s*이사|최고경영자|\bCEO\b|은행장", flat))
    return {"inst": inst, "exec": exe, "execSanctioned": bool(exe) and not re.match(r"해당\s*사항\s*없", exe or ""),
            "ceoMentioned": ceo, "fact": re.sub(r"\s*/\s*", " ", fact.group(1)).strip()[:160] if fact else None}


def fss_detail(row, *, get, read_pdf=None):
    """상세 페이지 → 공개안 PDF → 요약. 실패는 {"status": …}."""
    try:
        r = get(row.get("url") or fss_url(row["id"]), headers=UA, timeout=30)
        hrefs = re.findall(r'href="([^"]*hpdownload[^"]*\.pdf[^"]*)"', r.text)
        if not hrefs:
            return {"status": "no_pdf"}
        p = get(urljoin("https://www.fss.or.kr/", hrefs[0].replace("&amp;", "&")), headers=UA, timeout=40)
        if getattr(p, "status_code", 200) != 200 or not p.content[:4] == b"%PDF":
            return {"status": "pdf_failed"}
        return {"status": "ok", **fss_summary((read_pdf or pdf_text)(p.content, 3))}
    except Exception as e:
        return {"status": "failed", "error": type(e).__name__}


# ---------- 개인정보위 ----------

PIPC_LIST = "https://www.pipc.go.kr/np/cop/bbs/selectBoardList.do?bbsId=BS258&mCode=C010040000"
PIPC_VIEW = "https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS258&mCode=C010040000&nttId="
PIPC_FILE = "https://www.pipc.go.kr/np/cmm/fms/FileDown.do?atchFileId={}&fileSn={}"
# 탐침 184: 위반조항을 '법 제29조'로 줄여 쓴 공표도 있다('1한국연구재단법 제29조…'), 처분일 끝 점이 없는 것도('2026.1.28과징금')
LAW = r"(?:(?:舊\s*)?(?:개인정보\s*)?보호법|법(?=\s*제\s*\d))"
DATE = r"(20\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})(?!\d)\s*\.?"


def pipc_records(state):
    return [r for recs in ((state or {}).get("posts") or {}).values() for r in recs]


def pipc_rows(pdf_text):
    """'개인정보보호법 위반 행정처분 결과 공표' 표: 순번 | 위반행위를 한 자 | 위반조항 | 위반내용 | 처분일자 | 처분내용 (탐침 181·182).
    운영 pypdf(5.x)는 칸 사이 띄어쓰기 없이 이어 붙인다('처분내용1㈜한성크린텍舊 보호법*제29조안전조치의무 2026. 9. 18.과징금 7,088만원과태료 360만원2㈜…') —
    순번을 1, 2, 3 차례로 찾아 줄을 나눈다(앞 줄 금액 '360만원' 뒤에 붙은 '2'를 순번으로)."""
    t = re.sub(r"\s+", " ", pdf_text or "")
    t = t[t.find("처분내용") + 4:] if "처분내용" in t else t
    t = re.split(r"\*\s*舊\s*보호법\s*:|20\d{2}년\s*\d{1,2}월\s*\d{1,2}일\s*개\s*인\s*정\s*보", t)[0]
    starts, pos, n = [], 0, 1
    while n < 200:
        # 순번 뒤가 금액·조항 낱말이면 순번이 아니다(탐침 184: '과징금 4억 7,800만원'의 4, '제1항위탁업무'의 1)
        m = re.compile(r"(?<![\d제])" + str(n) + r"(?![\d.,])(?!\s*(?:억|만|천|원|개|명|일|월|년|조|항|호|%))\s*((?:㈜|\(주\))?\s*[^\d\s*][^*]{0,40}?)\s*" + LAW).search(t, pos)
        if not m:
            break
        starts.append(m)
        pos, n = m.end(), n + 1
    out = []
    for i, m in enumerate(starts):
        seg = t[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(t)]
        d = re.search(DATE, seg)
        if not d:
            continue
        what = re.sub(r"제\d+조(?:의\d+)?(?:\s*제\d+항)?|[*,]", " ", seg[:d.start()])
        what = re.sub(r"\s+", " ", what).strip()[:80]
        acts = re.findall(r"과징금\s*[\d,억만\s]+?원|과태료(?:\s*부과)?\s*[\d,억만\s]+?원|시정조치\s*(?:명령|권고)|공표\s*명령|개선\s*권고|징계\s*권고", seg[d.end():])
        org = re.sub(r"^(?:㈜|\(주\))\s*|\s*(?:㈜|\(주\))$", "", m.group(1).strip())
        org = re.sub(r"\s+", " ", re.sub(r"[\u4e00-\u9fff]", "", org)).strip()          # HWP 제어 글자가 한자처럼 섞인 것('경북대학교 병원 汤捯')
        out.append({"agency": "개인정보위", "no": str(i + 1), "org": org[:60], "date": f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}",
                    "what": what, "inst": ", ".join(dict.fromkeys(re.sub(r"\s+", " ", a).strip() for a in acts))[:120],
                    "major": any(a.startswith("과징금") for a in acts)})
    return out


def attachment_text(raw, read_pdf=None):
    """결과의 공표 첨부: PDF(대부분)·HWP(OLE)·HWPX(zip). 그림(PNG)은 None(탐침 182: PDF 24·HWP 2·HWPX 1·PNG 2)."""
    if raw[:4] == b"%PDF":
        return (read_pdf or pdf_text)(raw, 6)
    try:
        import kr_local_notice_watch as kl
        if raw[:4] == b"\xd0\xcf\x11\xe0":
            return kl.hwp_text(raw)
        if raw[:4] == b"PK\x03\x04":
            return kl.hwpx_text(raw)
    except Exception:
        return None
    return None


def refresh_pipc(state, *, get, now, max_posts=40, read_pdf=None, pause=None):
    """결과의 공표 게시판의 새 글만 첨부 PDF를 읽는다. state: {"posts": {nttId: [records]}}.
    첨부를 못 읽은 글은 저장하지 않아 다음 실행에 다시 본다(11-05 첫 실행: 세션 없이 내려받아 29건 모두 PDF가 아니었다 — 빈 목록으로 저장돼
    다시 안 읽힐 뻔). 첨부 내려받기는 글을 연 세션 쿠키가 필요하다(탐침 181은 Session으로 성공)."""
    state = dict(state or {})
    posts = {k: v for k, v in (state.get("posts") or {}).items() if v}       # 빈 글(예전 실패)은 다시 읽는다
    err, read, outcome = None, 0, {}
    try:
        ids = []
        for n in range(1, 6):
            r = get(f"{PIPC_LIST}&pageIndex={n}", headers=UA, timeout=30)
            got = re.findall(r"selectBoardArticle\.do[^\"']*?nttId=(\d+)", r.text)
            got = [x for x in dict.fromkeys(got) if x not in ids]
            if not got:
                break
            ids += got
            if all(x in posts for x in got):
                break
        for ntt in [x for x in ids if x not in posts][:max_posts]:
            v = get(PIPC_VIEW + ntt, headers=UA, timeout=30)
            files = re.findall(r"fn_egov_downFile\w*\(\s*'([^']+)'\s*,\s*'([^']+)'", v.text)
            recs, got_pdf = [], False
            if not files:
                outcome["no_file"] = outcome.get("no_file", 0) + 1
            for fid, sn in files[:3]:
                f = get(PIPC_FILE.format(fid, sn), headers={**UA, "Referer": PIPC_VIEW + ntt}, timeout=40)
                body = attachment_text(f.content, read_pdf) if getattr(f, "status_code", 200) == 200 else None
                if body is None:
                    k = f"unread:{getattr(f, 'status_code', '?')}:{f.content[:4]!r}"
                    outcome[k] = outcome.get(k, 0) + 1
                    continue
                got_pdf = True
                for x in pipc_rows(body):
                    recs.append({**x, "id": f"pipc:{ntt}:{x['no']}", "url": PIPC_VIEW + ntt})
            if recs:
                posts[ntt] = recs
                read += 1
                outcome["ok"] = outcome.get("ok", 0) + 1
            elif got_pdf:
                outcome["parsed_empty"] = outcome.get("parsed_empty", 0) + 1
            if pause:
                pause(0.2)
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:60]}"
    state.update(posts=posts, checkedAt=now.isoformat(timespec="seconds"))
    rows = sum(len(v) for v in posts.values())
    unread = sum(v for k, v in outcome.items() if k != "ok")
    return state, {"source": "개인정보위 결과의 공표", "status": "partial" if err or unread else "ok", "posts": len(posts), "read": read, "rows": rows,
                   "outcomes": outcome, **({"error": err} if err else {})}


# ---------- 공정위 ----------

FTC_LIST = "https://case.ftc.go.kr/ocp/co/ltfr.do"
FTC_SINCE = "2016-01-01"


def ftc_respondents(title):
    """사건명 앞 '…의 '까지를 피심인으로: '현대자동차(주) 및 기아(주)의 부당한 …' → ['현대자동차', '기아'].
    '4개 시중은행의 …'처럼 이름 없는 묶음은 [] (탐침 183 — 이런 건은 사건명으로 회사를 알 수 없다)."""
    m = re.match(r"\s*(.+?)의\s", title or "")
    head = m.group(1).split("관련")[-1] if m else ""        # '…발주 … 입찰 관련 ○○의 부당한 공동행위'는 '관련' 뒤가 피심인
    if not head or re.search(r"\d+\s*개|사업자들|업체들|사들$|\s등$|발주", head):
        return []
    out = []
    for x in re.split(r"\s+및\s+|\s*,\s*|\s*[·ㆍ]\s*", head):
        x = re.sub(r"\((?:주|유|합|사|재)\)|㈜|주식회사|유한회사|\s+", "", x).strip()
        if 2 <= len(x) <= 30 and not re.search(r"(?:등|들)$", x):
            out.append(x)
    return out


def refresh_ftc(state, *, get, now, backfill_pages=100, new_pages=3, pause=None, parse=None):
    """공정위 의결서 목록(case.ftc.go.kr ltfr.do, 2016년부터 4,960건·496쪽 — 탐침 183). 앞 몇 쪽 + 뒤 채우기.
    저장은 짧게: 사건번호·피심인(사건명에서)·의결일·조치."""
    if parse is None:
        import kr_signals_watch as ks
        parse = ks.parse_ftc_list
    state = dict(state or {})
    rows = dict(state.get("rows") or {})
    since = state.get("since") or FTC_SINCE
    fresh, pages, err = 0, 0, None

    def page(n):
        if pause:
            pause(0.5)
        r = get(FTC_LIST, params={"startRceptDt": since, "endRceptDt": now.date().isoformat(), "pageIndex": n}, headers=UA, timeout=40)
        if getattr(r, "status_code", 200) != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        got, last = parse(r.text)
        return [{"id": f"ftc:{x['csno']}", "o": ftc_respondents(x["name"]), "d": x.get("decidedOn") or "", "a": (x.get("action") or "")[:20]}
                for x in got if x.get("csno")], last

    try:
        for n in range(1, new_pages + 1):
            got, _ = page(n)
            pages += 1
            new = [x for x in got if x["id"] not in rows]
            for x in new:
                rows[x["id"]] = x
            fresh += len(new)
            if len(new) < len(got) or not got:
                break
        if not state.get("done"):
            n = int(state.get("nextPage") or 1)
            for _ in range(backfill_pages):
                got, last = page(n)
                pages += 1
                for x in got:
                    rows.setdefault(x["id"], x)
                if not got or (last and n >= last):
                    state["done"] = True
                    break
                n += 1
            state["nextPage"] = n
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:60]}"
    state.update(rows=rows, since=since, checkedAt=now.isoformat(timespec="seconds"))
    return state, {"source": "공정위 의결서 목록", "status": "partial" if err else "ok", "pages": pages, "new": fresh, "rows": len(rows),
                   "backfillDone": bool(state.get("done")), **({"error": err} if err else {})}


def ftc_records(state):
    out = []
    for r in ((state or {}).get("rows") or {}).values():
        if not re.match(r"\d{4}-\d{2}-\d{2}", r.get("d") or ""):
            continue
        for i, org in enumerate(r.get("o") or []):
            out.append({"agency": "공정위", "id": f"{r['id']}:{i}", "org": org, "date": r["d"], "inst": r.get("a"),
                        "url": f"{FTC_LIST}?caseNo={r['id'][4:]}"})
    return out


# ---------- 경력 칸과 잇기 ----------

TOP_ROLE = re.compile(r"대표\s*이사|대표(?!\s*단)|(?<!부)사장|부회장|회장|은행장|행장|\bCEO\b|최고경영자")
YEAR = r"(?:(?:19|20)\d{2}|['’]\d{2})"


def _year(s):
    s = s.strip("'’")
    return int(s) if len(s) == 4 else 2000 + int(s) if int(s) < 50 else 1900 + int(s)


def _years(seg, now):
    ys = re.findall(r"(?<![\d])(" + YEAR + r")(?:\s*[.년]\s*\d{1,2})?", seg)
    return [y for y in (_year(x) for x in ys) if 1950 <= y <= now.year + 1]


ONLY_PERIOD = re.compile(r"[\s()\[\]\d.,~∼\-–'’년월현재現]+")


def top_roles(career, segments, *, now):
    """경력 칸에서 '회사 + 최고 경영 직함' → [{org, role, start, end, current, seg}]. 기간을 못 읽으면 start/end None.
    한 마디에 여러 자리가 붙어 있으면('…부문장 에스엘 독립이사KB자산운용 대표이사 사장 SK증권 대표이사 사장') 자리마다 따로 보고,
    기간·현직 표시는 그 자리 몫의 글자(앞 자리 끝 ~ 다음 자리 앞)에서만 읽는다 — 11-05 실제: 마디 첫머리 '現)'를 뒤 자리들에도 붙여
    'SK증권 대표이사 ?~2026'으로 읽었다. 기간이 뒤 괄호로 따로 끊긴 마디('(2024~현재)')는 마지막 자리에 붙인다."""
    out = []
    segs = segments(career)
    for i, seg in enumerate(segs):
        tail = segs[i + 1] if i + 1 < len(segs) and ONLY_PERIOD.fullmatch(segs[i + 1]) else ""
        roles = list(TOP_ROLE.finditer(seg))
        prev = 0
        for j, role in enumerate(roles):
            raw_pre = seg[prev:role.start()]
            nxt = roles[j + 1].start() if j + 1 < len(roles) else len(seg)
            own = raw_pre + seg[role.start():nxt] + (" " + tail if j + 1 == len(roles) and tail else "")
            prev = role.end()
            pre = re.sub(r"^(?:[\s\-·ㆍ•()\[\]~∼\d.,년월'’]|現|前|現\)|前\)|현\s*\)|전\s*\)|\(현\)|\(전\)|현재)+", "", raw_pre)
            toks = re.findall(r"(?:㈜|\(주\))?[가-힣A-Za-z0-9&][가-힣A-Za-z0-9&\.\-]*(?:㈜|\(주\))?", pre)
            toks = [t for t in toks if not re.fullmatch(r"전|현|前|現|겸|및|등|상임|비상임|비상근|상근|부문|그룹|이사|대표이사|대표|사장|부사장", t)]
            if not toks:
                continue
            org = re.sub(r"^(?:㈜|\(주\))|(?:㈜|\(주\))$", "", toks[-1])
            if len(org) < 2 or re.search(r"대학|학회|협회|재단|위원회|연구원|정부|부처|청$|법원|검찰|공단|공사$|법무법인|회계법인", org) \
                    or re.search(r"법무법인|회계법인|세무법인|학회|협회|대학교?\s*\S*$", pre[-30:]):
                continue
            years = _years(own, now)
            # 현직: 이 자리 몫에 現·현재·열린 기간이 있거나, 마디 첫 자리이고 마디 머리에 現
            cur = bool(re.search(r"現|현\s*\)|\(현\)|현재|~\s*$|~\s*\)", own)) or (j == 0 and bool(re.match(r"\s*[\(\[]?\s*(?:現|현\s*\))", seg)))
            past = bool(re.search(r"前|전\s*\)|\(전\)", raw_pre)) or (j == 0 and bool(re.match(r"\s*[\(\[]?\s*(?:前|전\s*\))", seg)))
            cur = cur and not past
            start = min(years) if years else None
            end = now.year if cur else (max(years) if len(years) >= 2 else (start if start and not re.search(r"~|∼|-", own) else None))
            out.append({"org": org, "role": seg[role.start():role.end()], "start": start, "end": end, "current": cur, "seg": own.strip()[:100]})
    return out


def match(roles, records, *, lag_years=2):
    """경력 최고 경영 자리 × 공식 제재. 기간이 있으면 제재일이 [시작, 끝+lag] 안일 때만 'overlap', 기간을 못 읽으면 'timing_unknown'."""
    idx = {}
    for r in records:
        for k in org_keys(r["org"]):
            idx.setdefault(k, []).append(r)
    out = []
    for role in roles:
        seen = set()
        for k in org_keys(role["org"]):
            for r in idx.get(k, []):
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                y = int(r["date"][:4])
                if role["start"] and role["end"]:
                    if not (role["start"] <= y <= role["end"] + lag_years):
                        continue
                    timing = "overlap"
                elif role["start"] and not role["end"]:
                    if y < role["start"]:
                        continue
                    timing = "timing_unknown"
                else:
                    timing = "timing_unknown"
                out.append({"role": role, "record": r, "timing": timing})
    return out
