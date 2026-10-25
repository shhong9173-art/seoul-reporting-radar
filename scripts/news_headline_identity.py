"""News headline identity and obvious sports-name disambiguation.

Keep article content on both sides of hyphens/pipes; remove only a trailing
publisher equal to the verified feed source or a small trusted label list.
This is editorial ingestion filtering, never negative proof of press coverage.
"""
import re

KNOWN_PUBLISHERS = frozenset({
    "연합뉴스","연합뉴스TV","뉴스1","뉴시스","한국경제","매일경제",
    "서울경제","전자신문","이데일리","머니투데이","더팩트",
    "조선비즈","조선일보","동아일보","한겨레","경향신문",
    "KBS 뉴스","MBC 뉴스","SBS 뉴스","YTN","JTBC","중앙일보",
    "세계일보","국민일보","오토타임즈","모터그래프",
})
SEPARATOR = re.compile(r"\s+[-|｜]\s+")
SPORT = re.compile(
    r"프로농구|프로야구|KBO|KBL|농구단|야구단|"
    r"챔피언결정전|준플레이오프|플레이오프|"
    r"타이거즈|피버스|농구|야구|홈런|타점|득점|리바운드|"
    r"쿼터|역전승|[0-9]+연승|[0-9]+연패", re.I
)
SPORT_TEAMS = re.compile(
    r"기아\s*타이거즈|KIA\s*Tigers|현대모비스\s*피버스|"
    r"모비스\s*농구|"
    r"현대캐피탈\s*스카이워커스|"
    # Sponsored golf events and an esports team carrying a beat brand
    # (2026-10-25 data.json: ~25 '완성차' rows were golf results).
    r"제네시스\s*(?:챔피언십|인비테이셔널|스코티시\s*오픈)|"
    r"KPGA|KLPGA|DP\s*월드\s*투어|"
    r"디플러스\s*기아|Dplus\s*KIA|LCK|롤드컵|돌드컵", re.I
)
AUTO_CONTEXT = re.compile(
    r"자동차|완성차|전기차|배터리|모빌리티|차량|"
    r"자동차부품|공장|리콜|신차|판매량|생산량|주행|부품|"
    r"미래차|배출가스|차종|제네시스|전동화",re.I
)


def normalize_title(title, source_name=""):
    title = " ".join(str(title or "").split())
    source = " ".join(str(source_name or "").split())
    # Only strip a final suffix after a space-surrounded separator.
    # A separator inside a real headline must never remove its right half.
    for match in reversed(list(SEPARATOR.finditer(title))):
        suffix = title[match.end():].strip()
        if not suffix:
            continue
        if suffix.casefold() == source.casefold() or suffix in KNOWN_PUBLISHERS:
            return title[:match.start()].strip().casefold()
        break
    return title.casefold()


def obvious_sports_homonym(title, summary=""):
    title = str(title or "")
    summary = str(summary or "")
    if SPORT_TEAMS.search(title):
        return True
    # Require explicit sports action and a company name. Generic "팀" alone
    # is not a sports marker and must not remove industrial labour reporting.
    company = re.search(r"현대모비스|기아|KIA\b|모비스", title, re.I)
    if company and SPORT.search(title) and not AUTO_CONTEXT.search(title):
        return True
    # The feed title may be short, so use the summary only when both
    # company and sport are explicit in the headline.
    return False
