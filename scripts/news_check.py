"""이미 났나 확인: 네이버 뉴스 검색 API로 최근 기사를 날짜순으로 뽑는다.

필요한 것: developers.naver.com 에서 애플리케이션 등록(검색 API) 후 받은 값을
환경변수 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 에.

실행 예:
  python scripts/news_check.py "LS전선 해저케이블 미국 공장"
  python scripts/news_check.py "고려아연 공급계약" --n 50
낱말을 바꿔 2~3번 돌리는 게 원칙. 네이버에 안 걸리는 온라인 매체·전문지는 구글로 따로 본다.
"""
import argparse
import html
import os
import re
import sys
from email.utils import parsedate_to_datetime

import requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--n", type=int, default=30, help="최대 100")
    ap.add_argument("--sort", default="date", choices=["date", "sim"])
    a = ap.parse_args()

    cid, sec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not cid or not sec:
        sys.exit("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없다.")

    r = requests.get(
        "https://openapi.naver.com/v1/search/news.json",
        params={"query": a.query, "display": min(a.n, 100), "sort": a.sort},
        headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec},
        timeout=20,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    print(f"'{a.query}' 검색 {len(items)}건 ({'최신순' if a.sort == 'date' else '정확도순'})\n")
    for it in items:
        title = html.unescape(re.sub(r"<[^>]+>", "", it["title"]))
        when = parsedate_to_datetime(it["pubDate"]).strftime("%Y-%m-%d %H:%M")
        link = it.get("originallink") or it.get("link")
        print(f"{when} | {title}\n    {link}")


if __name__ == "__main__":
    main()