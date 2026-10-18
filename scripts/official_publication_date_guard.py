"""Reject stale official documents resurfaced as fresh RSS index hits.

A Google RSS publication timestamp can mean indexing/re-indexing, not the
underlying official notice's issuance date. Only deterministic historical-
document headings are excluded. Ambiguous years are held as review-unknown,
not presumed fresh or treated as proof that a source has zero new notices.
"""
from __future__ import annotations
import re
from datetime import datetime

HISTORIC_HEADING = re.compile(
    r"(?:^|[[:space:]])(20\d{2})년도?\s*"
    r".{0,85}?"
    r"(?:구매계획|구매실적|사업계획|사업보고서|공시자료|"
    r"경영공시|결산보고서|실적보고서|예산서|정기보고|"
    r"연차보고서|공공데이터|연구보고서|용역보고서|"
    r"운영계획|교육계획|통계연보)", re.I
)
# Python's re engine has no POSIX-style [:space:] classes.
HISTORIC_HEADING = re.compile(
    r"^\s*(?:\[(?:공지|공고|자료)\]\s*)?(20\d{2})년도?\s*.{0,85}?"
    r"(?:구매계획|구매실적|사업계획|사업보고서|공시자료|"
    r"경영공시|결산보고서|실적보고서|예산서|정기보고|"
    r"연차보고서|공공데이터|연구보고서|용역보고서|"
    r"운영계획|교육계획|통계연보)", re.I
)


def resurfaced_historical_original(title, retrieved_published, *, year_margin=2):
    """Return True only for a year-labeled historical official source document."""
    if not isinstance(title, str) or not isinstance(retrieved_published, datetime):
        return False
    if retrieved_published.tzinfo is None or retrieved_published.utcoffset() is None:
        return False
    m = HISTORIC_HEADING.search(title)
    if not m:
        return False
    year = int(m.group(1))
    return 2000 <= year <= retrieved_published.year - year_margin
