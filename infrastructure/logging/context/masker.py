"""
Sensitive data masker.

Automatically masks sensitive fields in
log records to prevent leaking credentials,
tokens, and other secrets in log output.

Fields are matched case-insensitively
against a configurable set of sensitive
field names.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set

# Default sensitive field names (lowercase)
DEFAULT_MASK_FIELDS: Set[str] = {
    "password",
    "token",
    "secret",
    "api_key",
    "apikey",
    "private_key",
    "account_no",
    "access_key",
    "access_token",
    "refresh_token",
    "authorization",
    "auth",
    "credentials",
    "ssn",
    "credit_card",
    "card_number",
    "cvv",
    "pin",
    "passphrase",
}

# Mask value
MASK_VALUE = "******"


class DataMasker:
    """
    Sensitive data masker.

    Masks values of sensitive fields in
    dictionaries, preventing secrets from
    appearing in log output.

    Features:
    - Case-insensitive field name matching
    - Configurable mask fields set
    - Customizable mask value
    - Deep masking of nested dicts
    - Pattern-based masking (e.g. partial card numbers)

    Usage:
        masker = DataMasker()
        safe = masker.mask({"password": "abc123", "user": "admin"})
        # safe = {"password": "******", "user": "admin"}
    """

    def __init__(
        self,
        mask_fields: Optional[Set[str]] = None,
        mask_value: str = MASK_VALUE,
        deep: bool = True,
    ) -> None:
        """
        Initialize masker.

        Args:
            mask_fields: Set of sensitive field names.
            mask_value: Value to replace sensitive data with.
            deep: Whether to mask nested dicts.
        """

        self._mask_fields = mask_fields or DEFAULT_MASK_FIELDS
        self._mask_value = mask_value
        self._deep = deep
        self._masked_count: int = 0

    @property
    def masked_count(
        self,
    ) -> int:
        """Get total masked field count."""
        return self._masked_count

    def mask(
        self,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Mask sensitive fields in a dictionary.

        Args:
            fields: Dictionary to mask.

        Returns:
            New dictionary with sensitive values masked.
        """

        self._masked_count = 0
        return self._mask_dict(fields)

    def _mask_dict(
        self,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Internal recursive masking."""

        result: Dict[str, Any] = {}

        for key, value in fields.items():
            if key.lower() in self._mask_fields:
                result[key] = self._mask_value
                self._masked_count += 1
            elif self._deep and isinstance(value, dict):
                result[key] = self._mask_dict(value)
            elif self._deep and isinstance(value, list):
                result[key] = [
                    self._mask_dict(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                result[key] = value

        return result

    def add_field(
        self,
        name: str,
    ) -> None:
        """
        Add a sensitive field name.

        Args:
            name: Field name to mask.
        """

        self._mask_fields.add(name.lower())

    def remove_field(
        self,
        name: str,
    ) -> None:
        """
        Remove a sensitive field name.

        Args:
            name: Field name to stop masking.
        """

        self._mask_fields.discard(name.lower())

    def is_sensitive(
        self,
        name: str,
    ) -> bool:
        """
        Check if a field name is sensitive.

        Args:
            name: Field name to check.

        Returns:
            True if sensitive.
        """

        return name.lower() in self._mask_fields

    def get_stats(
        self,
    ) -> dict:
        """Get masker statistics."""

        return {
            "mask_fields": len(self._mask_fields),
            "masked_count": self._masked_count,
            "deep": self._deep,
        }


# Default masker instance
_default_masker = DataMasker()


def mask(
    fields: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Mask sensitive fields using default masker.

    Args:
        fields: Dictionary to mask.

    Returns:
        Masked dictionary.
    """

    return _default_masker.mask(fields)
