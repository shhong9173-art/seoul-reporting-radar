"""Source-first discovery of NEW link observations on real official listing pages.

Direct company and public filings are preferred to news-article keywords. A
newly seen link is NOT a newly released document and never a scoop. The first
successful collection initializes the baseline without generating false leads.
"""
from __future__ import annotations
import hashlib
from html.parser import HTMLParser
import json
import re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError

from scripts.primary_document_dossiers import (
    KST, ROOT, MAX_BYTES, safe_url, fetch_page, _NoRedirect, normalized
)

REGISTRY=ROOT/"data/primary_site_listing_watches.json"
OUTPUT=ROOT/"digests/primary_original_discovery_latest.json"
STATUS="official_listing_links_observed_not_verified_scoops"
MAX_SEEN=100
MAX_LINKS_PER_SOURCE=12
MAX_CANDIDATES=50

class _ListingCards(HTMLParser):
    """Pair a single detail link with its NEAREST short enclosing card.

    Real auction listings use a company name in a sibling heading and
    a generic "View Auction Details" anchor. Requiring the company's name
    in the anchor alone missed those original documents. A page-wide ancestor
    (multiple detail links) must never donate its company text to all links.
    """
    VOID={"area","base","br","col","embed","hr","img","input","link",
          "meta","param","source","track","wbr"}
    SKIP={"script","style","noscript","svg"}
    def __init__(self,detail_prefix):
        super().__init__(convert_charrefs=True)
        self.stack=[]
        self.results=[]
        self.detail_prefix=detail_prefix

    def handle_starttag(self,tag,attrs):
        if tag in self.VOID:return
        url=dict(attrs).get("href","") if tag=="a" else ""
        self.stack.append({"tag":tag,"text":[],"links":[url] if
                           isinstance(url,str) and
                           self.detail_prefix in url else [],
                           "skip":tag in self.SKIP})

    def handle_data(self,data):
        if self.stack and not any(x["skip"] for x in self.stack):
            self.stack[-1]["text"].append(data[:3000])

    def handle_endtag(self,tag):
        if not self.stack:return
        pos=next((i for i in range(len(self.stack)-1,-1,-1)
                  if self.stack[i]["tag"]==tag),None)
        if pos is None:return
        while len(self.stack)>pos:
            frame=self.stack.pop()
            caption=re.sub(r"\s+"," "," ".join(frame["text"])).strip()
            links=list(dict.fromkeys(frame["links"]))
            # Reject page-wide ancestors, overlong composite cards and
            # ambiguous blocks with multiple independent original links.
            if len(links)==1 and 3<=len(caption)<=500 and not frame["skip"]:
                self.results.append((links[0],caption[:320]))
            if self.stack and not frame["skip"]:
                parent=self.stack[-1]
                parent["text"].extend(frame["text"])
                parent["links"].extend(frame["links"])

def fetch_listing(url):
    if not safe_url(url):
        raise ValueError("disallowed_official_listing_url")
    request=Request(url,headers={
        "User-Agent":"IndustrialReporterSourceChecker/1.0 (+public-original-verification)",
        "Accept":"text/html,application/xhtml+xml",
    })
    with build_opener(_NoRedirect).open(request,timeout=14) as r:
        ctype=r.headers.get("Content-Type","").lower()
        if "html" not in ctype:
            raise ValueError("not_html_listing")
        body=r.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:
            raise ValueError("listing_too_large")
        return body.decode("utf-8",errors="replace")

def valid_targets(config):
    if (not isinstance(config,dict) or config.get("schemaVersion")!=1
        or not isinstance(config.get("watch"),list)
        or not 1<=len(config["watch"])<=8
        or not isinstance(config.get("trackedNames"),list)
        or not 1<=len(config["trackedNames"])<=45):
        raise ValueError("invalid_official_listing_registry")
    ids=set()
    for item in config["watch"]:
        if (not isinstance(item,dict) or
            not isinstance(item.get("id"),str)
            or not re.fullmatch("[a-z0-9-]{5,60}",item["id"])
            or item["id"] in ids or not safe_url(item.get("url"))
            or not isinstance(item.get("pathPrefix"),str)
            or item["pathPrefix"] not in ("/auction-detail/","/blog/")):
            raise ValueError("unsafe_listing_target")
        ids.add(item["id"])
    if any(not isinstance(v,str) or not 3<=len(v)<=45
           for v in config["trackedNames"]):
        raise ValueError("unsafe_company_selector")
    return config

def named(text,names):
    title=str(text or "").casefold()
    matches=[]
    for name in names:
        clean=name.casefold()
        if re.search(r"(?<![a-z])"+re.escape(clean)+r"(?![a-z])",title):
            if clean=="tesla":
                # NVIDIA "Tesla" is a GPU product family, not necessarily
                # Tesla, Inc. manufacturing/asset activity. A false-positive
                # equipment sale appeared in actual 2026-10-21 production.
                gpu=bool(re.search(
                    r"\b(?:nvidia|nvda)\s+tesla\b|"
                    r"\btesla\s+(?:gpu|v100|p100|k80|t4|accelerator)\b",title))
                automotive=bool(re.search(
                    r"\btesla\s*(?:,\s*)?(?:inc\b|motors\b|vehicles?\b|"
                    r"model\s+[s3xy]\b|gigafactory\b|factory\b|cars?\b|"
                    r"supercharger\b|energy\b)",title))
                if gpu and not automotive:
                    continue
            matches.append(name)
    return matches[:8]

def extract_original_event_fields(text,source_id):
    """Preserve short ORIGINAL-page phrases; never invent transaction impact.

    These are document observations, not a generated article, a court
    docket verification or a statement that the document was first published
    today. No private plans or asserted contract effects are implied.
    """
    if not isinstance(text,str) or len(text)<35:
        return []
    clean=re.sub(r"\\s+"," ",text).strip()
    extracted=[]
    def field(kind,regex,*,max_value=145,claim_scope="original_notice_text_only"):
        match=re.search(regex,clean,re.I)
        if not match:
            return
        value=re.sub(r"\\s+"," ",match.group(1)).strip(" :;.,")
        if 3<=len(value)<=max_value:
            excerpt=clean[max(0,match.start()-32):min(len(clean),match.end()+18)]
            extracted.append({
                "field":kind,"verbatimValue":value,
                "originalQuote":excerpt[:230],
                "claimScope":claim_scope,
                "notIndependentlyVerified":True,
            })
    if source_id in ("svd-past","svd-upcoming"):
        field("announced_auction_dates",
              r"\\bAuction Dates:\\s*(.{3,65}?)(?=\\s+Address:|\\s+Checkout:|\\s+Auctioneer Fee:|$)")
        field("listing_address",
              r"\\bAddress:\\s*(.{5,140}?)(?=\\s+Checkout:|\\s+Auctioneer Fee:|$)")
        field("posted_checkout_dates",
              r"\\bCheckout:\\s*(.{3,75}?)(?=\\s+Auctioneer Fee:|\\s+State Compliance:|$)")
    elif source_id=="ipgate-insights":
        field("plaintiff_identified_patent",
              r"\\b(EP\\s*[0-9][0-9\\s]{4,22}\\s*B1)\\b",
              claim_scope="plaintiff_statement_not_court_finding")
        field("plaintiff_identified_court",
              r"\\b((?:Munich Regional Court|Landgericht München I))\\b",
              claim_scope="plaintiff_statement_not_court_finding")
        # Licensing timelines are claims by the patent owner, NOT an
        # independently proven negotiation or a license status.
        field("plaintiff_stated_license_proposal_date",
              r"\\blicen[cs](?:e|ing).{0,120}?(September\\s+2021)\\b",
              claim_scope="one_sided_plaintiff_claim")
    return extracted


def public_source_followup_questions(source_id):
    if source_id in ("svd-past","svd-upcoming"):
        return [
            "경매업체 공개 원문에 적힌 매각 회차·반출일·로트 번호를 확인할 수 있는가?",
            "공항 운영기관의 공개 임대·시설 사용기록에 동일 격납고의 변경 내역이 있는가?",
            "회사 홍보팀이 해당 공개 경매의 실시 사실과 장비 처분 범위를 확인해 줄 수 있는가?",
        ]
    if source_id=="ipgate-insights":
        return [
            "원고 측에 공개 가능한 법원 사건번호·소장과 특정 특허번호가 있는가?",
            "독일 법원 공개 사건목록에서 접수와 심리 단계가 독립적으로 확인되는가?",
            "현대차·모비스 홍보팀이 원고의 공개 주장에 대해 확인 가능한 공식 입장을 제공하는가?",
        ]
    return ["공식 문서의 식별번호·공개일·대상 법인명이 무엇인가?"]


def read_previous(previous):
    if previous is None:
        return {},{}
    if (not isinstance(previous,dict) or previous.get("status")!=STATUS
        or not isinstance(previous.get("sources"),list)
        or not isinstance(previous.get("candidates"),list)):
        raise ValueError("corrupt_official_listing_baseline")
    states={}
    for s in previous["sources"]:
        if not isinstance(s,dict) or not isinstance(s.get("id"),str):
            raise ValueError("bad_prior_source_state")
        states[s["id"]]=s
    existing={}
    for row in previous["candidates"]:
        if (not isinstance(row,dict) or
            not isinstance(row.get("url"),str) or
            not safe_url(row["url"])):
            raise ValueError("unsafe_prior_source_link")
        existing[row["url"]]=row
    return states,existing

def discover(config,prior=None,*,now,listing_fetcher=fetch_listing,detail_fetcher=fetch_page):
    valid_targets(config)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timestamp_requires_timezone")
    stamp=now.astimezone(KST).isoformat(timespec="seconds")
    states,previous=read_previous(prior)
    outcome={};source_records=[]
    for site in config["watch"]:
        prior_state=states.get(site["id"],{})
        had_baseline=bool(prior_state.get("lastOkAt"))
        status={"id":site["id"],"url":site["url"],"topic":site["topic"],
                "lastOkAt":prior_state.get("lastOkAt"),
                "lastFailAt":prior_state.get("lastFailAt"),
                "failStreak":prior_state.get("failStreak",0),
                "checkedAt":stamp,"status":"source_unavailable",
                "linksWithMatchedNamedCompany":None,"documentPagesMatched":None,
                "baselineOnly":not had_baseline,
                "newLinksSincePriorSuccess":None}
        try:
            markup=listing_fetcher(site["url"])
            if not isinstance(markup,str) or len(markup)<100:
                raise ValueError("empty_official_listing")
            a=_ListingCards(site["pathPrefix"]);a.feed(markup)
            candidates=[]
            dedup=set()
            host=urlsplit(site["url"]).hostname
            for href,caption in a.results:
                link=urljoin(site["url"],href)
                parsed=urlsplit(link)
                if (parsed.hostname!=host or
                    not parsed.path.startswith(site["pathPrefix"]) or
                    not safe_url(link) or link in dedup):
                    continue
                names=named(caption,config["trackedNames"])
                if not names:
                    continue
                dedup.add(link)
                candidates.append((link,caption,names))
                if len(candidates)>=MAX_LINKS_PER_SOURCE:break
            matched_count=0;failed_details=0;new_count=0
            for link,caption,names in candidates:
                try:
                    details=detail_fetcher(link)
                    if not isinstance(details,str) or len(details)<35:
                        raise ValueError("empty_detail_original")
                    verified_names=[n for n in names if named(details,[n])]
                    if not verified_names:
                        failed_details+=1
                        continue
                    matched_count+=1
                    old=previous.get(link)
                    is_new=not old and had_baseline and prior_state.get("failStreak",0)==0
                    if is_new:new_count+=1
                    digest=hashlib.sha256(re.sub(r"\s+"," ",details).encode()).hexdigest()
                    outcome[link]={
                        "url":link,"title":caption[:220],
                        "sourceId":site["id"],
                        "companiesMentionedInListingAndOriginal":verified_names,
                        "firstSeenAt":(old or {}).get("firstSeenAt",stamp),
                        "lastSeenAt":stamp,
                        "detailContentSha256":digest,
                        "detailTextChangedSinceLastCheck":(
                            None if not old else
                            digest!=(old or {}).get("detailContentSha256")),
                        "newlyObservedAfterCleanBaseline":is_new,
                        "observedAfterSourceGap":bool(not old and
                                                    prior_state.get("failStreak",0)),
                        "originalPageRead":True,
                        "eventFieldsQuotedFromOriginal":extract_original_event_fields(
                            details,site["id"]),
                        "publicConfirmationQuestions":public_source_followup_questions(
                            site["id"]),
                        "companyActivityOrLegalOutcomeIndependentlyConfirmed":False,
                        "publishedAtVerified":False,
                        "factsComparedToPublisherArticle":False,
                        "domesticPriorCoverageChecked":False,
                        "confirmedExclusive":False,
                        "reporterStatus":"named_official_page_for_manual_first_source_review",
                    }
                except (OSError,HTTPError,URLError,ValueError,UnicodeError,TimeoutError):
                    failed_details+=1
            status.update(
                status=("checked_partial_details" if failed_details
                        else "listing_checked_not_exhaustive"),
                lastOkAt=stamp,failStreak=0,
                linksWithMatchedNamedCompany=len(candidates),
                documentPagesMatched=matched_count,
                documentPagesFailedOrUnmatched=failed_details,
                newLinksSincePriorSuccess=new_count)
        except (OSError,HTTPError,URLError,ValueError,UnicodeError,TimeoutError) as e:
            status.update(lastFailAt=stamp,
                          failStreak=int(status["failStreak"])+1,
                          errorType=type(e).__name__)
        source_records.append(status)
    # Preserve previously verified links on a transient source failure, but
    # never resurrect rows now rejected by stronger company-identity rules.
    # A stale NVIDIA Tesla GPU auction must not remain for 14 days.
    legacy_rejected=0
    for url,old in previous.items():
        if url in outcome:continue
        if not named(old.get("title",""),config["trackedNames"]):
            legacy_rejected+=1
            continue
        seen=old.get("lastSeenAt")
        try:dt=datetime.fromisoformat(seen)
        except (ValueError,TypeError):continue
        if dt.tzinfo and now-dt<timedelta(days=14):
            outcome[url]={**old,"notRecheckedThisRun":True,
                          "newlyObservedAfterCleanBaseline":False,
                          "confirmedExclusive":False}
    rows=sorted(outcome.values(),
                key=lambda x:(not x["newlyObservedAfterCleanBaseline"],
                              x["firstSeenAt"],x["url"]))[:MAX_CANDIDATES]
    return {
        "status":STATUS,"generatedAt":stamp,
        "sources":source_records,"sourcesAttempted":len(source_records),
        "sourcesChecked":sum(x["status"] in
                    ("listing_checked_not_exhaustive","checked_partial_details")
                    for x in source_records),
        "sourcesUnavailable":sum(x["status"]=="source_unavailable"
                    for x in source_records),
        "candidates":rows,"candidateCount":len(rows),
        "newlyObservedAfterBaseline":sum(x["newlyObservedAfterCleanBaseline"]
                                       for x in rows),
        "priorRowsRejectedByCurrentIdentityRules":legacy_rejected,
        "sourceCoverageExhaustive":False,"domesticNoPriorCoverageProved":False,
        "confirmedScoops":0,
        "warning":"공식 목록의 링크 첫 관측은 새로 공개된 문서 또는 미보도 단독의 증명이 아님. 회사명·원문 URL만 교차 확인했고, 본문 사실·선행보도·실제 사건 발생시점은 기자가 검증해야 함",
    }

def main():
    config=json.loads(REGISTRY.read_text(encoding="utf-8"))
    prior=json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else None
    result=discover(config,prior,now=datetime.now(KST))
    OUTPUT.parent.mkdir(exist_ok=True)
    tmp=OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    tmp.replace(OUTPUT)
    print("First-party page discovery:",result["sourcesChecked"],"/",
          result["sourcesAttempted"],"source lists checked,",
          result["candidateCount"],"named official links,",
          result["newlyObservedAfterBaseline"],"newly observed after baseline; scoops 0")

if __name__=="__main__":main()
