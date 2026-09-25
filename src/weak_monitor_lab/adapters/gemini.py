"""Gemini adapter using the official Google Gen AI Python SDK (``google-genai``).

The model ID is always user-configured. This project makes no assumption about
which Gemini models or limits your account's free tier provides.
"""

from __future__ import annotations

import re
import time

from weak_monitor_lab.adapters.base import Completion, ProviderError, QuotaError, TransientError
from weak_monitor_lab.config import ModelConfig, redact

_RETRY_RE = re.compile(r"retry(?:Delay|_delay)?['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", re.I)


def classify_gemini_error(exc: Exception) -> ProviderError:
    """Map SDK/transport exceptions onto the adapter error taxonomy."""
    msg = redact(f"{type(exc).__name__}: {exc}")[:500]
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "")
    if code == 429 or "RESOURCE_EXHAUSTED" in status or "RESOURCE_EXHAUSTED" in msg:
        m = _RETRY_RE.search(str(exc))
        return QuotaError(msg, retry_after_s=float(m.group(1)) if m else None)
    if code in (408, 500, 502, 503, 504) or isinstance(exc, (TimeoutError, ConnectionError)):
        return TransientError(msg)
    name = type(exc).__name__.lower()
    if "timeout" in name or "connect" in name:
        return TransientError(msg)
    return ProviderError(msg)


class GeminiAdapter:
    provider = "gemini"
    requires_network = True
    is_fixture = False

    def __init__(self, model_id: str, api_key: str | None, timeout_s: float = 120.0, client=None):
        if not model_id or model_id == "mock":
            raise ProviderError("set a Gemini model_id in your config; none is assumed")
        self.model_id = model_id
        if client is None:
            if not api_key:
                raise ProviderError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set; see .env.example")
            try:
                from google import genai
                from google.genai import types
            except ImportError as exc:
                raise ProviderError("google-genai is not installed: pip install -e '.[gemini]'") from exc
            client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))
        self._client = client

    def generate(self, system: str, messages: list[dict], cfg: ModelConfig,
                 seed: int | None = None, json_mode: bool = True) -> Completion:
        from google.genai import types

        contents = [types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part(text=m["content"])])
                    for m in messages]
        kw: dict = {"system_instruction": system, "temperature": cfg.temperature,
                    "max_output_tokens": cfg.max_output_tokens}
        if cfg.top_p is not None:
            kw["top_p"] = cfg.top_p
        if seed is not None:
            kw["seed"] = seed
        if json_mode:
            kw["response_mime_type"] = "application/json"
        if cfg.gemini_thinking_budget is not None:
            kw["thinking_config"] = types.ThinkingConfig(thinking_budget=cfg.gemini_thinking_budget)
        t0 = time.monotonic()
        try:
            resp = self._client.models.generate_content(
                model=self.model_id, contents=contents, config=types.GenerateContentConfig(**kw))
        except Exception as exc:  # SDK raises several exception families
            raise classify_gemini_error(exc) from None
        latency = time.monotonic() - t0
        um = getattr(resp, "usage_metadata", None)
        usage = None
        if um is not None:
            usage = {"prompt_tokens": getattr(um, "prompt_token_count", None),
                     "output_tokens": getattr(um, "candidates_token_count", None),
                     "thinking_tokens": getattr(um, "thoughts_token_count", None),
                     "total_tokens": getattr(um, "total_token_count", None)}
        finish = None
        if getattr(resp, "candidates", None):
            finish = str(getattr(resp.candidates[0], "finish_reason", None))
        try:
            text = resp.text or ""
        except Exception:  # e.g. blocked candidates
            text = ""
        return Completion(text=text, model_id=self.model_id, latency_s=latency, usage=usage,
                          meta={"finish_reason": finish, "model_version": getattr(resp, "model_version", None)})

    def describe(self) -> dict:
        info = {"provider": "gemini", "model_id": self.model_id, "is_fixture": False}
        try:
            m = self._client.models.get(model=self.model_id)
        except Exception as exc:
            raise classify_gemini_error(exc) from None
        for attr in ("name", "display_name", "version", "input_token_limit", "output_token_limit"):
            info[attr] = getattr(m, attr, None)
        return info
