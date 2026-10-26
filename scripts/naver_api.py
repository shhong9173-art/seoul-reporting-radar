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


def news_search(cid, secret, params, *, timeout=12, get=None):
    """Return (endpoint label, items). Raises NaverKeyRefused if every endpoint refuses the key;
    other HTTP/network errors propagate (requests.RequestException)."""
    if get is None:
        import requests
        get = requests.get
    refused = []
    for label, url, headers in ENDPOINTS:
        resp = get(url, params=params, headers=headers(cid, secret), timeout=timeout)
        if resp.status_code in (401, 403):
            refused.append(f"{label} HTTP {resp.status_code}")
            continue
        resp.raise_for_status()
        return label, resp.json().get("items", [])
    raise NaverKeyRefused("키 거부: " + ", ".join(refused))
