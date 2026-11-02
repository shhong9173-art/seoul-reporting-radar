"""Naver news search: API HUB first, old Developers Center endpoint only on key refusal."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import naver_api  # noqa: E402


class R:
    def __init__(self, code, body=None):
        self.status_code, self.body = code, body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.body


def fake(responses):
    calls = []

    def get(url, params, headers, timeout):
        calls.append((url, headers))
        for prefix, resp in responses.items():
            if url.startswith(prefix):
                return resp
        raise AssertionError(url)
    get.calls = calls
    return get


class NaverApi(unittest.TestCase):
    def test_hub_first_with_ncp_headers(self):
        get = fake({"https://naverapihub": R(200, {"items": [{"title": "a"}]})})
        via, items = naver_api.news_search("i", "s", {"query": "q"}, get=get)
        self.assertEqual((via, len(items)), ("API HUB", 1))
        self.assertEqual(get.calls[0][1]["X-NCP-APIGW-API-KEY-ID"], "i")
        self.assertEqual(len(get.calls), 1)

    def test_old_keys_fall_back_only_on_refusal(self):
        get = fake({"https://naverapihub": R(401), "https://openapi.naver.com": R(200, {"items": []})})
        via, items = naver_api.news_search("i", "s", {"query": "q"}, get=get)
        self.assertEqual(via, "개발자센터")
        self.assertEqual(get.calls[1][1]["X-Naver-Client-Id"], "i")

    def test_refused_everywhere_raises_and_server_errors_do_not_fall_back(self):
        get = fake({"https://naverapihub": R(403), "https://openapi.naver.com": R(401)})
        with self.assertRaises(naver_api.NaverKeyRefused):
            naver_api.news_search("i", "s", {"query": "q"}, get=get)
        get = fake({"https://naverapihub": R(500)})
        with self.assertRaises(RuntimeError):
            naver_api.news_search("i", "s", {"query": "q"}, get=get)
        self.assertEqual(len(get.calls), 1)

    def test_standard_library_fallback(self):
        # auto-desk 색인 단계에는 requests가 없다(11-02 13:14: 33건 모두 ModuleNotFoundError)
        import io
        import json
        import urllib.error
        import urllib.request
        seen = []

        class Body(io.BytesIO):
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def urlopen(req, timeout):
            seen.append((req.full_url, req.get_header("X-ncp-apigw-api-key-id"), timeout))
            if "naverapihub" in req.full_url:
                return Body(json.dumps({"items": [{"title": "단독"}]}).encode())
            raise urllib.error.HTTPError(req.full_url, 401, "x", {}, io.BytesIO(b""))
        real_open, real_requests = urllib.request.urlopen, sys.modules.get("requests")
        urllib.request.urlopen = urlopen
        sys.modules["requests"] = None  # import requests → ModuleNotFoundError
        try:
            via, items = naver_api.news_search("i", "s", {"query": "단독 포스코", "display": 100})
            r = naver_api.urllib_get("https://openapi.naver.com/v1/search/news.json", {"query": "q"}, {}, 5)
        finally:
            urllib.request.urlopen = real_open
            if real_requests is None:
                sys.modules.pop("requests", None)
            else:
                sys.modules["requests"] = real_requests
        self.assertEqual((via, items), ("API HUB", [{"title": "단독"}]))
        self.assertIn("query=%EB%8B%A8%EB%8F%85+%ED%8F%AC%EC%8A%A4%EC%BD%94", seen[0][0])
        self.assertEqual(seen[0][1:], ("i", 12))
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
