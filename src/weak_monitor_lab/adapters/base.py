"""Common adapter interface and error taxonomy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from weak_monitor_lab.config import ModelConfig


@dataclass
class Completion:
    text: str
    model_id: str
    latency_s: float
    usage: dict | None = None  # token counts when the provider supplies them
    meta: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Non-retryable provider failure (bad model ID, auth error, invalid request)."""


class TransientError(ProviderError):
    """Retryable: timeouts, connection errors, 5xx."""


class QuotaError(ProviderError):
    """Rate limit / quota response (HTTP 429, RESOURCE_EXHAUSTED)."""

    def __init__(self, msg: str, retry_after_s: float | None = None):
        super().__init__(msg)
        self.retry_after_s = retry_after_s


class QuotaExhausted(Exception):
    """Quota errors persisted beyond the configured retries: stop the run cleanly."""


class BudgetExceeded(Exception):
    """The run's configured max_total_requests has been reached."""


class NetworkDisabled(Exception):
    """A network-backed adapter was used while network model calls are disabled."""


class Adapter(Protocol):
    provider: str
    model_id: str
    requires_network: bool
    is_fixture: bool

    def generate(self, system: str, messages: list[dict], cfg: ModelConfig,
                 seed: int | None = None, json_mode: bool = True) -> Completion: ...

    def describe(self) -> dict: ...
