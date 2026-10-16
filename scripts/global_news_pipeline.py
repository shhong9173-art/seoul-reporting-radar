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


def same_text_identity(new,old):
    return (isinstance(old,dict) and
        all(new.get(k)==old.get(k) for k in ("title","url","summary")) and
        isinstance(old.get("koTitle"),str) and old["koTitle"].strip() and
        old.get("translationStatus") in ("translated","translated_fallback","already_ko") and
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
            for field in ("koTitle","koSummary","translationStatus","summaryTranslationStatus"):
                if field in old:out[field]=old[field]
            out["translationCacheUsed"]=True
            return out
        try:
            ko_title,title_status=translator(out["title"])
            if title_status=="translation_failed" or not ko_title:
                return None
            ko_summary,summary_status=translator((out.get("summary") or "")[:900])
        except Exception:
            return None
        out["koTitle"]=ko_title
        out["koSummary"]=ko_summary if summary_status!="translation_failed" else ""
        out["translationStatus"]=title_status
        out["summaryTranslationStatus"]=summary_status
        out["translationCacheUsed"]=False
        return out
    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="global-translate") as pool:
        all_rows=list(pool.map(translate_one,rows))
    return [x for x in all_rows if x is not None]
