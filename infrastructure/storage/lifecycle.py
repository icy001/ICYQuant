"""
Object lifecycle management.

Provides lifecycle rule definitions for
automatic object expiration, transition,
and cleanup in storage buckets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LifecycleRule:
    """
    Object lifecycle rule.

    Defines a lifecycle policy for objects
    matching a prefix pattern, including
    expiration and storage class transitions.

    Attributes:
        id: Rule identifier.
        prefix: Key prefix to match.
        expiration_days: Days until object expires.
        enabled: Whether rule is active.
        storage_class_transition: Target storage class
            for transition (e.g., GLACIER).
        transition_days: Days until transition.
        noncurrent_version_expiration: Days to keep
            non-current versions.
    """

    id: str = ""

    prefix: str = ""

    expiration_days: int = 0

    enabled: bool = True

    storage_class_transition: Optional[str] = None

    transition_days: Optional[int] = None

    noncurrent_version_expiration: Optional[
        int
    ] = None

    def to_dict(
        self,
    ) -> dict:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "id": self.id,
            "prefix": self.prefix,
            "expiration_days": (
                self.expiration_days
            ),
            "enabled": self.enabled,
            "storage_class_transition": (
                self.storage_class_transition
            ),
            "transition_days": self.transition_days,
            "noncurrent_version_expiration": (
                self.noncurrent_version_expiration
            ),
        }

    @classmethod
    def create_expiration(
        cls,
        prefix: str,
        days: int,
    ) -> LifecycleRule:
        """
        Create a simple expiration rule.

        Args:
            prefix: Key prefix to match.
            days: Days until expiration.

        Returns:
            LifecycleRule for expiration.
        """

        return cls(
            id=f"expire-{prefix.rstrip('/')}",
            prefix=prefix,
            expiration_days=days,
            enabled=True,
        )

    @classmethod
    def create_archive(
        cls,
        prefix: str,
        transition_days: int,
        expiration_days: int,
    ) -> LifecycleRule:
        """
        Create an archive lifecycle rule.

        Transitions objects to GLACIER after
        transition_days, then expires after
        expiration_days.

        Args:
            prefix: Key prefix to match.
            transition_days: Days until GLACIER transition.
            expiration_days: Days until expiration.

        Returns:
            LifecycleRule for archive.
        """

        return cls(
            id=f"archive-{prefix.rstrip('/')}",
            prefix=prefix,
            expiration_days=expiration_days,
            storage_class_transition="GLACIER",
            transition_days=transition_days,
            enabled=True,
        )


@dataclass
class LifecyclePolicy:
    """
    Bucket lifecycle policy.

    Collection of lifecycle rules applied
    to a bucket.

    Attributes:
        rules: List of lifecycle rules.
    """

    rules: List[LifecycleRule]

    def to_dict(
        self,
    ) -> dict:
        """
        Serialize to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "rules": [
                rule.to_dict()
                for rule in self.rules
            ]
        }

    def add_rule(
        self,
        rule: LifecycleRule,
    ) -> None:
        """
        Add a lifecycle rule.

        Args:
            rule: Lifecycle rule to add.
        """

        self.rules.append(rule)

    @classmethod
    def default(
        cls,
    ) -> LifecyclePolicy:
        """
        Create default lifecycle policy.

        Includes rules for common ICYQuant
        data patterns:
        - logs/ expire after 30 days
        - temp/ expire after 7 days
        - cache/ expire after 1 day

        Returns:
            Default lifecycle policy.
        """

        return cls(
            rules=[
                LifecycleRule.create_expiration(
                    prefix="logs/",
                    days=30,
                ),
                LifecycleRule.create_expiration(
                    prefix="temp/",
                    days=7,
                ),
                LifecycleRule.create_expiration(
                    prefix="cache/",
                    days=1,
                ),
            ]
        )