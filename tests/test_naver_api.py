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


if __name__ == "__main__":
    unittest.main()
