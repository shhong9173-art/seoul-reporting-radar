"""Deduplicate and prioritize verified international-news *headlines* BEFORE translation.

Translation is a presentation step and not independent sourcing or a scoop.
Cached translations only apply when original URL, title AND summary match.
"""
from concurrent.futures import ThreadPoolExecutor
import re


def norm_title(title):
    return re.sub(r"\s+"," ",str(title or "").strip()).casefold()


def shortlist(raw,*,limit=40):
    if not isinstance(raw,list) or not 1<=limit<=80:
        raise ValueError("invalid_global_shortlist")
    # Prefer the newest exact headline, then rank by public source-linked score.
    ranked=sorted((x for x in raw if isinstance(x,dict)
        and isinstance(x.get("title"),str) and x.get("title")
        and isinstance(x.get("url"),str) and x["url"].startswith("https://")
        and isinstance(x.get("published"),str)),
        key=lambda x:x["published"],reverse=True)
    seen=set()
    unique=[]
    for x in ranked:
        key=norm_title(x["title"])
        if key in seen:continue
        seen.add(key)
        unique.append(x)
    return sorted(unique,key=lambda x:(
        x.get("globalScore",0),x["published"]),reverse=True)[:limit]


# AI 번역 규칙(프롬프트·매체 이름 떼기)을 바꾸면 올린다 — 예전 규칙으로 만든 번역은 다시 번역한다(11-01: v1 번역에 매체 이름·없는 사실이 섞임).
AI_TRANSLATION_VERSION=2


def same_text_identity(new,old):
    return (isinstance(old,dict) and
        all(new.get(k)==old.get(k) for k in ("title","url","summary")) and
        isinstance(old.get("koTitle"),str) and old["koTitle"].strip() and
        # 보조 번역기(MyMemory) 결과는 다시 쓰지 않고 다음 실행에 주 번역기로 다시 번역한다(11-01: 품질이 낮았다)
        (old.get("translationStatus") in ("translated","already_ko") or
         (old.get("translationStatus")=="translated_ai" and old.get("translationVersion")==AI_TRANSLATION_VERSION)) and
        isinstance(old.get("koSummary"),str))


def translate_selected(rows,translator,*,previous=None,workers=3):
    if not callable(translator) or not 1<=workers<=4 or not isinstance(rows,list):
        raise ValueError("invalid_translation_task")
    previous=previous if isinstance(previous,list) else []
    cache={x.get("url"):x for x in previous
        if isinstance(x,dict) and isinstance(x.get("url"),str)}
    def translate_one(row):
        out=dict(row)
        old=cache.get(out.get("url"))
        if same_text_identity(out,old):
            for field in ("koTitle","koSummary","translationStatus","summaryTranslationStatus","translationVersion"):
                if field in old:out[field]=old[field]
            out["translationCacheUsed"]=True
            return out
        try:
            ko_title,title_status=translator(out["title"])
            if title_status=="translation_failed" or not ko_title:
                return None
            summary=(out.get("summary") or "")[:900]
            # 본문 설명이 없는 항목(구글 뉴스는 제목뿐)은 요약을 번역하지 않는다 — 제목 번역을 요약처럼 되풀이하지 않게
            ko_summary,summary_status=translator(summary) if summary.strip() else ("","no_summary")
        except Exception:
            return None
        out["koTitle"]=ko_title
        out["koSummary"]=ko_summary if summary_status!="translation_failed" else ""
        out["translationStatus"]=title_status
        if title_status=="translated_ai":out["translationVersion"]=AI_TRANSLATION_VERSION
        out["summaryTranslationStatus"]=summary_status
        out["translationCacheUsed"]=False
        return out
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="global-translate") as pool:
        all_rows=list(pool.map(translate_one,rows))
    return [x for x in all_rows if x is not None]


# 한국어 요약(11-01 기자 요청: 외신을 한국어로 요약·번역). 매체 RSS 본문 발췌(articleText)가 있는 항목만 — 본문이 없으면 요약하지 않는다.
# 같은 주소·같은 제목·같은 요약 규칙 버전이면 지난 요약을 다시 쓴다. 영어 본문(articleText)은 결과에서 지운다(공개 저장소에 원문을 싣지 않게).
SUMMARY_VERSION=1


def summarize_selected(rows,summarizer,*,previous=None,workers=2):
    if not callable(summarizer) or not 1<=workers<=4 or not isinstance(rows,list):
        raise ValueError("invalid_summary_task")
    cache={x.get("url"):x for x in (previous if isinstance(previous,list) else [])
        if isinstance(x,dict) and isinstance(x.get("url"),str)}
    def one(row):
        out=dict(row)
        text=str(out.pop("articleText","") or "")
        old=cache.get(out.get("url"))
        if (isinstance(old,dict) and old.get("title")==out.get("title") and old.get("summaryTranslationStatus")=="summarized_ai"
                and old.get("summaryVersion")==SUMMARY_VERSION and isinstance(old.get("koSummary"),str) and old["koSummary"].strip()):
            out.update(koSummary=old["koSummary"],summaryTranslationStatus="summarized_ai",summaryVersion=SUMMARY_VERSION)
            return out
        if text.strip() and not out.get("koSummary"):
            try:
                ko=summarizer(out.get("title",""),text)
            except Exception:
                ko=""
            if ko:
                out.update(koSummary=ko,summaryTranslationStatus="summarized_ai",summaryVersion=SUMMARY_VERSION)
        return out
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="global-summary") as pool:
        return list(pool.map(one,rows))
