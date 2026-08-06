"""Webhook Trigger — HTTP-webhook-driven scheduling for external system integration.

The :class:`WebhookTrigger` exposes an HTTP endpoint.  When a POST request
is received (with valid authentication), the trigger fires and the payload
is forwarded to the scheduler runtime.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class _EvaluationResult:
    should_fire: bool
    is_misfire: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    fire_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class WebhookTrigger:
    """Trigger that fires on incoming HTTP webhook calls.

    Usage::

        trigger = WebhookTrigger(
            schedule_id="sch-external-signal",
            secret="my-shared-secret",
            target="job-process-signal",
        )
        # Incoming POST → trigger.handle_request(body, signature)
    """

    schedule_id: str
    secret: str = ""
    target: str = ""
    priority: int = 150
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)
    allowed_ips: List[str] = field(default_factory=list)

    # Internal state
    trigger_id: str = field(default_factory=lambda: f"webhook_{id(object()):x}")
    trigger_type: str = "webhook"
    _pending_requests: List[Dict[str, Any]] = field(default_factory=list)
    _last_fire_at: Optional[datetime] = field(default=None, repr=False)
    _fire_count: int = field(default=0, repr=False)

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    def handle_request(
        self,
        body: bytes,
        signature: str = "",
        client_ip: str = "",
    ) -> bool:
        """Handle an incoming webhook request.

        Returns True if the request was accepted and queued.
        """
        # IP whitelist check
        if self.allowed_ips and client_ip not in self.allowed_ips:
            return False

        # Signature verification
        if self.secret and not self._verify_signature(body, signature):
            return False

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return False

        self._pending_requests.append({
            "received_at": datetime.now(timezone.utc).isoformat(),
            "client_ip": client_ip,
            "data": data,
        })
        return True

    def _verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify HMAC-SHA256 signature."""
        if not signature:
            return False
        expected = hmac.new(
            self.secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self) -> _EvaluationResult:
        """Evaluate — fire once per pending webhook request."""
        try:
            if not self._pending_requests:
                return _EvaluationResult(should_fire=False)

            request = self._pending_requests.pop(0)
            now = datetime.now(timezone.utc)

            self._last_fire_at = now
            self._fire_count += 1

            return _EvaluationResult(
                should_fire=True,
                payload={
                    **self.payload,
                    "webhook_data": request["data"],
                    "received_at": request["received_at"],
                    "trigger_type": "webhook",
                },
                fire_at=now,
            )

        except Exception as e:
            return _EvaluationResult(
                should_fire=False,
                is_misfire=True,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def pending_count(self) -> int:
        return len(self._pending_requests)

    def clear_pending(self) -> None:
        self._pending_requests.clear()

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "target": self.target,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
            "allowed_ips": self.allowed_ips,
            "has_secret": bool(self.secret),
        }

    def __repr__(self) -> str:
        return f"WebhookTrigger(id={self.trigger_id}, target={self.target})"
