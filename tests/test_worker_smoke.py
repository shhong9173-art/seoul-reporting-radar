"""배포 뒤 운영 점검(scripts/worker_smoke.py) — 네트워크 없이 꼴만 본다."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import worker_smoke as ws  # noqa: E402

TOKEN = "t" * 32
TOOLS = [{"name": n} for n in ws.MUST_HAVE] + [{"name": f"x{i}"} for i in range(40)]
SECRET = "비공개 저장소 내용: [보류] 한화 ITC 337-1494 재검토"


class Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body, text

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


def ok_text(n=300):
    return Resp(200, {"result": {"content": [{"type": "text", "text": SECRET + "가" * n}]}})


E1102 = Resp(503, None, '{"title":"Error 1102: Worker exceeded resource limits","status":503,"error_code":1102}')


def poster(plan):
    """plan: 도구 이름 → 응답 목록(부를 때마다 하나씩, 마지막 것은 되풀이)."""
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        assert url.endswith("/mcp/" + TOKEN)
        if json["method"] == "tools/list":
            return Resp(200, {"result": {"tools": plan.get("tools/list", TOOLS)}})
        name = json["params"]["name"]
        calls.append(name)
        seq = plan.get(name, [ok_text()])
        return seq[min(calls.count(name) - 1, len(seq) - 1)]

    post.calls = calls
    return post


class WorkerSmoke(unittest.TestCase):
    def run_it(self, plan, env=None):
        lines = []
        code = ws.run(poster(plan), lambda *a, **k: Resp(404, {}), {"MCP_ACCESS_TOKEN": TOKEN, **(env or {})}, sleep=lambda s: None, out=lines.append)
        return code, lines

    def test_all_ok_prints_counts_only(self):
        code, lines = self.run_it({})
        self.assertEqual(code, 0)
        blob = "\n".join(lines)
        self.assertIn(f"호출 {len(ws.CALLS)}번 중 실패 0", blob)
        self.assertNotIn("한화", blob)          # 도구가 돌려준 글은 찍지 않는다
        self.assertNotIn(TOKEN, blob)           # 주소·토큰도 찍지 않는다
        self.assertRegex(blob, r"scoop_desk 정상 [\d.]+초 \d+자")

    def test_1102_fails_and_names_the_error(self):
        # 11-13 운영: scoop_desk 기본 호출이 세 번 연속 HTTP 503(1102)
        code, lines = self.run_it({"scoop_desk": [E1102]})
        self.assertEqual(code, 1)
        blob = "\n".join(lines)
        self.assertIn("::error title=worker-smoke-fail::scoop_desk() HTTP 503 · Cloudflare 오류 1102", blob)
        self.assertIn("실패 3", blob)            # CALLS에 scoop_desk가 세 번 있다

    def test_one_retry_then_ok_is_warning_not_failure(self):
        code, lines = self.run_it({"us_litigation": [E1102, ok_text()]})
        self.assertEqual(code, 0)
        self.assertIn("::warning title=worker-smoke-retry::us_litigation", "\n".join(lines))

    def test_tool_error_text_and_missing_tool_fail(self):
        bad = Resp(200, {"result": {"content": [{"type": "text", "text": "도구 실행 실패: boom — 이 도구의 결과는 미확인으로 적는다." + "가" * 50}], "isError": True}})
        code, lines = self.run_it({"kr_official": [bad], "tools/list": [t for t in TOOLS if t["name"] != "scoop_desk"]})
        self.assertEqual(code, 1)
        blob = "\n".join(lines)
        self.assertIn("빠진 도구 scoop_desk", blob)
        self.assertIn("kr_official", blob)
        self.assertIn("도구가 오류를 돌려줌", blob)

    def test_no_token_is_unverified_not_ok(self):
        lines = []
        self.assertEqual(ws.run(poster({}), None, {}, sleep=lambda s: None, out=lines.append), 1)
        self.assertIn("미확인", lines[0])

    def test_waits_for_workers_build_on_push(self):
        states = iter([{"check_runs": []}, {"check_runs": [{"name": "Workers Builds: seoul-reporting-radar", "status": "in_progress"}]},
                       {"check_runs": [{"name": "Workers Builds: seoul-reporting-radar", "status": "completed", "conclusion": "success"}]}])
        got = ws.wait_deploy(lambda *a, **k: Resp(200, next(states)), "abc", "", sleep=lambda s: None)
        self.assertEqual(got, "success")
        self.assertEqual(ws.wait_deploy(lambda *a, **k: Resp(200, {"check_runs": []}), "abc", "", sleep=lambda s: None, tries=3), "none")
        failed = {"check_runs": [{"name": "Workers Builds: x", "status": "completed", "conclusion": "failure"}]}
        self.assertEqual(ws.wait_deploy(lambda *a, **k: Resp(200, failed), "abc", "", sleep=lambda s: None), "failure")


if __name__ == "__main__":
    unittest.main()
