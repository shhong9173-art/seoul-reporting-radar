"""Bounded public article review. Context matches are leads, never findings of guilt.

Only explicit article containers/NewsArticle.articleBody are read; search snippets,
navigation and whole-page text are never substitutes. Store a short excerpt + hash.
"""
from __future__ import annotations
import hashlib
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin

VERSION = "executive_article/v1"
MAX_BYTES = 1_500_000
HOSTS = ("naver.com", "inews24.com", "yna.co.kr", "yonhapnewstv.co.kr", "newsis.com",
         "news1.kr", "newsworks.co.kr", "hani.co.kr", "khan.co.kr", "chosun.com",
         "donga.com", "joongang.co.kr", "hankyung.com", "mk.co.kr", "sedaily.com",
         "edaily.co.kr", "mt.co.kr", "etnews.com", "koreatimes.co.kr")
BODY_IDS = {"dic_area", "newsct_article", "articleBody", "article-body", "article_body",
            "article-view-content-div", "articleBodyContents", "newsView", "article_text"}
BODY_CLASSES = {"article-body", "article_body", "article-view-content-div", "article_txt", "article-text", "article-cont"}
SKIP = {"script", "style", "nav", "aside", "footer", "header", "noscript", "button", "form", "figure", "figcaption"}
VOID = {"br", "img", "meta", "link", "hr", "input", "source", "wbr", "embed"}
OUTCOME = re.compile(r"무죄|무혐의|혐의\s*없|불기소|불송치|누명|다른\s*사람|동명이인|기소.{0,8}(?:아니|않)|혐의.{0,8}부인")
ROLE = r"(?:전\s*|현\s*)?(?:대표(?:이사)?|회장|부회장|사장|부사장|이사|감사|장관|차관|교수|위원장|원장)"


def public_host(host, resolve=None):
    """목록 밖 언론사(11-05 실제: 기사 23건 중 16건이 목록 밖이라 unsupported_source — 투데이신문·뉴스핌·노컷뉴스 등)는
    이름이 공인 IP로만 풀릴 때 읽는다. IP 직접 입력·내부망·루프백·링크로컬·사설 주소는 막는다(요청할 때마다·리다이렉트마다 다시 본다)."""
    host = (host or "").strip(".").lower()
    if not host or "." not in host or host.endswith((".local", ".internal", ".localhost", ".test", ".invalid", ".example")):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    try:
        infos = (resolve or socket.getaddrinfo)(host, 443, proto=socket.IPPROTO_TCP)
        addrs = {str(i[4][0]).split("%")[0] for i in infos}
        return bool(addrs) and all(ipaddress.ip_address(a).is_global for a in addrs)
    except (OSError, ValueError, UnicodeError):
        return False


def allowed_url(url, resolve=None):
    try:
        u = urlsplit(url)
        if not (u.scheme in ("http", "https") and not u.username and not u.password and u.port in (None, 80, 443)):
            return False
        if any(u.hostname == h or (u.hostname or "").endswith("." + h) for h in HOSTS):
            return True
        return public_host(u.hostname, resolve)
    except (ValueError, TypeError):
        return False


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.parts, self.json_parts, self.scripts = [], [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        parent = self.stack[-1] if self.stack else ("", False, False, False)
        selected = a.get("id") in BODY_IDS or bool(set(a.get("class", "").split()) & BODY_CLASSES) or a.get("itemprop") == "articleBody"
        state = (tag, parent[1] or selected, parent[2] or tag in SKIP,
                 tag == "script" and a.get("type", "").lower() == "application/ld+json")
        if tag not in VOID:
            self.stack.append(state)
        if tag in ("p", "br", "div") and parent[1] and not parent[2]:
            self.parts.append("\n")
        if state[3]:
            self.json_parts = []

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                if self.stack[i][3]:
                    self.scripts.append("".join(self.json_parts))
                if self.stack[i][1] and tag in ("p", "div"):
                    self.parts.append("\n")
                del self.stack[i:]
                break

    def handle_data(self, text):
        if self.stack and self.stack[-1][3]:
            self.json_parts.append(text)
        elif self.stack and self.stack[-1][1] and not self.stack[-1][2]:
            self.parts.append(text)


def extract_article(raw):
    p = ArticleParser()
    p.feed(raw)
    body = "".join(p.parts).strip()
    method = "article_container"
    if not body:
        def bodies(obj):
            if isinstance(obj, list):
                for x in obj:
                    yield from bodies(x)
            elif isinstance(obj, dict):
                types = obj.get("@type", [])
                types = [types] if isinstance(types, str) else types
                if obj.get("isAccessibleForFree") not in (False, "false") and any(t in ("NewsArticle", "Article", "ReportageNewsArticle") for t in types) and isinstance(obj.get("articleBody"), str):
                    yield obj["articleBody"]
                if "@graph" in obj:
                    yield from bodies(obj["@graph"])
        candidates = []
        for s in p.scripts:
            try:
                candidates.extend(bodies(json.loads(s)))
            except (ValueError, TypeError):
                pass
        if len(candidates) == 1:
            body, method = candidates[0], "newsarticle_jsonld"
    body = re.sub(r"[ \t\r]+", " ", body).strip()
    return {"status": "ok", "body": body, "method": method} if len(body) >= 80 else {"status": "body_missing"}


def fetch_article(url, *, get=None, resolve=None):
    if get is None:
        import requests
        get = requests.get
    try:
        for _ in range(3):
            if not allowed_url(url, resolve):
                return {"status": "unsupported_source"}
            with get(url, timeout=(4, 8), allow_redirects=False, stream=True,
                     headers={"User-Agent": "Mozilla/5.0 (compatible; ReporterEvidence/1.0)"}) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, r.headers.get("Location", ""))
                    continue
                if r.status_code != 200:
                    return {"status": "http_error", "httpStatus": r.status_code}
                if "html" not in r.headers.get("Content-Type", "").lower():
                    return {"status": "unsupported_content"}
                chunks, size = [], 0
                for chunk in r.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        return {"status": "too_large"}
                    chunks.append(chunk)
                raw = b"".join(chunks)
                encoding = r.encoding
                if not encoding or encoding.lower() == "iso-8859-1":
                    m = re.search(br'charset=["\s]*([a-zA-Z0-9_-]+)', raw[:10000])
                    encoding = m.group(1).decode() if m else "utf-8"
                return {**extract_article(raw.decode(encoding, errors="replace")), "url": url}
        return {"status": "redirect_limit"}
    except Exception as e:
        return {"status": "fetch_failed", "error": type(e).__name__}


def mention(text, word):
    # Company prefixes (GS/GS리테일, LS/LS전선) are not identity evidence.
    return bool(word and re.search(r"(?<![가-힣A-Za-z0-9])" + re.escape(word) + r"(?=$|[\s,·()㈜]|[이가은는의를와과](?:\s|$))", text))


def assess(article, name, anchors, incident):
    out = {"version": VERSION, "status": article.get("status", "fetch_failed")}
    if article.get("url"):
        out["url"] = article["url"]
    if out["status"] != "ok":
        return out
    body = article.get("body", "")
    out.update(bodyHash=hashlib.sha256(body.encode()).hexdigest(), bodyLength=len(body), method=article.get("method"))
    # No whole-document co-occurrence, cross-paragraph joins, or search-snippet fallback.
    sentences = [s.strip() for s in re.split(r"[\n.!?。]+", body) if s.strip()]
    contexts = [s for s in sentences if mention(s, name) and any(mention(s, a) for a in anchors)]
    if any(OUTCOME.search(s) for s in contexts):
        out["status"] = "outcome_requires_review"
        return out
    for s in contexts:
        # Require explicit name + company + role in a short phrase, followed by event words.
        for org in anchors:
            patterns = (r"(?<![가-힣A-Za-z0-9])" + re.escape(name) + r"\s+(?:전\s*|현\s*)?" + re.escape(org) + r"\s*" + ROLE,
                        r"(?<![가-힣A-Za-z0-9])" + re.escape(org) + r"\s*(?:전\s*|현\s*)?" + ROLE + r"\s+" + re.escape(name))
            for pattern in patterns:
                m = re.search(pattern, s)
                if not m:
                    continue
                tail = s[m.end():m.end() + 100]
                # Speakers, reporters, investigators and third-party allegations are not subjects.
                if re.search(r"[\"“「]|에\s*따르면|밝혔|말했|지적했|설명했|피해자|고발했|수사했", tail):
                    continue
                event = incident.search(tail)
                if event and not re.search(r"[가-힣]{2,4}\s*(?:씨|대표|회장|사장|이사|장관)|[을를]\s|[가-힣]{2,4}[이가은는의]\s", tail[:event.start()]):
                    out.update(status="context_linked", excerpt=s[max(0, m.start()):m.end() + event.end()][:120],
                               organization=org, eventTerm=event.group(0))
                    return out
    out["status"] = "context_unconfirmed"
    return out


def context_key(name, anchors):
    return hashlib.sha256(json.dumps([name, sorted(set(anchors))], ensure_ascii=False).encode()).hexdigest()


class Reviewer:
    def __init__(self, fetch=fetch_article, budget=30, priority=()):
        self.fetch, self.remaining, self.cache = fetch, budget, {}
        self.priority = set(priority)

    def review(self, url, name, anchors, incident, stamp):
        if url not in self.cache:
            if self.remaining <= 0 or (url not in self.priority and self.remaining <= len(self.priority)):
                return {"version": VERSION, "status": "budget_exhausted", "checkedAt": stamp, "contextKey": context_key(name, anchors)}
            self.remaining -= 1
            self.priority.discard(url)
            try:
                self.cache[url] = self.fetch(url)
            except Exception as e:
                self.cache[url] = {"status": "fetch_failed", "error": type(e).__name__}
        return {**assess(self.cache[url], name, anchors, incident), "checkedAt": stamp, "contextKey": context_key(name, anchors)}
