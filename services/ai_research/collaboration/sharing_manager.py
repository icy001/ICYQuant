"""
ICYQuant Collaboration — sharing manager for research artifacts.

Manages sharing of research reports, notebooks, experiments, and
artifacts with team members and external collaborators.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SharePermission(str, Enum):
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"
    OWNER = "owner"


class ShareTarget(str, Enum):
    REPORT = "report"
    NOTEBOOK = "notebook"
    EXPERIMENT = "experiment"
    ARTIFACT = "artifact"
    SESSION = "session"


@dataclass
class ShareLink:
    """A shared resource link."""
    share_id: str
    target_type: ShareTarget
    target_id: str
    owner_id: str
    permissions: dict[str, SharePermission] = field(default_factory=dict)  # user_id → permission
    is_public: bool = False
    public_url: str = ""
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class SharingManager:
    """Research artifact sharing and access control.

    Supports:
        - Share resources with specific users
        - Permission levels (view, comment, edit, owner)
        - Public sharing with expiration
        - Access revocation
        - Share activity tracking
    """

    def __init__(self) -> None:
        self._shares: dict[str, ShareLink] = {}
        self._total_shares = 0

    def share(
        self,
        target_type: ShareTarget,
        target_id: str,
        owner_id: str,
        shared_with: Optional[dict[str, SharePermission]] = None,
        is_public: bool = False,
        expires_in_hours: Optional[int] = None,
    ) -> ShareLink:
        """Share a resource with specific users."""
        import uuid

        expires_at = None
        if expires_in_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        share = ShareLink(
            share_id=str(uuid.uuid4()),
            target_type=target_type,
            target_id=target_id,
            owner_id=owner_id,
            permissions=shared_with or {},
            is_public=is_public,
            public_url=f"icyquant://share/{uuid.uuid4().hex[:12]}" if is_public else "",
            expires_at=expires_at,
        )
        self._shares[share.share_id] = share
        self._total_shares += 1
        logger.info("Shared %s %s", target_type.value, target_id)
        return share

    def add_user(
        self,
        share_id: str,
        user_id: str,
        permission: SharePermission = SharePermission.VIEW,
    ) -> bool:
        """Add a user to a share."""
        share = self._shares.get(share_id)
        if share is None:
            return False
        share.permissions[user_id] = permission
        return True

    def remove_user(self, share_id: str, user_id: str) -> bool:
        """Remove a user from a share."""
        share = self._shares.get(share_id)
        if share is None:
            return False
        share.permissions.pop(user_id, None)
        return True

    def change_permission(
        self,
        share_id: str,
        user_id: str,
        new_permission: SharePermission,
    ) -> bool:
        """Change a user's permission level."""
        share = self._shares.get(share_id)
        if share is None or user_id not in share.permissions:
            return False
        share.permissions[user_id] = new_permission
        return True

    def check_access(
        self,
        share_id: str,
        user_id: str,
        required_permission: SharePermission = SharePermission.VIEW,
    ) -> bool:
        """Check if a user has sufficient permission."""
        share = self._shares.get(share_id)
        if share is None:
            return False

        # Owner always has full access
        if user_id == share.owner_id:
            return True

        # Public access (view only)
        if share.is_public and required_permission == SharePermission.VIEW:
            if share.expires_at is None or share.expires_at > datetime.now(timezone.utc):
                return True

        # Check explicit permissions
        user_perm = share.permissions.get(user_id)
        if user_perm is None:
            return False

        perm_order = {
            SharePermission.VIEW: 0,
            SharePermission.COMMENT: 1,
            SharePermission.EDIT: 2,
            SharePermission.OWNER: 3,
        }
        return perm_order.get(user_perm, -1) >= perm_order.get(required_permission, 0)

    def revoke(self, share_id: str) -> bool:
        """Revoke a share entirely."""
        if share_id in self._shares:
            del self._shares[share_id]
            return True
        return False

    def list_shares_for_target(self, target_id: str) -> list[ShareLink]:
        """List all shares for a specific target."""
        return [s for s in self._shares.values() if s.target_id == target_id]

    def list_shares_by_owner(self, owner_id: str) -> list[ShareLink]:
        """List all shares created by an owner."""
        return [s for s in self._shares.values() if s.owner_id == owner_id]

    def list_shares_for_user(self, user_id: str) -> list[ShareLink]:
        """List all shares accessible to a user."""
        return [
            s for s in self._shares.values()
            if user_id in s.permissions or s.is_public
        ]

    def cleanup_expired(self) -> int:
        """Remove expired shares."""
        now = datetime.now(timezone.utc)
        expired_ids = [
            sid for sid, s in self._shares.items()
            if s.expires_at is not None and s.expires_at < now
        ]
        for sid in expired_ids:
            del self._shares[sid]
        return len(expired_ids)

    @property
    def total_shares(self) -> int:
        return self._total_shares

    @property
    def active_share_count(self) -> int:
        return len(self._shares)
