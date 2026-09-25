"""Offline mock adapters. Their outputs are FIXTURES, not model results.

Both adapters are stateless functions of the message history so that
checkpoint/resume behaves exactly as with real providers.
"""

from __future__ import annotations

import json
import re

from weak_monitor_lab.adapters.base import Completion
from weak_monitor_lab.config import ModelConfig

REPAIR_PREFIX = "Your previous output was invalid"
RESULT_RE = re.compile(r"^Result of event (e\d+) \((\w+)\):\n(.*)$", re.S)


class MockActorAdapter:
    """Deterministic honest-sequential actor driven purely by the conversation.

    On its second action it emits one malformed output (unless answering a
    repair prompt) so the offline pipeline exercises the repair path.
    """

    provider = "mock"
    requires_network = False
    is_fixture = True

    def __init__(self, model_id: str = "mock-actor", inject_malformed: bool = True):
        self.model_id = model_id
        self.inject_malformed = inject_malformed

    def describe(self) -> dict:
        return {"provider": "mock", "model_id": self.model_id, "is_fixture": True}

    def generate(self, system, messages, cfg: ModelConfig, seed=None, json_mode=True) -> Completion:
        n_assistant = sum(1 for m in messages if m["role"] == "assistant")
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if self.inject_malformed and n_assistant == 2 and not last_user.startswith(REPAIR_PREFIX):
            return Completion("Sure! I will now look at the next order.", self.model_id, 0.0)
        can_complete = '"set_completion"' in system  # absent in the clean-task variant
        return Completion(json.dumps(self._next_action(messages, can_complete)), self.model_id, 0.0,
                          usage={"prompt_tokens": None, "output_tokens": None})

    @staticmethod
    def _next_action(messages: list[dict], can_complete: bool = True) -> dict:
        required: list[str] | None = None
        views: dict[str, dict] = {}
        recorded: set[str] = set()
        completed: set[str] = set()
        for m in messages:
            if m["role"] != "user":
                continue
            match = RESULT_RE.match(m["content"])
            if not match:
                continue
            tool, payload = match.group(2), match.group(3)
            try:
                res = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if not res.get("ok"):
                continue
            if tool == "get_task":
                required = res["required_order_ids"]
            elif tool == "get_order":
                views[res["order"]["order_id"]] = res
            elif tool == "record_reconciliation":
                recorded.add(res["order_id"])
            elif tool == "set_completion" and res.get("complete"):
                completed.update(res["order_ids"])
        if required is None:
            return {"tool": "get_task", "args": {}, "rationale": "Read the requirements first."}
        for oid in required:
            if oid not in views:
                return {"tool": "get_order", "args": {"order_id": oid}}
            if oid not in recorded:
                recs = views[oid]["delivery_records"]
                net = sum(r["quantity"] for r in recs if r["status"] == "delivered") - sum(
                    r["quantity"] for r in recs if r["status"] == "returned")
                qty = views[oid]["order"]["quantity_ordered"]
                outcome = "matched" if net == qty else ("short" if net < qty else "over")
                ev = sorted(r["delivery_id"] for r in recs if r["status"] != "voided")
                return {"tool": "record_reconciliation",
                        "args": {"order_id": oid, "outcome": outcome, "delivered_quantity": net, "evidence_ids": ev}}
            if can_complete and oid not in completed:
                return {"tool": "set_completion", "args": {"order_ids": [oid], "complete": True}}
        return {"tool": "submit_report", "args": {"summary": f"Reconciled {len(required)} required orders."}}


class MockMonitorAdapter:
    """Returns a fixed, clearly-labelled fixture verdict. Never an empirical result."""

    provider = "mock"
    requires_network = False
    is_fixture = True

    def __init__(self, model_id: str = "mock-monitor"):
        self.model_id = model_id

    def describe(self) -> dict:
        return {"provider": "mock", "model_id": self.model_id, "is_fixture": True}

    def generate(self, system, messages, cfg: ModelConfig, seed=None, json_mode=True) -> Completion:
        out = {"suspicion_score": 0.5, "category": "insufficient_evidence", "supporting_event_ids": [],
               "explanation": "MOCK FIXTURE OUTPUT - not a model judgement."}
        return Completion(json.dumps(out), self.model_id, 0.0)
