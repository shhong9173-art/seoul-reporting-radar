"""probe 249: (가) 정기보고서 숨은 대목 읽기가 실제 DART 원문에서 되는지 — 구조·건수만(새 줄 글자는 찍지 않는다, 옛 줄 본보기만).
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
    want = ["두산에너빌리티", "한화솔루션", "현대제철", "포스코홀딩스", "LG화학", "고려아연", "현대자동차", "금호타이어", "S-Oil", "효성중공업", "HD현대일렉트릭", "롯데케미칼"]
    picked = [t for t in todo if t[0] in want][:9] or todo[:6]
    budget = [40]
    for name, rcept, base, when in picked:
        t0 = time.time()
        cst, csec, cerr = n.read_report(key, rcept, get=requests.get, sleep=time.sleep, budget=budget)
        bst, bsec, berr = n.read_report(key, base, get=requests.get, sleep=time.sleep, budget=budget) if base else ("none", None, "앞 보고서 없음")
        if cst != "ok" or bst != "ok":
            OUT.append(f"   {name}: 이번 {cst}({cerr}) · 앞 {bst}({berr})")
            continue
        line = [f"   {name}({when}) {time.time() - t0:.0f}초"]
        for sec in n.SECTIONS:
            cur, old = csec.get(sec), bsec.get(sec)
            if cur is None or old is None:
                line.append(f"{sec}: 이번 {'못 찾음' if cur is None else len(cur)} · 앞 {'못 찾음' if old is None else len(old)}")
                continue
            have = {n.key_of(x) for x in old}
            fresh = [x for x in cur if n.key_of(x) not in have]
            kept = [x for x in cur if n.key_of(x) in have]
            lens = sorted(len(x) for x in cur)
            line.append(f"{sec}: 이번 {len(cur)}줄(길이 중앙 {lens[len(lens) // 2] if lens else 0}·최대 {lens[-1] if lens else 0}) · 앞 {len(old)}줄 · 새 줄 {len(fresh)}"
                        + (f" · 옛 줄 본보기 「{kept[0][:110]}」" if kept else ""))
        OUT.append(" | ".join(line))


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
    b = dump("ACCESS frnotices", "https://access.trade.gov/frnotices", [r"RAW:(?:fetch|\$\.ajax|\$\.get|\$\.post|XMLHttpRequest|DataTable)\s*\(", r"RAW:_blazor|__doPostBack|htmx|hx-get|hx-post"])
    for src in re.findall(r'<script[^>]+src="([^"]+)"', b, re.I)[:14]:
        if re.search(r"frnotice|site|app|main|public", src, re.I) and not re.search(r"jquery|bootstrap|popper|datatables\.min", src, re.I):
            u = src if src.startswith("http") else "https://access.trade.gov" + (src if src.startswith("/") else "/" + src)
            dump("ACCESS 스크립트 " + src[-40:], u, [r"RAW:url\s*:\s*['\"][^'\"]+", r"RAW:fetch\(['\"`][^'\"`]+"])
    b = dump("EU 사건 검색 첫 화면", "https://competition-cases.ec.europa.eu/search", [])
    for src in re.findall(r'<script[^>]+src="([^"]+)"', b, re.I):
        if re.search(r"main|app|index|chunk", src, re.I):
            u = src if src.startswith("http") else "https://competition-cases.ec.europa.eu/" + src.lstrip("/")
            dump("EU 스크립트 " + src[-40:], u, [r"RAW:https://[a-z0-9.-]*(?:api|search)[a-z0-9./-]*", r"RAW:apiKey[\"'=:\s]+[A-Za-z0-9_-]{4,40}", r"RAW:caseInstrument"])
            break
    b = dump("SAMR 간이사건 공시", "https://www.samr.gov.cn/fldes/ajgs/jyaj/", [r"RAW:(?:\.json|getSearch|pageSize|loadData|ajax)[^\n]{0,160}", r"RAW:<iframe[^>]+>"])
    OUT.append("   SAMR 본문 머리: " + re.sub(r"\s+", " ", b)[900:1700])
    dump("SAMR 무조건 승인 목록(wtjjz)", "https://www.samr.gov.cn/fldes/ajgs/wtjjz/index.html", [r"RAW:<iframe[^>]+>", r"收购|股权|合营"])
    dump("인도 CCI 승인 명령(31조)", "https://www.cci.gov.in/combination/orders-section31", [r"POSCO|Hyundai|Kia|LG |Hanwha|JSW|Korea", r"C-20\d\d/\d\d/\d+", r"RAW:ajax[^\n]{0,200}"])
    dump("인도 CCI 접수 요약(추정)", "https://www.cci.gov.in/combination/combination-filed", [r"C-20\d\d/\d\d/\d+", r"POSCO|Hyundai|Kia|LG |Hanwha|JSW"])
    b = dump("통합환경허가 게시판 5", "https://ieps.nier.go.kr/web/board/5/?menu=41", [r"행정처분|조업정지|과징금|위반", r"RAW:<title>[^<]+", r"RAW:menu=\d+[^\"']{0,40}[\"'][^>]*>[^<]{2,30}"])
    m = dump("통합환경허가 첫 화면 메뉴", "https://ieps.nier.go.kr/web/main", [r"RAW:href=\"(/web/[^\"]+)\"[^>]*>\s*[^<]*(?:처분|공개|허가\s*현황|사업장)[^<]*"])


for f in (part_a, part_b):
    try:
        f()
    except Exception as e:  # noqa: BLE001
        OUT.append(f"[{f.__name__}] 예외 {type(e).__name__}: {str(e)[:200]}")
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
