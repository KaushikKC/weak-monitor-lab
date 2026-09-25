"""Local Ollama adapter using the Ollama REST API (/api/chat) over httpx.

Note: "localhost" is resolved on the machine running this code. A remote or
cloud coding environment cannot reach an Ollama server on your laptop through
its own localhost.
"""

from __future__ import annotations

import time

import httpx

from weak_monitor_lab.adapters.base import Completion, ProviderError, QuotaError, TransientError
from weak_monitor_lab.config import ModelConfig


class OllamaAdapter:
    provider = "ollama"
    requires_network = True
    is_fixture = False

    def __init__(self, model_id: str, base_url: str, timeout_s: float = 120.0,
                 transport: httpx.BaseTransport | None = None):
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout_s, transport=transport)

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            r = self._client.request(method, path, **kw)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise TransientError(f"ollama {path}: {type(exc).__name__}: {exc}") from exc
        if r.status_code == 429:
            raise QuotaError(f"ollama {path}: HTTP 429")
        if r.status_code >= 500:
            raise TransientError(f"ollama {path}: HTTP {r.status_code}: {r.text[:300]}")
        if r.status_code >= 400:
            raise ProviderError(f"ollama {path}: HTTP {r.status_code}: {r.text[:300]}")
        return r

    def generate(self, system: str, messages: list[dict], cfg: ModelConfig,
                 seed: int | None = None, json_mode: bool = True) -> Completion:
        options: dict = {"temperature": cfg.temperature, "num_predict": cfg.max_output_tokens}
        if cfg.top_p is not None:
            options["top_p"] = cfg.top_p
        if seed is not None:
            options["seed"] = seed
        if cfg.ollama_num_ctx:
            options["num_ctx"] = cfg.ollama_num_ctx
        payload: dict = {
            "model": self.model_id,
            "messages": [{"role": "system", "content": system}] + messages,
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"
        if cfg.ollama_think is not None:
            payload["think"] = cfg.ollama_think
        t0 = time.monotonic()
        r = self._request("POST", "/api/chat", json=payload)
        latency = time.monotonic() - t0
        data = r.json()
        return Completion(
            text=(data.get("message") or {}).get("content", ""),
            model_id=data.get("model", self.model_id),
            latency_s=latency,
            usage={"prompt_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count")},
            meta={"done_reason": data.get("done_reason"), "total_duration_ns": data.get("total_duration"),
                  "load_duration_ns": data.get("load_duration")},
        )

    def describe(self) -> dict:
        """Server version plus model digest/quantization, without generating anything."""
        info: dict = {"provider": "ollama", "model_id": self.model_id, "base_url": self.base_url, "is_fixture": False}
        info["server_version"] = self._request("GET", "/api/version").json().get("version")
        tags = self._request("GET", "/api/tags").json().get("models", [])
        entry = next((m for m in tags if m.get("name") == self.model_id or m.get("model") == self.model_id), None)
        if entry is None:
            raise ProviderError(f"model {self.model_id!r} is not installed in Ollama; run `ollama pull {self.model_id}`"
                                " yourself if you want it (this tool never downloads models)")
        details = entry.get("details", {})
        info.update(digest=entry.get("digest"), size_bytes=entry.get("size"),
                    quantization=details.get("quantization_level"), parameter_size=details.get("parameter_size"),
                    family=details.get("family"), format=details.get("format"))
        return info
