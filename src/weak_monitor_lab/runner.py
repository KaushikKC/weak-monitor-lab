"""Checkpointed, budgeted, rate-limited model calls.

Every completed call is appended to ``calls.jsonl`` under a caller-supplied
``call_key``. The key encodes (run, episode/trajectory, step, repair attempt,
sample index, purpose), so:

* resuming re-uses completed calls instead of repeating them, and
* independent repeated samples have distinct keys and are never deduplicated.

A cached call is only reused if its prompt hash matches the current prompt;
otherwise the run refuses to continue (config or code changed under it).
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Callable

from weak_monitor_lab.adapters.base import (
    Adapter, BudgetExceeded, ProviderError, QuotaError, QuotaExhausted, TransientError,
)
from weak_monitor_lab.config import LimitsConfig, ModelConfig, redact
from weak_monitor_lab.io import append_jsonl, read_json, read_jsonl, sha256_json, sha256_text, utc_now, write_json


class CheckpointMismatch(RuntimeError):
    pass


class ProviderUnavailable(ProviderError):
    """Transient errors persisted beyond max_retries."""


class CallRunner:
    def __init__(self, run_dir: Path, limits: LimitsConfig,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 today: Callable[[], str] | None = None):
        self.run_dir = Path(run_dir)
        self.limits = limits
        self.sleep = sleep
        self.clock = clock
        self.calls_path = self.run_dir / "calls.jsonl"
        self.failures_path = self.run_dir / "failures.jsonl"
        self.budget_path = self.run_dir / "budget.json"
        self.cache: dict[str, dict] = {r["call_key"]: r for r in read_jsonl(self.calls_path)}
        budget = read_json(self.budget_path) if self.budget_path.exists() else {}
        self.requests_used = budget.get("network_requests_used", 0)
        self.requests_by_day: dict[str, int] = budget.get("by_day", {})
        tz = ZoneInfo(limits.quota_day_timezone)
        self.today = today or (lambda: datetime.now(tz).date().isoformat())
        self._last_request_t: float | None = None
        self.cache_hits = 0

    def _record_failure(self, key: str, adapter: Adapter, kind: str, detail: str, attempt: int) -> None:
        append_jsonl(self.failures_path, {
            "timestamp": utc_now(), "call_key": key, "provider": adapter.provider, "model_id": adapter.model_id,
            "kind": kind, "detail": redact(detail)[:500], "attempt": attempt})

    def _throttle(self) -> None:
        min_interval = 60.0 / self.limits.requests_per_minute
        if self._last_request_t is not None:
            wait = self._last_request_t + min_interval - self.clock()
            if wait > 0:
                self.sleep(wait)
        self._last_request_t = self.clock()

    def _backoff(self, n: int, hint: float | None = None) -> float:
        b = min(self.limits.backoff_max_s, self.limits.backoff_base_s * (2 ** (n - 1)))
        return max(b, hint or 0.0)

    def call(self, adapter: Adapter, key: str, system: str, messages: list[dict], mc: ModelConfig,
             seed: int | None, purpose: str, extra: dict | None = None) -> dict:
        prompt_hash = sha256_json({"system": system, "messages": messages, "provider": adapter.provider,
                                   "model_id": adapter.model_id, "seed": seed})
        if key in self.cache:
            rec = self.cache[key]
            if rec["prompt_hash"] != prompt_hash:
                raise CheckpointMismatch(
                    f"checkpointed call {key} has a different prompt; refusing to mix runs. "
                    "Start a new run ID if the config or code changed.")
            self.cache_hits += 1
            return {**rec, "from_cache": True}

        quota_failures = transient_failures = 0
        attempt = 0
        while True:
            attempt += 1
            if adapter.requires_network:
                if self.requests_used >= self.limits.max_total_requests:
                    raise BudgetExceeded(f"max_total_requests={self.limits.max_total_requests} reached")
                day = self.today()
                counts_daily = adapter.provider in self.limits.daily_cap_providers
                cap = self.limits.max_requests_per_day if counts_daily else 0
                if cap and self.requests_by_day.get(day, 0) >= cap:
                    raise BudgetExceeded(
                        f"max_requests_per_day={cap} reached for {day} ({self.limits.quota_day_timezone}); "
                        "resume after the daily quota resets")
                self._throttle()
                self.requests_used += 1
                if counts_daily:
                    self.requests_by_day[day] = self.requests_by_day.get(day, 0) + 1
                write_json(self.budget_path, {"network_requests_used": self.requests_used,
                                              "by_day": self.requests_by_day, "updated": utc_now()})
            try:
                comp = adapter.generate(system, messages, mc, seed=seed, json_mode=True)
                break
            except QuotaError as exc:
                quota_failures += 1
                self._record_failure(key, adapter, "quota", str(exc), attempt)
                if quota_failures > self.limits.max_quota_retries:
                    raise QuotaExhausted(redact(str(exc))) from None
                self.sleep(self._backoff(quota_failures, exc.retry_after_s))
            except TransientError as exc:
                transient_failures += 1
                self._record_failure(key, adapter, "transient", str(exc), attempt)
                if transient_failures > self.limits.max_retries:
                    raise ProviderUnavailable(redact(str(exc))) from None
                self.sleep(self._backoff(transient_failures))
            except ProviderError as exc:
                self._record_failure(key, adapter, "provider_error", str(exc), attempt)
                raise

        rec = {
            "call_key": key,
            "purpose": purpose,
            "timestamp": utc_now(),
            "provider": adapter.provider,
            "model_id": adapter.model_id,
            "response_model_id": comp.model_id,
            "is_fixture": adapter.is_fixture,
            "seed": seed,
            "sampling": {"temperature": mc.temperature, "top_p": mc.top_p, "max_output_tokens": mc.max_output_tokens},
            "prompt_hash": prompt_hash,
            "system_prompt_hash": sha256_text(system),
            "prompt_chars": len(system) + sum(len(m["content"]) for m in messages),
            "text": comp.text,
            "usage": comp.usage,
            "latency_s": comp.latency_s,
            "meta": comp.meta,
            "attempts": attempt,
            "retries": attempt - 1,
            **(extra or {}),
        }
        append_jsonl(self.calls_path, rec)
        self.cache[key] = rec
        return {**rec, "from_cache": False}
