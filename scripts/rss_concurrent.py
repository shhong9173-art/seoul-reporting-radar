"""Deterministic bounded-concurrency wrapper for independent public RSS feeds.

Parallelize latency, not publisher trust. Workers never alter newspaper facts;
the existing per-query parser and news publication threshold still decide.
"""
from concurrent.futures import ThreadPoolExecutor


def collect_feeds(feeds, global_feeds, parser, *, on_error, workers=3):
    if not callable(parser) or not callable(on_error):
        raise ValueError("parser_and_error_callback_required")
    if not isinstance(workers,int) or not 1<=workers<=4:
        raise ValueError("unsafe_parallelism")
    jobs=[(cat,query,False,"") for cat,query in feeds]
    jobs.extend(("글로벌",query,True,hint) for hint,query in global_feeds)
    if not jobs or len(jobs)>60:
        raise ValueError("invalid_feed_jobs")

    def run(job):
        category,query,is_global,hint=job
        try:
            rows=parser(category,query,global_feed=is_global,source_hint=hint)
            if not isinstance(rows,list):
                raise TypeError("rss_parser_result_not_list")
            return rows
        except Exception as exc:
            # Bug or unexpected parser exception: preserve evidence of failure.
            # Never expose the query, feed URL, exception message or API tokens.
            on_error(category,is_global,type(exc).__name__)
            return []

    with ThreadPoolExecutor(max_workers=workers,thread_name_prefix="rss-news") as pool:
        ordered=list(pool.map(run,jobs))
    domestic=[]
    global_items=[]
    for i,rows in enumerate(ordered):
        if i<len(feeds):domestic.extend(rows)
        else:global_items.extend(rows)
    return domestic,global_items
