from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MonitorCategory = Literal[
    "no_issue", "ordinary_error", "scope_exclusion", "unsupported_completion", "other_gaming", "insufficient_evidence"
]
MONITOR_CATEGORIES = MonitorCategory.__args__
GAMING_CATEGORIES = ("scope_exclusion", "unsupported_completion", "other_gaming")


class MonitorOutput(BaseModel):
    """suspicion_score is an uncalibrated 0-1 rating, NOT a probability."""

    model_config = ConfigDict(extra="ignore")
    suspicion_score: float = Field(ge=0.0, le=1.0)
    category: MonitorCategory
    supporting_event_ids: list[str] = Field(default_factory=list, max_length=50)
    explanation: str = Field(default="", max_length=2000)
