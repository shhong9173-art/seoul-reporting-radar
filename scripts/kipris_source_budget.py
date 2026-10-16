"""Fail-closed request ledger for *KIPRIS source* calls; never store keys/URLs.

Other workflows such as deep history and claim lookup use separate API calls:
the ledger is NOT an authoritative KIPRIS account balance.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone,timedelta
from pathlib import Path

KST=timezone(timedelta(hours=9))

class SourceRequestBudgetExhausted(RuntimeError):
    pass

class SourceRequestMeter:
    def __init__(self,path,*,now=None,run_limit=28,monthly_limit=650,fetch=None):
        if fetch is None:raise ValueError("explicit_fetch_required")
        self.path=Path(path)
        self.now=now or datetime.now(KST)
        self.month=self.now.astimezone(KST).strftime("%Y-%m")
        if not 1<=run_limit<=100 or not 1<=monthly_limit<=1200:
            raise ValueError("invalid_budgets")
        self.run_limit=run_limit
        self.monthly_limit=monthly_limit
        self.fetch=fetch
        self.this_run=0
        self.monthly_count=0
        self.data=None
        self.provider_probe_override=False
        self.provider_result_code=None
        self.next_provider_probe_at=None
        if self.path.exists():
            try:
                data=json.loads(self.path.read_text(encoding="utf-8"))
                if (not isinstance(data,dict) or
                    data.get("status")!="source_request_counted_not_account_quota" or
                    not isinstance(data.get("month"),str) or
                    type(data.get("sourceRequestsCounted")) is not int or
                    data["sourceRequestsCounted"]<0 or
                    data["sourceRequestsCounted"]>100000):
                    raise ValueError("corrupt_budget_file")
                # Provider response 22 has been observed in this connected
                # account; the provider has not given us its meaning.
                # Preserve a bounded cooldown across monthly ledger rollover.
                if data.get("lastProviderResultCode") is not None:
                    if data["lastProviderResultCode"]!="22":
                        raise ValueError("unrecognized_provider_code")
                    until=data.get("nextProviderProbeAt")
                    if not isinstance(until,str):
                        raise ValueError("invalid_backoff")
                    try:
                        stamp=datetime.fromisoformat(until)
                        if stamp.utcoffset() is None:
                            raise ValueError("naive_backoff")
                    except (TypeError,ValueError):
                        raise ValueError("invalid_backoff")
                    self.provider_result_code="22"
                    self.next_provider_probe_at=stamp
                self.data=data
                if data["month"]==self.month:
                    self.monthly_count=data["sourceRequestsCounted"]
            except (OSError,ValueError,TypeError):
                # Do not reset a corrupted same-month ledger and overspend.
                raise SourceRequestBudgetExhausted("budget_ledger_invalid_manual_review")
    def public(self):
        return {"month":self.month,
                "status":"source_request_counted_not_account_quota",
                "sourceRequestsCounted":self.monthly_count,
                "thisRunAttempted":self.this_run,
                "runLimit":self.run_limit,
                "monthlySourceLimit":self.monthly_limit,
                "includesDeepAndClaimsWorkflows":False,
                "officialProviderUsageVerified":False,
                "lastProviderResultCode":self.provider_result_code,
                "nextProviderProbeAt":(
                    self.next_provider_probe_at.isoformat(timespec="seconds")
                    if self.next_provider_probe_at else None),
                "providerCodeMeaningVerified":False,
                "providerBackoffIsAccountQuotaEvidence":False,
                "note":"Source endpoint attempt ledger only; this is NOT actual account remaining calls or API error-code interpretation."}
    def persist(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix(self.path.suffix+".tmp")
        tmp.write_text(json.dumps(self.public(),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        tmp.replace(self.path)
    def should_probe(self,force=False):
        """A manual probe may bypass cooldown, never source call limits."""
        if force:
            return True
        return (self.next_provider_probe_at is None or
                self.now>=self.next_provider_probe_at)

    def record_provider_code(self,code):
        """Temporarily reduce repeat requests after repeated opaque code 22."""
        if code!="22":
            return False
        self.provider_result_code="22"
        self.next_provider_probe_at=self.now+timedelta(hours=72)
        self.persist()
        return True

    def clear_provider_backoff(self):
        self.provider_result_code=None
        self.next_provider_probe_at=None
        self.persist()

    def get(self,url):
        if not self.should_probe(force=self.provider_probe_override):
            raise SourceRequestBudgetExhausted("provider_22_probe_cooldown")
        if self.this_run>=self.run_limit or self.monthly_count>=self.monthly_limit:
            raise SourceRequestBudgetExhausted("source_request_budget_exhausted")
        # Reserve BEFORE network, even when a request times out/returns code 22.
        self.this_run+=1
        self.monthly_count+=1
        self.persist()
        return self.fetch(url)
