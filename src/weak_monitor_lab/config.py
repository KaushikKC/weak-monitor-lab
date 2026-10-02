"""Experiment configuration (TOML -> validated Pydantic) and secret handling.

Secrets are read from the process environment or a local ``.env`` file only.
They are never stored in config snapshots, logs, or run directories.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Provider = Literal["mock", "ollama", "gemini"]
SECRET_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelConfig(_M):
    provider: Provider = "mock"
    model_id: str = "mock"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float | None = Field(None, gt=0.0, le=1.0)
    max_output_tokens: int = Field(512, ge=16, le=8192)
    seed: int | None = None  # base sampling seed; per-sample seeds are derived from it
    ollama_num_ctx: int | None = None
    ollama_think: bool | None = None  # for thinking-capable local models; None = server default
    gemini_thinking_budget: int | None = None  # None = SDK/server default


class MonitorConfig(ModelConfig):
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    samples: int = Field(1, ge=1, le=20)  # independent repeated monitor samples per (trajectory, condition)
    max_input_chars: int = Field(30_000, ge=2_000)
    max_repairs: int = Field(1, ge=0, le=5)
    prompt_variant: Literal["v1", "v2", "v3", "v4", "v5"] = "v1"  # see monitor/prompts.py


class EpisodeConfig(_M):
    max_actions: int = Field(40, ge=1, le=500)
    max_repairs_per_step: int = Field(2, ge=0, le=10)
    max_context_chars: int = Field(24_000, ge=4_000)
    max_rationale_chars: int = Field(300, ge=0, le=2000)


class NetworkConfig(_M):
    enabled: bool = False  # network model calls (incl. localhost Ollama) are off by default
    ollama_base_url: str = "http://localhost:11434"
    request_timeout_s: float = Field(120.0, gt=0)
    concurrency: int = 1

    @field_validator("concurrency")
    @classmethod
    def _only_one(cls, v: int) -> int:
        if v != 1:
            raise ValueError("only concurrency=1 is implemented")
        return v


class LimitsConfig(_M):
    max_total_requests: int = Field(200, ge=0)  # hard cap on generation requests per run
    # Per-day cap for this run (0 = none). Counts only this run's requests, not other runs or apps.
    max_requests_per_day: int = Field(0, ge=0)
    quota_day_timezone: str = "America/Los_Angeles"  # Gemini daily quotas reset at midnight Pacific time
    daily_cap_providers: list[str] = ["gemini"]  # only these providers count toward max_requests_per_day
    requests_per_minute: float = Field(10.0, gt=0)
    max_retries: int = Field(3, ge=0, le=10)  # transient errors (timeouts, 5xx)
    max_quota_retries: int = Field(2, ge=0, le=10)  # 429 / RESOURCE_EXHAUSTED before stopping
    backoff_base_s: float = Field(2.0, ge=0)
    backoff_max_s: float = Field(60.0, ge=0)


class ExperimentConfig(_M):
    seed: int = 1234
    n_scenarios: int = Field(5, ge=1)
    samples_per_scenario: int = Field(1, ge=1)
    n_required: int = Field(6, ge=4, le=30)
    n_distractors: int = Field(2, ge=0, le=20)
    dev_fraction: float = Field(0.5, ge=0.0, le=1.0)
    # Actor elicitation (agent.ELICITATIONS). "none" for every dataset source except
    # elicited_adversarial, which requires a non-"none" value. Enforced in pipeline.run_actor.
    elicitation: Literal["none", "score_pressure"] = "none"


class Config(_M):
    actor: ModelConfig = ModelConfig()
    monitor: MonitorConfig = MonitorConfig()
    episode: EpisodeConfig = EpisodeConfig()
    network: NetworkConfig = NetworkConfig()
    limits: LimitsConfig = LimitsConfig()
    experiment: ExperimentConfig = ExperimentConfig()

    def snapshot(self) -> dict:
        """Serializable, secret-free config snapshot."""
        return self.model_dump(mode="json")


def load_config(path: str | Path | None, enable_network: bool = False) -> Config:
    data: dict = {}
    if path:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    cfg = Config.model_validate(data)
    if enable_network or os.environ.get("WML_ENABLE_NETWORK") == "1":
        cfg.network.enabled = True
    return cfg


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env loader (KEY=VALUE lines). Existing environment variables win."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def gemini_api_key() -> str | None:
    for var in SECRET_ENV_VARS:
        if os.environ.get(var):
            return os.environ[var]
    return None


def redact(text: str) -> str:
    """Remove any known secret values from text before it is logged or printed."""
    for var in SECRET_ENV_VARS:
        val = os.environ.get(var)
        if val and len(val) >= 8:
            text = text.replace(val, "***REDACTED***")
    return text
