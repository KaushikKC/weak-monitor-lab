from __future__ import annotations

from weak_monitor_lab.adapters.base import (
    Adapter, BudgetExceeded, Completion, NetworkDisabled, ProviderError, QuotaError, QuotaExhausted, TransientError,
)
from weak_monitor_lab.config import Config, ModelConfig, gemini_api_key


def make_adapter(mc: ModelConfig, cfg: Config, role: str) -> Adapter:
    """Build an adapter. Network-backed adapters refuse to exist while network calls are disabled."""
    if mc.provider == "mock":
        from weak_monitor_lab.adapters.mock import MockActorAdapter, MockMonitorAdapter

        return MockActorAdapter(mc.model_id) if role == "actor" else MockMonitorAdapter(mc.model_id)
    if not cfg.network.enabled:
        raise NetworkDisabled(
            f"{role} provider is {mc.provider!r} but network model calls are disabled. "
            "Pass --enable-network (or set [network].enabled = true) to allow them.")
    if mc.provider == "ollama":
        from weak_monitor_lab.adapters.ollama import OllamaAdapter

        return OllamaAdapter(mc.model_id, cfg.network.ollama_base_url, cfg.network.request_timeout_s)
    if mc.provider == "gemini":
        from weak_monitor_lab.adapters.gemini import GeminiAdapter

        return GeminiAdapter(mc.model_id, gemini_api_key(), cfg.network.request_timeout_s)
    raise ValueError(f"unknown provider {mc.provider!r}")


__all__ = ["Adapter", "BudgetExceeded", "Completion", "NetworkDisabled", "ProviderError", "QuotaError",
           "QuotaExhausted", "TransientError", "make_adapter"]
