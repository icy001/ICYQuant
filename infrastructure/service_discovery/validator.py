"""Service discovery validation.

Provides ``ServiceValidator`` for validating service names, instance
identifiers, hosts, ports, versions, namespaces, and metadata with
thread-safe statistics tracking.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Dict, List

from .instance import ServiceInstance

logger = logging.getLogger(__name__)

_SERVICE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\-\.]{0,127}$")
_INSTANCE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\.:]{0,255}$")
_NAMESPACE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\-]{0,63}$")
_VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                         r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
                         r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")

_RESERVED_NAMESPACES = {"", "all", "null", "none", "default"}


class ServiceValidator:
    """Validates service discovery entities.

    Provides field-level validation for service instances and their
    components, accumulating per-call statistics in a thread-safe
    manner.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._validations = 0
        self._failures = 0
        self._by_field: Dict[str, int] = {}

    def validate_instance(self, instance: ServiceInstance) -> List[str]:
        """Validate a complete service instance.

        Args:
            instance: The ``ServiceInstance`` to validate.

        Returns:
            A list of validation error messages. An empty list
            indicates the instance is valid.
        """
        errors: List[str] = []
        if instance is None:
            return ["Instance is None."]
        with self._lock:
            self._validations += 1

        if not self.validate_service_name(instance.service_name):
            errors.append(f"Invalid service_name: {instance.service_name!r}")
            self._record_failure("service_name")
        if not self.validate_instance_id(instance.instance_id):
            errors.append(f"Invalid instance_id: {instance.instance_id!r}")
            self._record_failure("instance_id")
        if not self.validate_host(instance.host):
            errors.append(f"Invalid host: {instance.host!r}")
            self._record_failure("host")
        if not self.validate_port(instance.port):
            errors.append(f"Invalid port: {instance.port!r}")
            self._record_failure("port")
        if not self.validate_version(instance.version):
            errors.append(f"Invalid version: {instance.version!r}")
            self._record_failure("version")
        if not self.validate_namespace(instance.namespace):
            errors.append(f"Invalid namespace: {instance.namespace!r}")
            self._record_failure("namespace")
        meta_errors = self.validate_metadata(instance.metadata)
        for err in meta_errors:
            errors.append(err)
            self._record_failure("metadata")

        with self._lock:
            if errors:
                self._failures += 1
        if errors:
            logger.warning(
                "Instance '%s/%s' failed validation with %d error(s).",
                instance.service_name,
                instance.instance_id,
                len(errors),
            )
        return errors

    def validate_service_name(self, name: str) -> bool:
        """Validate a service name.

        Args:
            name: The service name to validate.

        Returns:
            True if the name is valid.
        """
        if not isinstance(name, str):
            return False
        return bool(_SERVICE_NAME_RE.match(name))

    def validate_instance_id(self, instance_id: str) -> bool:
        """Validate an instance identifier.

        Args:
            instance_id: The instance identifier to validate.

        Returns:
            True if the identifier is valid.
        """
        if not isinstance(instance_id, str):
            return False
        return bool(_INSTANCE_ID_RE.match(instance_id))

    def validate_host(self, host: str) -> bool:
        """Validate a host name or IP address.

        Accepts non-empty strings. Full IP/hostname validation is
        intentionally lightweight.

        Args:
            host: The host to validate.

        Returns:
            True if the host is valid.
        """
        if not isinstance(host, str) or not host:
            return False
        if len(host) > 255:
            return False
        if host.startswith(".") or host.endswith("."):
            return False
        return True

    def validate_port(self, port: int) -> bool:
        """Validate a port number.

        Args:
            port: The port to validate.

        Returns:
            True if the port is in the valid range (1-65535).
        """
        try:
            port_int = int(port)
        except (TypeError, ValueError):
            return False
        return 1 <= port_int <= 65535

    def validate_version(self, version: str) -> bool:
        """Validate a semantic version string.

        Args:
            version: The version to validate.

        Returns:
            True if the version matches semantic versioning rules.
        """
        if not isinstance(version, str) or not version:
            return False
        return bool(_VERSION_RE.match(version))

    def validate_namespace(self, namespace: str) -> bool:
        """Validate a namespace name.

        Args:
            namespace: The namespace to validate.

        Returns:
            True if the namespace is valid.
        """
        if not isinstance(namespace, str) or not namespace:
            return False
        return bool(_NAMESPACE_RE.match(namespace))

    def validate_metadata(self, metadata: Dict[str, Any]) -> List[str]:
        """Validate a metadata mapping.

        Args:
            metadata: The metadata mapping to validate.

        Returns:
            A list of validation error messages.
        """
        errors: List[str] = []
        if metadata is None:
            return errors
        if not isinstance(metadata, dict):
            errors.append("Metadata must be a dictionary.")
            return errors
        for key, value in metadata.items():
            if not isinstance(key, str) or not key:
                errors.append(f"Metadata key must be a non-empty string: {key!r}")
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                errors.append(
                    f"Metadata value for key '{key}' has unsupported type: "
                    f"{type(value).__name__}"
                )
        return errors

    def _record_failure(self, field: str) -> None:
        with self._lock:
            self._by_field[field] = self._by_field.get(field, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the validator.

        Returns:
            A dictionary with validation counts and per-field failure
            counts.
        """
        with self._lock:
            return {
                "total_validations": self._validations,
                "total_failures": self._failures,
                "failure_rate": (
                    self._failures / self._validations
                    if self._validations
                    else 0.0
                ),
                "failures_by_field": dict(self._by_field),
            }

    def __repr__(self) -> str:
        return (
            f"ServiceValidator(validations={self._validations}, "
            f"failures={self._failures})"
        )
