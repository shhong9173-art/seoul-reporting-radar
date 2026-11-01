"""KIPRIS Plus로 보내는 모든 요청을 한 장부에 센다(키·주소·응답 본문은 저장하지 않음).

- 특허 공보(patent_source)·과거 제목 검색(patent_deep)·청구항(patent_claims)·상표(trademark)가
  같은 인증키를 쓴다. 용도별로 따로 세던 장부는 공보 검색만 셌기 때문에 나머지 호출이 빠졌다.
- 요청을 보내기 전에 1건을 먼저 적고 저장한다(실패·시간초과·코드 22도 1건).
- 이 저장소가 보낸 요청만 센다. KIPRIS Plus 계정의 실제 사용량이 아니다
  (다른 곳에서 같은 키를 쓰거나 이 장부가 생기기 전 호출은 빠진다).
- KIPRIS Plus 무료 한도는 매월 1,000회(매월 1일 초기화, 서비스 수수료 안내). 여유를 두고
  월 900회에서 멈추고, 묶음별 상한(특허 700·상표 180·진단 20)을 둔다.
- 제공기관 응답 코드 22를 받으면 그 묶음(특허/상표/진단)이 72시간 쉰다. 코드의 뜻은
  제공기관이 밝히지 않았으므로 '월 한도 초과'로 단정하지 않는다. 서비스별 신청 문제일 수도
  있어 한 묶음의 22로 다른 묶음을 막지 않는다(묶음당 72시간에 1건만 더 쓴다).
  특허 묶음은 기존 특허 공보 장부의 대기 시각도 함께 따른다.
- 장부 파일이 깨졌으면 0으로 되돌리지 않고 멈춘다(같은 달 초과 방지).
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kipris_source_budget import SourceRequestBudgetExhausted

KST = timezone(timedelta(hours=9))
PATH = "digests/kipris_account_ledger_latest.json"
LEGACY_PATH = "digests/kipris_source_request_budget_latest.json"
STATUS = "repository_requests_counted_not_account_quota"
MONTHLY_LIMIT = 900
# 11-01: 상표 감시에 석유화학·정유 6곳(34곳, 실행당 약 34~36회 × 월 최대 5번 월요일)을 더해 상표 150→180, 특허 730→700.
GROUP_LIMITS = {"patent": 700, "trademark": 180, "diagnostic": 20}
PURPOSES = {
    "patent_source": "patent",
    "patent_deep": "patent",
    "patent_claims": "patent",
    "trademark": "trademark",
    "diagnostic": "diagnostic",
}
COOLDOWN = timedelta(hours=72)
PACE_SECONDS = 0.2
CODE = re.compile(rb"<resultCode>\s*([A-Za-z0-9_-]{1,12})\s*</resultCode>")
SAFE_CATEGORIES = {"request_limit_reported", "access_denied_reported",
                   "key_not_registered_reported", "key_expired_reported",
                   "unrecognized_provider_message"}


class KiprisBudgetStop(SourceRequestBudgetExhausted):
    """No network request was made. ``reason`` is a short safe label."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _stamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid_timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("naive_timestamp")
    return parsed


def provider_code(raw):
    """resultCode from a KIPRIS XML reply, or None (body is never kept)."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8", "ignore")
    if not isinstance(raw, (bytes, bytearray)):
        return None
    hit = CODE.search(bytes(raw[:4000]))
    return hit.group(1).decode() if hit else None


class KiprisAccountLedger:
    def __init__(self, path=PATH, *, now=None, legacy_path=LEGACY_PATH,
                 monthly_limit=MONTHLY_LIMIT, group_limits=None, sleep=time.sleep):
        self.path = Path(path)
        self.legacy_path = Path(legacy_path) if legacy_path else None
        self.now = now or datetime.now(KST)
        self.month = self.now.astimezone(KST).strftime("%Y-%m")
        self.monthly_limit = monthly_limit
        self.group_limits = dict(group_limits or GROUP_LIMITS)
        if not 1 <= monthly_limit <= 1000 or sum(self.group_limits.values()) > monthly_limit:
            raise ValueError("invalid_limits")
        self.sleep = sleep
        self.by_purpose = {name: 0 for name in PURPOSES}
        self.this_run = 0
        self.cooldowns = {}
        self.last_success_at = {}
        self._load()

    # ---------- state ----------
    def _load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(data, dict) or data.get("status") != STATUS
                    or not isinstance(data.get("month"), str)
                    or not isinstance(data.get("byPurpose"), dict)):
                raise ValueError("corrupt_ledger")
            counts = {}
            for name, value in data["byPurpose"].items():
                if name not in PURPOSES or type(value) is not int or not 0 <= value <= 100000:
                    raise ValueError("corrupt_ledger")
                counts[name] = value
            cooldowns = data.get("providerCooldown") or {}
            if not isinstance(cooldowns, dict):
                raise ValueError("corrupt_ledger")
            for group, row in cooldowns.items():
                if group not in self.group_limits or not isinstance(row, dict):
                    raise ValueError("corrupt_ledger")
                if row.get("lastResultCode") != "22":
                    raise ValueError("unrecognized_provider_code")
                purpose = row.get("lastPurpose")
                category = row.get("lastMessageCategory")
                self.cooldowns[group] = {
                    "lastResultCode": "22",
                    "lastPurpose": purpose if purpose in PURPOSES else None,
                    "lastMessageCategory": category if category in SAFE_CATEGORIES else None,
                    "lastResponseAt": (_stamp(row["lastResponseAt"]).isoformat(timespec="seconds")
                                       if row.get("lastResponseAt") else None),
                    "nextProbeAt": _stamp(row.get("nextProbeAt")).isoformat(timespec="seconds"),
                }
            success = data.get("lastSuccessAt") or {}
            if not isinstance(success, dict):
                raise ValueError("corrupt_ledger")
            for group, value in success.items():
                if group not in self.group_limits:
                    raise ValueError("corrupt_ledger")
                self.last_success_at[group] = _stamp(value).isoformat(timespec="seconds")
            if data["month"] == self.month:
                self.by_purpose.update(counts)
        except (OSError, ValueError, TypeError):
            # Never reset a damaged same-month ledger and overspend.
            raise KiprisBudgetStop("ledger_invalid_manual_review")

    def legacy_next_probe_at(self):
        """Cooldown kept by the older patent source ledger, if any."""
        if not self.legacy_path or not self.legacy_path.exists():
            return None
        try:
            data = json.loads(self.legacy_path.read_text(encoding="utf-8"))
            value = data.get("nextProviderProbeAt") if isinstance(data, dict) else None
            return _stamp(value) if value else None
        except (OSError, ValueError, TypeError):
            raise KiprisBudgetStop("legacy_ledger_invalid_manual_review")

    def wait_until(self, group):
        stamps = []
        if group in self.cooldowns:
            stamps.append(_stamp(self.cooldowns[group]["nextProbeAt"]))
        if group == "patent":
            legacy = self.legacy_next_probe_at()
            if legacy:
                stamps.append(legacy)
        return max(stamps) if stamps else None

    def total(self):
        return sum(self.by_purpose.values())

    def group_used(self, group):
        return sum(v for k, v in self.by_purpose.items() if PURPOSES[k] == group)

    def remaining(self, purpose):
        group = PURPOSES[purpose]
        return max(0, min(self.monthly_limit - self.total(),
                          self.group_limits[group] - self.group_used(group)))

    def should_probe(self, purpose, force=False):
        if force:
            return True
        until = self.wait_until(PURPOSES[purpose])
        return until is None or self.now >= until

    def public(self):
        waits = {}
        for group in self.group_limits:
            until = self.wait_until(group)
            if until:
                waits[group] = until.isoformat(timespec="seconds")
        return {
            "month": self.month,
            "status": STATUS,
            "counted": self.total(),
            "monthlyLimit": self.monthly_limit,
            "byPurpose": dict(self.by_purpose),
            "groupLimits": dict(self.group_limits),
            "groupUsed": {g: self.group_used(g) for g in self.group_limits},
            "thisRunAttempted": self.this_run,
            "providerCooldown": {g: dict(row) for g, row in self.cooldowns.items()},
            "effectiveNextProbeAt": waits,
            "providerCodeMeaningVerified": False,
            "lastSuccessAt": dict(self.last_success_at),
            "officialAccountUsageVerified": False,
            "freeTierNote": "KIPRIS Plus 무료: 매월 1,000회, 매월 1일 초기화(서비스 수수료 안내). 900에서 멈춤.",
            "note": "이 저장소 작업이 보낸 요청 수. 계정 실제 사용량 아님(장부 이전·다른 곳 호출은 빠짐).",
        }

    def persist(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.public(), ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        tmp.replace(self.path)

    # ---------- requests ----------
    def reserve(self, purpose, *, force=False):
        if purpose not in PURPOSES:
            raise ValueError("unknown_purpose")
        if not self.should_probe(purpose, force=force):
            raise KiprisBudgetStop("provider_22_cooldown")
        if self.total() >= self.monthly_limit:
            raise KiprisBudgetStop("monthly_limit_reached")
        group = PURPOSES[purpose]
        if self.group_used(group) >= self.group_limits[group]:
            raise KiprisBudgetStop(group + "_limit_reached")
        if self.this_run:
            self.sleep(PACE_SECONDS)
        self.by_purpose[purpose] += 1
        self.this_run += 1
        self.persist()

    def record_provider_code(self, code, purpose, category=None):
        """22: that group waits 72h. 00: that group's own wait is cleared."""
        if purpose not in PURPOSES:
            raise ValueError("unknown_purpose")
        group = PURPOSES[purpose]
        stamp = self.now.isoformat(timespec="seconds")
        if code == "22":
            self.cooldowns[group] = {
                "lastResultCode": "22",
                "lastPurpose": purpose,
                "lastMessageCategory": category if category in SAFE_CATEGORIES else None,
                "lastResponseAt": stamp,
                "nextProbeAt": (self.now + COOLDOWN).isoformat(timespec="seconds"),
            }
            self.persist()
            return True
        if code in ("00", "0"):
            self.cooldowns.pop(group, None)
            self.last_success_at[group] = stamp
            self.persist()
        return False

    def fetcher(self, purpose, fetch, *, force=False):
        """Wrap a transport: count first, then send; note code 22 / 00 from the reply."""
        if purpose not in PURPOSES:
            raise ValueError("unknown_purpose")

        def send(url):
            self.reserve(purpose, force=force)
            raw = fetch(url)
            self.record_provider_code(provider_code(raw), purpose)
            return raw
        return send
