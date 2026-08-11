"""
Approval Repository — persistence layer for approval requests, responses, and transitions.

Follows the same pattern as PolicyRepository: abstraction over storage backends.
Works with the existing ApprovalRequest model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .approval_request import ApprovalRequest, ApprovalRequestStatus
from .approval_response import ApprovalResponse
from .approval_status import ApprovalStatus
from .approval_transition import ApprovalTransition


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------

class ApprovalBackend(Protocol):
    """Storage backend for approval data."""

    def save_request(self, request: Dict[str, Any]) -> None: ...
    def load_request(self, request_id: str) -> Optional[Dict[str, Any]]: ...
    def list_requests(self, status: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def delete_request(self, request_id: str) -> None: ...

    def save_response(self, request_id: str, response: Dict[str, Any]) -> None: ...
    def load_response(self, request_id: str) -> Optional[Dict[str, Any]]: ...

    def save_transition(self, request_id: str, transition: Dict[str, Any]) -> None: ...
    def list_transitions(self, request_id: str) -> List[Dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# In-Memory Backend
# ---------------------------------------------------------------------------

class InMemoryApprovalBackend:
    """In-memory storage for approval data."""

    def __init__(self):
        self._requests: Dict[str, Dict[str, Any]] = {}
        self._responses: Dict[str, Dict[str, Any]] = {}
        self._transitions: Dict[str, List[Dict[str, Any]]] = {}

    def save_request(self, request: Dict[str, Any]) -> None:
        self._requests[request["request_id"]] = request

    def load_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        return self._requests.get(request_id)

    def list_requests(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        results = list(self._requests.values())
        if status:
            results = [r for r in results if r.get("status") == status]
        return results

    def delete_request(self, request_id: str) -> None:
        self._requests.pop(request_id, None)

    def save_response(self, request_id: str, response: Dict[str, Any]) -> None:
        self._responses[request_id] = response

    def load_response(self, request_id: str) -> Optional[Dict[str, Any]]:
        return self._responses.get(request_id)

    def save_transition(self, request_id: str, transition: Dict[str, Any]) -> None:
        if request_id not in self._transitions:
            self._transitions[request_id] = []
        self._transitions[request_id].append(transition)

    def list_transitions(self, request_id: str) -> List[Dict[str, Any]]:
        return self._transitions.get(request_id, [])


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

@dataclass
class ApprovalRepository:
    """
    Persistence layer for approval data.
    """

    backend: Any = field(default_factory=InMemoryApprovalBackend)

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    def save_request(self, request: ApprovalRequest) -> None:
        """Save an approval request."""
        self.backend.save_request(request.to_dict())

    def load_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Load an approval request by ID."""
        data = self.backend.load_request(request_id)
        if data is None:
            return None
        return ApprovalRequest(
            request_id=data["request_id"],
            decision_request_id=data.get("decision_request_id", ""),
            decision_type=data.get("decision_type", ""),
            amount=data.get("amount"),
            risk=data.get("risk"),
            level=data.get("level", "INTERNAL"),
            context=data.get("context", {}),
            reason=data.get("reason", ""),
            status=ApprovalRequestStatus[data.get("status", "PENDING")],
            created_at=data.get("created_at", 0.0),
            expires_at=data.get("expires_at"),
            resolved_at=data.get("resolved_at"),
            resolved_by=data.get("resolved_by", ""),
            resolution_reason=data.get("resolution_reason", ""),
        )

    def list_requests(self, status: Optional[ApprovalRequestStatus] = None) -> List[ApprovalRequest]:
        """List approval requests, optionally filtered by status."""
        status_str = status.name if status else None
        data_list = self.backend.list_requests(status_str)
        results = []
        for data in data_list:
            results.append(ApprovalRequest(
                request_id=data["request_id"],
                decision_request_id=data.get("decision_request_id", ""),
                decision_type=data.get("decision_type", ""),
                amount=data.get("amount"),
                risk=data.get("risk"),
                level=data.get("level", "INTERNAL"),
                context=data.get("context", {}),
                reason=data.get("reason", ""),
                status=ApprovalRequestStatus[data.get("status", "PENDING")],
                created_at=data.get("created_at", 0.0),
                expires_at=data.get("expires_at"),
                resolved_at=data.get("resolved_at"),
                resolved_by=data.get("resolved_by", ""),
                resolution_reason=data.get("resolution_reason", ""),
            ))
        return results

    def delete_request(self, request_id: str) -> None:
        """Delete an approval request."""
        self.backend.delete_request(request_id)

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def save_response(self, request_id: str, response: ApprovalResponse) -> None:
        """Save an approval response."""
        self.backend.save_response(request_id, response.to_dict())

    def load_response(self, request_id: str) -> Optional[ApprovalResponse]:
        """Load an approval response."""
        data = self.backend.load_response(request_id)
        if data is None:
            return None
        return ApprovalResponse(
            approval_id=data["approval_id"],
            request_id=data.get("request_id", ""),
            decision_id=data.get("decision_id", ""),
            status=ApprovalStatus[data.get("status", "PENDING")],
            approved=data.get("approved", False),
            approved_amount=data.get("approved_amount"),
            approved_action=data.get("approved_action", ""),
            valid_from=data.get("valid_from", 0.0),
            valid_until=data.get("valid_until", 0.0),
            consumed=data.get("consumed", False),
            reason=data.get("reason", ""),
            reject_reason=data.get("reject_reason", ""),
            created_at=data.get("created_at", 0.0),
            updated_at=data.get("updated_at", 0.0),
            executed_at=data.get("executed_at"),
        )

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    def save_transition(self, transition: ApprovalTransition) -> None:
        """Record a state transition."""
        self.backend.save_transition(transition.approval_id, transition.to_dict())

    def list_transitions(self, request_id: str) -> List[ApprovalTransition]:
        """List all transitions for a request."""
        data_list = self.backend.list_transitions(request_id)
        results = []
        for data in data_list:
            results.append(ApprovalTransition(
                approval_id=data["approval_id"],
                from_status=ApprovalStatus[data["from_status"]],
                to_status=ApprovalStatus[data["to_status"]],
                reason=data.get("reason", ""),
                actor=data.get("actor", "SYSTEM"),
                timestamp=data.get("timestamp", 0.0),
                metadata=data.get("metadata", {}),
            ))
        return results

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def count_by_status(self, status: ApprovalRequestStatus) -> int:
        """Count approvals with a given status."""
        return len(self.list_requests(status))

    def count_pending(self) -> int:
        """Count pending approvals."""
        return self.count_by_status(ApprovalRequestStatus.PENDING)

    def count_approved(self) -> int:
        """Count approved approvals."""
        return self.count_by_status(ApprovalRequestStatus.APPROVED)
