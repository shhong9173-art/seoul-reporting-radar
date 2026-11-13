"""probe 219(216 이어서, #798 배포 뒤): 운영 Worker의 scoop_desk(단독 데스크)가 실제 자료로 도는지 본다. 비공개 저장소 내용은 찍지 않는다 — 건수·구역 머리줄·참/거짓만.
주소(토큰 포함)·응답 본문은 찍지 않는다. 쓰기 도구는 부르지 않는다. 호출 4번."""
import collections
import json
import os
import re
import sys
import time

sys.path.insert(0, "scripts")
import requests  # noqa: E402
import private_store as ps  # noqa: E402

OUT = []
tok = ps.normalize_token(os.environ.get("MCP_ACCESS_TOKEN", ""))
OUT.append(f"token {'있음' if tok else '없음'} 형식 {'정상' if re.fullmatch(r'[A-Za-z0-9_-]{16,128}', tok or '') else '비정상'}")


def rpc(method, params, n):
    try:
        r = requests.post(f"{ps.WORKER}/mcp/{tok}", json={"jsonrpc": "2.0", "id": n, "method": method, "params": params},
                          headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "User-Agent": ps.UA}, timeout=90)
    except Exception as e:  # noqa: BLE001 — 예외 글에는 주소가 들어갈 수 있어 종류만
        return None, type(e).__name__
    if r.status_code != 200:
        code = re.search(r"error code:? ?(\d{3,4})", r.text or "")   # Cloudflare 오류 번호만(본문·주소는 안 찍음)
        # Cloudflare 오류 화면 글(우리 자료 아님)만 본다: 태그·토큰을 지우고 앞 500자
        plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[\s\S]*?</\1>", " ", r.text or ""))).replace(tok, "***")
        hdr = {k: r.headers.get(k) for k in ("cf-ray", "server", "content-type", "retry-after") if r.headers.get(k)}
        return None, f"HTTP {r.status_code} cf {code.group(1) if code else '-'} 본문 {len(r.text or '')}자 헤더 {hdr} 글 「{plain[:500]}」"
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        m = re.search(r"^data: (.*)$", r.text, re.M)
        try:
            body = json.loads(m.group(1)) if m else None
        except Exception:  # noqa: BLE001
            body = None
    if not isinstance(body, dict):
        return None, "본문 해석 실패"
    if body.get("error"):
        return None, f"rpc error {body['error'].get('code')}"
    return body.get("result"), ""


SAFE_HEAD = re.compile(r"^(?:단독 데스크 · |\[\d\. |\[수집 상태|- 이미 처리\(다시 내지 않음\): |- 이미 보도\(|- 약한 유형: |- 참고 등급\(C\)이라 접음: |〈실적 있는 유형〉|〈그 밖 )")


def summarize(label, res, err):
    if res is None:
        OUT.append(f"{label}: 실패 {err}")
        return
    text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
    lines = text.split("\n")
    OUT.append(f"{label}: isError {bool(res.get('isError'))} · 글자 {len(text)} · 줄 {len(lines)} · '도구 실행 실패' {('도구 실행 실패' in text)} · 장부 못 읽음 {('처리 장부를 읽지 못했다' in text)} · 잘림 {('응답 예산' in text)}")
    sec = None
    count = collections.Counter()
    tiers = collections.Counter()
    labels = collections.Counter()
    for ln in lines:
        m = re.match(r"^\[(\d)\. ", ln)
        if m:
            sec = m.group(1)
        if ln.startswith("- ") and sec:
            count[sec] += 1
            if sec == "1":
                parts = ln[2:].split(" · ")
                tiers[parts[0][:1]] += 1
                labels[parts[2] if len(parts) > 2 else "?"] += 1   # 유형 이름(코드에 적힌 감시 이름) — 회사·내용은 안 찍음
        if SAFE_HEAD.match(ln):
            # 머리줄은 코드에 적힌 글 + 건수뿐이다. 수집 상태 줄 아래 내용·후보 줄·패키지 제목은 찍지 않는다.
            OUT.append("   " + (ln if len(ln) < 300 else ln[:300] + "…"))
    OUT.append(f"   1구역 유형: {dict(labels)}")
    OUT.append(f"   구역별 '- ' 줄: {dict(sorted(count.items()))} · 1구역 등급 {dict(tiers)} · 〔이 유형 실적〕 {text.count('〔이 유형 실적〕')} · 〔기사 포인트〕 {text.count('〔기사 포인트〕')}"
               f" · 보도 대조 줄 {len(re.findall(r'^   보도 대조', text, re.M))} · ⚠앞선 기사 {text.count('⚠ 항목 날짜 전 기사')} · 표시 {text.count('〔비슷한 건 처리 이력')}/{text.count('〔앞서 추천')}/{text.count('〔즉시 알림 보냄')}")


def timed(label, args, n):
    t0 = time.time()
    res, err = rpc("tools/call", {"name": "scoop_desk", "arguments": args}, n)
    OUT.append(f"[{label}] {time.time() - t0:.1f}초")
    summarize(label, res, err)


def timed(label, name, args, n, full=False):
    t0 = time.time()
    res, err = rpc("tools/call", {"name": name, "arguments": args}, n)
    dt = time.time() - t0
    if full:
        OUT.append(f"[{label}] {dt:.1f}초")
        summarize(label, res, err)
    else:
        text = "" if res is None else "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        OUT.append(f"{label}: {dt:.1f}초 · {'ok 글자 ' + str(len(text)) + ' 실패글 ' + str('도구 실행 실패' in text) + ' 표시 ' + str(text.count('〔이미 처리')) + '/' + str(text.count('〔처리 이력 있음')) if res is not None else '실패 ' + err[:160]}")
    time.sleep(1.5)


res, err = rpc("tools/list", {}, 1)
OUT.append(f"tools/list: {'실패 ' + err if res is None else str(len(res.get('tools', []))) + '개'}")
timed("scoop_desk() 1", "scoop_desk", {}, 2, full=True)
timed("radar_today(168h)", "radar_today", {"hours": 168, "limit": 3}, 3)
timed("scoop_desk() 2", "scoop_desk", {}, 4)
timed("us_litigation", "us_litigation", {"limit": 5}, 5)
timed("scoop_desk() 3", "scoop_desk", {}, 6)
timed("trade_remedies edis", "trade_remedies", {"section": "edis", "limit": 15}, 7)
timed("kr_official", "kr_official", {"limit": 10}, 8)
timed("scoop_desk(days=14, weak)", "scoop_desk", {"days": 14, "include_weak": True, "limit": 30}, 9)
timed("radar_today(24h)", "radar_today", {}, 10)
timed("us_recalls", "us_recalls", {"limit": 20}, 11)
timed("scoop_desk(company=한화)", "scoop_desk", {"company": "한화"}, 12, full=True)
timed("scoop_desk() 4", "scoop_desk", {}, 13)
open("/tmp/probe_out.txt", "w").write("\n".join(OUT))
print(len(OUT), "lines")
