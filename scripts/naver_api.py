"""Naver news search: NAVER API HUB first, old Developers Center keys as fallback.

Naver moved search APIs to NAVER API HUB (NAVER Cloud Platform). HUB keys use different
headers and host. Keys from the old Developers Center keep working only for apps registered
before the cutoff, so they are tried only when HUB refuses the key (401/403).
"""
from __future__ import annotations

ENDPOINTS = (
    ("API HUB", "https://naverapihub.apigw.ntruss.com/search/v1/news",
     lambda cid, sec: {"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec}),
    ("개발자센터", "https://openapi.naver.com/v1/search/news.json",
     lambda cid, sec: {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}),
)


class NaverKeyRefused(RuntimeError):
    pass


class _Resp:
    def __init__(self, code, body):
        self.status_code, self._body = code, body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        import json
        return json.loads(self._body.decode("utf-8"))


def urllib_get(url, params=None, headers=None, timeout=12):
    """requests가 없는 실행(auto-desk 경쟁지 [단독] 색인 단계는 표준 라이브러리만 쓴다)용.
    11-02 13:14 운영: 네이버 보강 33건이 모두 ModuleNotFoundError(requests)로 실패했다."""
    import urllib.error
    import urllib.parse
    import urllib.request
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(full, headers={**(headers or {}), "User-Agent": "seoul-reporting-radar"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return _Resp(r.status, r.read())
    except urllib.error.HTTPError as e:
        return _Resp(e.code, e.read() or b"{}")


def news_search(cid, secret, params, *, timeout=12, get=None):
    """Return (endpoint label, items). Raises NaverKeyRefused if every endpoint refuses the key;
    other HTTP/network errors propagate (requests.RequestException)."""
    if get is None:
        try:
            import requests
            get = requests.get
        except ModuleNotFoundError:
            get = urllib_get
    refused = []
    for label, url, headers in ENDPOINTS:
        resp = get(url, params=params, headers=headers(cid, secret), timeout=timeout)
        if resp.status_code in (401, 403):
            refused.append(f"{label} HTTP {resp.status_code}")
            continue
        resp.raise_for_status()
        return label, resp.json().get("items", [])
    raise NaverKeyRefused("키 거부: " + ", ".join(refused))
