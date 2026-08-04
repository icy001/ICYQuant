"""
Secrets platform utility functions.

Provides common helpers used across the
secrets management platform, including
sanitization, masking, and format conversion.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

from .constants import SECRET_PATTERN, SecretFormat


def mask_secret_value(
    value: str,
    keep_start: int = 0,
    keep_end: int = 4,
    mask_char: str = "*",
) -> str:
    """
    Mask a secret value for safe display.

    Args:
        value: The secret value to mask.
        keep_start: Number of chars to keep at start.
        keep_end: Number of chars to keep at end.
        mask_char: Character to use for masking.

    Returns:
        Masked string.
    """
    if not value:
        return ""

    if len(value) <= keep_start + keep_end:
        return mask_char * len(value)

    start = value[:keep_start]
    end = value[-keep_end:] if keep_end > 0 else ""
    mask_len = len(value) - keep_start - keep_end
    return f"{start}{mask_char * max(mask_len, 0)}{end}"


def sanitize_secret_key(key: str) -> str:
    """
    Sanitize a secret key path.

    Normalizes the key path by removing
    consecutive slashes, trimming, and
    ensuring it's a valid path.

    Args:
        key: The raw secret key.

    Returns:
        Sanitized key path.
    """
    if not key:
        return ""

    key = key.strip()
    key = re.sub(r"/{2,}", "/", key)
    key = key.strip("/")
    return key


def parse_secret_reference(reference: str) -> Optional[Dict[str, str]]:
    """
    Parse a ${secret:...} reference string.

    Args:
        reference: The reference string to parse.

    Returns:
        Dict with 'key' and optional 'namespace', or None.
    """
    match = re.match(SECRET_PATTERN, reference)
    if not match:
        return None

    key_path = match.group(1)
    return {"key": key_path, "namespace": "default"}


def is_secret_reference(value: str) -> bool:
    """
    Check if a string is a secret reference.

    Args:
        value: String to check.

    Returns:
        True if value is a ${secret:...} reference.
    """
    return bool(re.match(SECRET_PATTERN, value))


def resolve_references(
    text: str,
    resolver: Optional[Any] = None,
) -> str:
    """
    Resolve all ${secret:...} references in a text.

    Args:
        text: Text containing secret references.
        resolver: Callable(key, namespace) -> str to resolve refs.

    Returns:
        Resolved text with all references replaced.
    """
    def _replace(match: re.Match) -> str:
        key_path = match.group(1)

        if resolver and callable(resolver):
            result = resolver(key_path, "default")
            return result if result is not None else match.group(0)
        return match.group(0)

    return re.sub(SECRET_PATTERN, _replace, text)


def compute_checksum(value: str, algorithm: str = "sha256") -> str:
    """
    Compute a checksum for a secret value.

    Args:
        value: The value to hash.
        algorithm: Hash algorithm (sha256, sha512, etc.).

    Returns:
        Hex digest string.
    """
    if algorithm == "sha256":
        return hashlib.sha256(value.encode()).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(value.encode()).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(value.encode()).hexdigest()
    else:
        return hashlib.sha256(value.encode()).hexdigest()


def encode_value(value: Any, fmt: SecretFormat = SecretFormat.PLAINTEXT) -> str:
    """
    Encode a value into the specified format.

    Args:
        value: The value to encode.
        fmt: Target format.

    Returns:
        Encoded string.
    """
    if fmt == SecretFormat.PLAINTEXT:
        return str(value)
    elif fmt == SecretFormat.JSON:
        return json.dumps(value)
    elif fmt == SecretFormat.BASE64:
        raw = value.encode() if isinstance(value, str) else str(value).encode()
        return base64.b64encode(raw).decode()
    else:
        return str(value)


def decode_value(value: str, fmt: SecretFormat = SecretFormat.PLAINTEXT) -> Any:
    """
    Decode a value from the specified format.

    Args:
        value: The encoded string.
        fmt: Source format.

    Returns:
        Decoded value.
    """
    if fmt == SecretFormat.PLAINTEXT:
        return value
    elif fmt == SecretFormat.JSON:
        return json.loads(value)
    elif fmt == SecretFormat.BASE64:
        return base64.b64decode(value.encode()).decode()
    else:
        return value


def generate_secret_id() -> str:
    """
    Generate a unique secret identifier.

    Returns:
        Unique ID string.
    """
    ts = datetime.utcnow().timestamp()
    raw = f"secret_{ts}_{hashlib.sha256(str(ts).encode()).hexdigest()[:12]}"
    return raw


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Format a datetime to ISO 8601 string.

    Args:
        dt: Datetime to format (defaults to now).

    Returns:
        ISO 8601 formatted string.
    """
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat() + "Z"


def parse_timestamp(ts_str: str) -> datetime:
    """
    Parse an ISO 8601 timestamp string.

    Args:
        ts_str: Timestamp string.

    Returns:
        Parsed datetime.
    """
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1]
    return datetime.fromisoformat(ts_str)
