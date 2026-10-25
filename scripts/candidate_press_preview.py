"""Bounded Google News headline recheck; never proof of no prior reporting."""
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urlsplit


def recheck(terms, *, now, fetcher):
    result = dict(channel="google_news_rss", checkedAt=now.isoformat(),
                  status="not_queried", items=[], rejectedDateCount=0,
                  titleMatchCount=0, rawItemCount=None, truncated=False,
                  noPriorPressProved=False, publisherFulltextCompared=False)
    if not isinstance(terms, list) or not 1 <= len(terms) <= 6 or any(
            not isinstance(t, str) or not 2 <= len(t) <= 80 or '"' in t for t in terms):
        return result
    query = " ".join('"'+t+'"' for t in terms) + " after:" + (now-timedelta(days=365)).date().isoformat()
    result.update(query=query, windowDays=365,
                  queryUrl="https://news.google.com/rss/search?" + urlencode(
                      dict(q=query, hl="ko", gl="KR", ceid="KR:ko")))
    try:
        raw = fetcher(result["queryUrl"])
        if not isinstance(raw, (str, bytes)) or len(raw) > 2_500_000:
            raise ValueError("invalid_rss_size")
        root = ET.fromstring(raw)
        channel = root.find("channel")
        if root.tag != "rss" or channel is None:
            raise ValueError("not_rss_channel")
        rows = channel.findall("item")
        result.update(rawItemCount=len(rows), truncated=len(rows) > 100)
        seen = set()
        for row in rows[:100]:
            title = (row.findtext("title") or "").strip()
            url = (row.findtext("link") or "").strip()
            if not all(t.casefold() in title.casefold() for t in terms):
                continue
            result["titleMatchCount"] += 1
            try:
                date = parsedate_to_datetime(row.findtext("pubDate") or "")
                if date.tzinfo is None or not now-timedelta(days=365) <= date <= now:
                    raise ValueError("outside_search_window")
            except (ValueError, TypeError, OverflowError):
                result["rejectedDateCount"] += 1
                continue
            try:
                u = urlsplit(url)
                safe = u.scheme == "https" and u.hostname and not u.username and not u.password
            except ValueError:
                safe = False
            if not safe or url in seen:
                continue
            seen.add(url)
            if len(result["items"]) < 5:
                result["items"].append(dict(title=title[:250], url=url,
                    publishedAt=date.isoformat(), source=(row.findtext("source") or "")[:100]))
            else:
                result["truncated"] = True
        result["status"] = "possible_prior_titles" if result["items"] else "no_usable_titles_in_response"
    except (OSError, ValueError, ET.ParseError, TimeoutError) as exc:
        result.update(status="search_failed", errorType=type(exc).__name__)
    return result
