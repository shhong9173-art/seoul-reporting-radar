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


def refresh_fss(state, *, get, now, backfill_pages=200, new_pages=5, pause=None):
    """앞쪽(새 공개) 몇 쪽 + 뒤쪽 채우기 몇 쪽. state: {"rows": {id: row}, "nextPage": n, "done": bool, "since": …}.
    반환: (state, {"status", "pages", "new", "error"?})"""
    state = dict(state or {})
    rows = dict(state.get("rows") or {})
    since = state.get("since") or FSS_SINCE
    edate = now.date().isoformat()
    fresh, pages, err = 0, 0, None

    def page(n):
        if pause:
            pause(0.2)                                  # 공개 누리집 — 쪽 사이 잠깐 쉰다
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
LAW = r"(?:舊\s*)?(?:개인정보\s*)?보호법"
DATE = r"(20\d{2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\."


def pipc_records(state):
    return [r for recs in ((state or {}).get("posts") or {}).values() for r in recs]


def pipc_rows(pdf_text):
    """'개인정보보호법 위반 행정처분 결과 공표' 표: 순번 | 위반행위를 한 자 | 위반조항 | 위반내용 | 처분일자 | 처분내용 (탐침 181)."""
    t = re.sub(r"\s+", " ", pdf_text or "")
    t = t[t.find("처분내용") + 4:] if "처분내용" in t else t
    starts = list(re.finditer(r"(?:^|\s)(\d{1,3})\s+(\S.{0,50}?)\s+" + LAW, t))
    out = []
    for i, m in enumerate(starts):
        seg = t[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(t)]
        seg = re.split(r"\*\s*舊\s*보호법\s*:|20\d{2}년\s*\d{1,2}월\s*\d{1,2}일\s*개\s*인\s*정\s*보", seg)[0]
        d = re.search(DATE, seg)
        if not d:
            continue
        what = re.sub(r"제\d+조(?:의\d+)?(?:\s*제\d+항)?|[*,]", " ", seg[:d.start()])
        what = re.sub(r"\s+", " ", what).strip()[:80]
        acts = re.findall(r"과징금\s*[\d,억만]+\s*원|과태료(?:\s*부과)?\s*[\d,억만]+\s*원|시정조치\s*(?:명령|권고)|공표\s*명령|개선\s*권고|징계\s*권고", seg[d.end():])
        org = re.sub(r"^(?:㈜|\(주\))\s*|\s*(?:㈜|\(주\))$", "", m.group(2).strip())
        out.append({"agency": "개인정보위", "no": m.group(1), "org": org[:60], "date": f"{d.group(1)}-{int(d.group(2)):02d}-{int(d.group(3)):02d}",
                    "what": what, "inst": ", ".join(dict.fromkeys(re.sub(r"\s+", " ", a) for a in acts))[:120],
                    "major": any(a.startswith("과징금") for a in acts)})
    return out


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
                if getattr(f, "status_code", 200) != 200 or f.content[:4] != b"%PDF":
                    k = f"not_pdf:{getattr(f, 'status_code', '?')}:{str(getattr(f, 'headers', {}).get('Content-Type', ''))[:20]}"
                    outcome[k] = outcome.get(k, 0) + 1
                    continue
                got_pdf = True
                for x in pipc_rows((read_pdf or pdf_text)(f.content, 6)):
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
    한 마디에 여러 자리가 붙어 있으면('KB자산운용 대표이사 사장 SK증권 대표이사 사장') 자리마다. 기간이 뒤 괄호로 따로 끊긴 마디('(2024~현재)')는 앞 자리에 붙인다."""
    out = []
    segs = segments(career)
    for i, seg in enumerate(segs):
        tail = segs[i + 1] if i + 1 < len(segs) and ONLY_PERIOD.fullmatch(segs[i + 1]) else ""
        whole = seg + " " + tail if tail else seg
        prev = 0
        for role in TOP_ROLE.finditer(seg):
            pre = re.sub(r"^(?:[\s\-·ㆍ•()\[\]~∼\d.,년월'’]|現|前|現\)|前\)|현\s*\)|전\s*\)|\(현\)|\(전\)|현재)+", "", seg[prev:role.start()])
            prev = role.end()
            toks = re.findall(r"(?:㈜|\(주\))?[가-힣A-Za-z0-9&][가-힣A-Za-z0-9&\.\-]*(?:㈜|\(주\))?", pre)
            toks = [t for t in toks if not re.fullmatch(r"전|현|前|現|겸|및|등|상임|비상임|비상근|상근|부문|그룹|이사|대표이사|대표", t)]
            if not toks:
                continue
            org = re.sub(r"^(?:㈜|\(주\))|(?:㈜|\(주\))$", "", toks[-1])
            if len(org) < 2 or re.search(r"대학|학회|협회|재단|위원회|연구원|정부|부처|청$|법원|검찰|공단|공사$|법무법인|회계법인", org) \
                    or re.search(r"법무법인|회계법인|세무법인|학회|협회|대학교?\s*\S*$", pre[-30:]):
                continue
            years = _years(whole, now)
            cur = bool(re.search(r"現|현\s*\)|\(현\)|현재|~\s*$|~\s*\)", whole))
            start = min(years) if years else None
            end = now.year if cur else (max(years) if len(years) >= 2 else (start if start and not re.search(r"~|∼|-", whole) else None))
            out.append({"org": org, "role": seg[role.start():role.end()], "start": start, "end": end, "current": cur, "seg": whole[:100]})
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
