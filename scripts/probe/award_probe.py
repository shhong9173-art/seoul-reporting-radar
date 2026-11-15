"""probe 250: (가) 정기보고서 숨은 대목 읽기가 실제 DART 원문에서 되는지 — 구조·건수만(새 줄 글자는 찍지 않는다, 옛 줄 본보기만).
(나) 단독 원천 후보의 자료 주소 찾기(스크립트 주소·API 낱말). 공개 페이지만, 저장 안 함."""
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
OUT = []
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Accept-Language": "en,ko;q=0.8"}


def part_a():
    import dart_watch
    import earnings_compare as ec
    import governance_watch as gw
    import kr_exec_watch as kx
    import kr_report_notes as n
    key = os.environ.get("DART_API_KEY")
    if not key:
        OUT.append("[가] DART_API_KEY 없음")
        return
    registry = json.loads((ROOT / "dart_corp_codes.json").read_text(encoding="utf-8"))
    try:
        table = dart_watch.load_corp_codes(key)
    except SystemExit:
        table = None
    now = dt.datetime.now(ec.KST)
    year, report = ec.target_period(now)
    dy, base_report = kx.BASE[report]
    OUT.append(f"[가] 대상 기간 {year}{report} · 앞 보고서 {year + dy}{base_report} · 출입처 {len(kx.BEATS)}곳")
    names = [x for x, _, _ in kx.BEATS]
    codes, missing = gw.resolve_codes(names, registry, table)
    for name, alts in kx.SPELLINGS.items():
        if name in names and name not in codes:
            for alt in alts:
                c2, _ = gw.resolve_codes([alt], registry, table)
                if alt in c2:
                    codes[name] = c2[alt]
    OUT.append(f"[가] 고유번호 찾음 {len([x for x in names if x in codes])} · 못 찾음 {[x for x in names if x not in codes]}")
    since = (now - dt.timedelta(days=430)).strftime("%Y%m%d")
    filed, nobase, todo = 0, 0, []
    for name in names:
        code = codes.get(name)
        if not code:
            continue
        try:
            st, body = ec.call("list.json", {"corp_code": code, "bgn_de": since, "end_de": now.strftime("%Y%m%d"), "pblntf_ty": "A", "page_count": "40"},
                               get=lambda u, params, **kw: requests.get(u, params={"crtfc_key": key, **params}, **kw), sleep=time.sleep)
        except Exception as e:  # noqa: BLE001
            OUT.append(f"   {name}: 목록 실패 {type(e).__name__}")
            continue
        time.sleep(0.25)
        rows = (body or {}).get("list") or [] if st == "ok" else []
        rcept, when = n.report_of(rows, year, report)
        base, _ = n.report_of(rows, year + dy, base_report)
        if rcept:
            filed += 1
            if not base:
                nobase += 1
            todo.append((name, rcept, base, when))
    OUT.append(f"[가] 이번 기간 보고서 낸 곳 {filed}/{len(names)} · 그중 앞 보고서 못 찾음 {nobase} · 접수일 분포 {sorted({t[3] for t in todo})}")
    want = ["두산에너빌리티", "한화솔루션", "현대제철", "포스코홀딩스", "LG화학", "고려아연", "현대자동차", "금호타이어", "S-Oil", "롯데케미칼", "기아", "현대모비스"]
    picked = ([t for t in todo if t[0] in want] + [t for t in todo if t[0] not in want])[:10]
    budget = [60]
    plain = lambda t: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    for name, rcept, base, when in picked:
        t0 = time.time()
        texts, err = kx.fetch_document(key, rcept, get=requests.get, sleep=time.sleep, want="제재")
        cst, csec = ("ok", max((n.sections(t) for t in texts[:3]), key=len)) if texts else ("failed", None)
        bst, bsec, berr = n.read_report(key, base, get=requests.get, sleep=time.sleep, budget=budget) if base else ("none", None, "앞 보고서 없음")
        if cst != "ok" or bst != "ok" or not csec:
            OUT.append(f"   {name}: 이번 {cst}({err}) · 앞 {bst}({berr})")
            continue
        line = [f"   {name}({when}) {time.time() - t0:.0f}초"]
        for sec in n.SECTIONS:
            cur, old = csec.get(sec), bsec.get(sec)
            if cur is None or old is None:
                line.append(f"{sec}: 이번 {'못 찾음' if cur is None else len(cur)} · 앞 {'못 찾음' if old is None else len(old)}")
                continue
            fresh = n.fresh_lines(cur, set(n.keys_of(old)))
            kinds = f"표 한 건 {sum(1 for x in cur if n.SEP in x)}·줄 {sum(1 for x in cur if n.SEP not in x)}"
            line.append(f"{sec}: 이번 {len(cur)}({kinds}) · 앞 {len(old)} · 새 줄 {len(fresh)}(처음 보는 건 {sum(1 for x in fresh if x.startswith('〔처음'))}·바뀐 줄 {sum(1 for x in fresh if x.startswith('〔앞'))}·그 밖 {sum(1 for x in fresh if not x.startswith('〔'))})")
        OUT.append(" | ".join(line))
        # 제재 대목이 비었으면 그 자리에 적힌 안내 글(회사 기재 안내문 — 단서가 아니다)
        if csec.get("sanction") is not None and len(csec["sanction"]) <= 1:
            for t in texts[:1]:
                marks = [(m.start(), m.end(), n.clean(m.group(1))) for m in n.TITLE.finditer(t)]
                for i, (_, end, title) in enumerate(marks):
                    if re.search(r"제재\s*(?:등과|등에|현황)", title):
                        nxt = marks[i + 1][0] if i + 1 < len(marks) else len(t)
                        OUT.append(f"      제재 대목 글({nxt - end}자): 「{plain(t[end:nxt])[:260]}」")
                        break
    # 잡음 확인: 지난 반기(8월 제출) ← 1분기(5월 제출) 비교의 새 줄 글(오래된 공개 보고서)
    for name in ["포스코홀딩스", "롯데케미칼", "한화솔루션"]:
        code = codes.get(name)
        st, body = ec.call("list.json", {"corp_code": code, "bgn_de": since, "end_de": now.strftime("%Y%m%d"), "pblntf_ty": "A", "page_count": "40"},
                           get=lambda u, params, **kw: requests.get(u, params={"crtfc_key": key, **params}, **kw), sleep=time.sleep)
        rows = (body or {}).get("list") or []
        h1, _ = n.report_of(rows, 2026, "11012")
        q1, _ = n.report_of(rows, 2026, "11013")
        if not h1 or not q1:
            OUT.append(f"   [잡음] {name}: 반기 {h1} · 1분기 {q1}")
            continue
        s1, a1, e1 = n.read_report(key, h1, get=requests.get, sleep=time.sleep, budget=budget)
        s0, a0, e0 = n.read_report(key, q1, get=requests.get, sleep=time.sleep, budget=budget)
        if s1 != "ok" or s0 != "ok":
            OUT.append(f"   [잡음] {name}: {s1} {e1} · {s0} {e0}")
            continue
        for sec in ("sanction", "suit"):
            if sec in a1 and sec in a0:
                fresh = n.fresh_lines(a1[sec], set(n.keys_of(a0[sec])))
                OUT.append(f"   [잡음] {name} 반기←1분기 {sec}: 반기 {len(a1[sec])} · 1분기 {len(a0[sec])} · 새 줄 {len(fresh)}")
                for x in fresh[:5]:
                    OUT.append("        · " + x[:240])


def dump(name, url, pats=(), **kw):
    try:
        r = requests.get(url, headers=UA, timeout=40, **kw)
        body = r.text
        srcs = re.findall(r'<script[^>]+src="([^"]+)"', body, re.I)
        urls = sorted({u for u in re.findall(r'["\'`](/?[A-Za-z0-9_./:-]*(?:api|ajax|search|json|getList|List\.do|notice)[A-Za-z0-9_./?=&:-]*)["\'`]', body, re.I) if 6 < len(u) < 140})
        OUT.append(f"[{name}] HTTP {r.status_code} · {len(body)}자 · 스크립트 {len(srcs)}개 {[s[-70:] for s in srcs[:8]]}")
        if urls:
            OUT.append("   주소 낱말: " + " | ".join(urls[:24]))
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S | re.I)))
        for p in pats:
            for m in list(re.finditer(p, plain if not p.startswith("RAW:") else body, re.I))[:3]:
                src = plain if not p.startswith("RAW:") else body
                OUT.append("   · " + re.sub(r"\s+", " ", src[max(0, m.start() - 100):m.end() + 200]).strip()[:330])
        return body
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[{name}] 실패 {type(e).__name__}: {str(e)[:120]}")
        return ""


def part_b():
    try:
        r = requests.get("https://competition-cases.ec.europa.eu/main-WPNRFSVK.js", headers=UA, timeout=60)
        urls = sorted({u for u in re.findall(r'https?://[A-Za-z0-9./_-]+', r.text) if re.search(r"api|search|case|europa", u) and not re.search(r"w3\.org|angular|github|eur-lex|ecl", u)})
        OUT.append(f"[EU main JS] 주소 {len(urls)}개: " + " | ".join(urls[:30]))
        for m in list(re.finditer(r'apiKey|caseInstrument|searchApi|/rest/search', r.text))[:6]:
            OUT.append("   · " + r.text[max(0, m.start() - 120):m.end() + 160].replace("\n", " "))
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[EU main JS] 실패 {type(e).__name__}")
    b = dump("인도 CCI 심사 중 신고", "https://www.cci.gov.in/combination/notice-under-review", [r"RAW:ajax\s*:\s*[^\n]{0,200}", r"RAW:url\s*:\s*[\"'][^\"']+", r"C-20\d\d/\d\d/\d+", r"POSCO|Hyundai|Kia|LG |Hanwha|JSW|Korea"])
    b = dump("SAMR 간이사건 공시", "https://www.samr.gov.cn/fldes/ajgs/jyaj/", [r"RAW:build/unit[^\n]{0,400}", r"RAW:(?:webId|pageId|tplSetId|unitUrl|parseType)[\"'=:\s]+[^,;\n]{0,80}"])
    i = b.find("build/unit")
    if i > 0:
        OUT.append("   SAMR 호출 앞뒤: " + re.sub(r"\s+", " ", b[max(0, i - 700):i + 500]))
    b = dump("통합환경허가 게시판 5", "https://ieps.nier.go.kr/web/board/5/?menu=41", [r"RAW:<title>[^<]+", r"RAW:class=\"(?:tit|title|subject)[^>]*>\s*(?:<a[^>]*>)?\s*[^<]{4,80}"])
    plainb = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", b, flags=re.S | re.I)))
    i = plainb.find("번호")
    OUT.append("   게시판 5 목록 머리: " + plainb[i:i + 500])


for f in (part_a, part_b):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[{f.__name__}] 예외 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
