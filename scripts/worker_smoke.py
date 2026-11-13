"""배포 뒤 운영 점검(11-13): Worker의 기자 전용 도구를 실제로 불러 본다.

11-13에 처리 장부(#795~#797)가 Worker CPU 한도를 넘겨 scoop_desk·radar_today(7일)·us_litigation이
'Error 1102: Worker exceeded resource limits'(HTTP 503)로 31분간 끊겼다. 오프라인 테스트는 모두 통과했고,
운영에서 불러 보기 전에는 알 수 없었다. 이 점검은 main에 Worker 코드가 들어갈 때마다(그리고 3시간마다)
배포가 끝나기를 기다렸다가 도구를 실제로 부른다.

기록 규칙: 도구가 돌려준 글은 찍지 않는다(비공개 저장소 내용). 도구 이름·걸린 시간·글자 수·참/거짓과
Cloudflare 오류 번호만 남긴다. 주소(토큰 포함)는 찍지 않는다. 쓰기 도구는 부르지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import private_store as ps  # noqa: E402

REPO = "shhong9173-art/seoul-reporting-radar"
# (이름, 인자) — 읽기만 하는 도구. 무거운 것(7·14일)을 섞는다: 가벼운 호출만으로는 CPU 한도 초과가 안 보인다.
CALLS = (
    ("radar_today", {}),
    ("scoop_desk", {}),
    ("radar_today", {"hours": 168, "limit": 3}),
    ("scoop_desk", {"days": 14, "include_weak": True, "limit": 30}),
    ("us_litigation", {"limit": 5}),
    ("trade_remedies", {"limit": 5}),
    ("kr_official", {"limit": 5}),
    ("kr_signals", {"limit": 5}),
    ("partner_filings", {"limit": 5}),
    ("us_recalls", {"limit": 5}),
    ("scoop_screen", {}),
    ("scoop_desk", {}),
)
MUST_HAVE = ("radar_today", "scoop_desk", "scoop_screen", "kr_official", "trade_remedies", "us_litigation", "package_save")
MIN_TOOLS = 40
RETRY_WAIT = 20   # 초 — 한 번만 다시 부른다(같은 호출을 되풀이하지 않는다)


def rpc(post, token, method, params, n):
    """→ (result | None, 오류 글). 오류 글에는 주소·본문을 넣지 않는다."""
    try:
        r = post(f"{ps.WORKER}/mcp/{token}", json={"jsonrpc": "2.0", "id": n, "method": method, "params": params},
                 headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": ps.UA}, timeout=90)
    except Exception as e:  # noqa: BLE001 — 예외 글에는 주소가 들어갈 수 있어 종류만
        return None, f"요청 실패({type(e).__name__})"
    if r.status_code != 200:
        code = re.search(r'"error_code"\s*:\s*(\d{3,4})|error code:? ?(\d{3,4})', getattr(r, "text", "") or "")
        return None, f"HTTP {r.status_code}" + (f" · Cloudflare 오류 {code.group(1) or code.group(2)}" if code else "")
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        return None, "본문이 JSON이 아님"
    if not isinstance(body, dict) or body.get("error"):
        return None, f"rpc 오류 {((body or {}).get('error') or {}).get('code')}" if isinstance(body, dict) else "본문 꼴 다름"
    return body.get("result"), ""


def check_call(post, token, name, args, n, sleep=time.sleep):
    """도구 한 번(실패하면 한 번 더) → {name, ok, seconds, chars, why, retried}."""
    out = {"name": name, "args": args, "ok": False, "seconds": 0.0, "chars": 0, "why": "", "retried": False}
    for attempt in (1, 2):
        t0 = time.time()
        res, err = rpc(post, token, "tools/call", {"name": name, "arguments": args}, n)
        out["seconds"] = round(time.time() - t0, 1)
        if res is None:
            out["why"] = err
        else:
            text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
            out["chars"] = len(text)
            if res.get("isError") or "도구 실행 실패" in text:
                out["why"] = "도구가 오류를 돌려줌"
            elif len(text) < 40:
                out["why"] = "빈 응답"
            else:
                out["ok"], out["why"] = True, ""
                return out
        if attempt == 1:
            out["retried"] = True
            sleep(RETRY_WAIT)
    return out


def wait_deploy(get, sha, gh_token, sleep=time.sleep, tries=48, gap=10):
    """이 커밋의 'Workers Builds' 검사가 끝나기를 기다린다 → 'success' | 'failure' | 'none'(검사 없음) | 'timeout'."""
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {gh_token}"} if gh_token else {})}
    seen = False
    for _ in range(tries):
        try:
            r = get(f"https://api.github.com/repos/{REPO}/commits/{sha}/check-runs", headers=headers, timeout=30)
            runs = [c for c in (r.json().get("check_runs") or []) if str(c.get("name", "")).startswith("Workers Builds")] if r.status_code == 200 else []
        except Exception:  # noqa: BLE001
            runs = []
        if runs:
            seen = True
            if runs[0].get("status") == "completed":
                return "success" if runs[0].get("conclusion") == "success" else "failure"
        sleep(gap)
    return "timeout" if seen else "none"


def run(post, get, env, sleep=time.sleep, out=print):
    token = ps.normalize_token(env.get("MCP_ACCESS_TOKEN", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", token or ""):
        out("::error title=worker-smoke::MCP_ACCESS_TOKEN 없음·형식 다름 — 점검 못 함(미확인)")
        return 1
    deploy = "건너뜀"
    if env.get("GITHUB_EVENT_NAME") == "push" and env.get("GITHUB_SHA"):
        deploy = wait_deploy(get, env["GITHUB_SHA"], env.get("GITHUB_TOKEN", ""), sleep)
        if deploy == "failure":
            out("::error title=worker-smoke::Workers Builds 배포 실패 — 운영은 앞 판 그대로다. 앞 판을 점검한다")
    res, err = rpc(post, token, "tools/list", {}, 1)
    names = [t.get("name") for t in (res or {}).get("tools", [])]
    missing = [m for m in MUST_HAVE if m not in names]
    fails = []
    if res is None or len(names) < MIN_TOOLS or missing:
        fails.append(f"tools/list {err or f'{len(names)}개'}{' · 빠진 도구 ' + ','.join(missing) if missing else ''}")
    out(f"::notice title=worker-smoke-list::배포 {deploy} · 도구 {len(names)}개{' · 빠짐 ' + ','.join(missing) if missing else ''}{' · ' + err if err else ''}")
    results = []
    for i, (name, args) in enumerate(CALLS):
        r = check_call(post, token, name, args, 10 + i, sleep)
        results.append(r)
        label = f"{name}{json.dumps(args, ensure_ascii=False) if args else '()'}"
        if not r["ok"]:
            fails.append(f"{label} {r['why']}")
        elif r["retried"]:
            out(f"::warning title=worker-smoke-retry::{label} 첫 호출 실패 뒤 두 번째에 성공 — 한도에 가까울 수 있음")
        sleep(1)
    slow = max(results, key=lambda r: r["seconds"])
    out("::notice title=worker-smoke-calls::" + " · ".join(f"{r['name']} {'정상' if r['ok'] else '실패'} {r['seconds']}초 {r['chars']}자" for r in results))
    out(f"::notice title=worker-smoke::호출 {len(results)}번 중 실패 {sum(1 for r in results if not r['ok'])} · 다시 부른 것 {sum(1 for r in results if r['retried'])} · 가장 느린 것 {slow['name']} {slow['seconds']}초")
    for f in fails:
        out(f"::error title=worker-smoke-fail::{f} — 운영 도구가 끊겼을 수 있다(1102면 CPU 한도 초과: 방금 넣은 코드의 '항목 수 × 기준 수' 반복을 본다)")
    return 1 if fails or deploy == "failure" else 0


if __name__ == "__main__":
    import requests

    sys.exit(run(requests.post, requests.get, os.environ))
