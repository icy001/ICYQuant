"""Service discovery exception hierarchy.

Defines the exception hierarchy used across the ICYQuant service
discovery module, enabling precise error handling for registration,
deregistration, resolution, lease, namespace, adapter, and
validation issues.
"""

from __future__ import annotations

from typing import Any, Dict


class ServiceDiscoveryError(Exception):
    """Base exception for all service discovery errors."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the error to a dictionary.

        Returns:
            A dictionary with the error type name and message.
        """
        return {
            "error": type(self).__name__,
            "message": str(self),
        }


class ServiceRegistrationError(ServiceDiscoveryError):
    """Raised when service registration fails."""


class ServiceDeregistrationError(ServiceDiscoveryError):
    """Raised when service deregistration fails."""


class ServiceNotFoundError(ServiceDiscoveryError):
    """Raised when a requested service cannot be found."""


class ServiceUnavailableError(ServiceDiscoveryError):
    """Raised when no healthy instances are available for a service."""


class NamespaceError(ServiceDiscoveryError):
    """Raised when there is an issue with a namespace operation."""


class LeaseExpiredError(ServiceDiscoveryError):
    """Raised when a service lease has expired."""


class LeaseRenewalError(ServiceDiscoveryError):
    """Raised when service lease renewal fails."""


class RegistryError(ServiceDiscoveryError):
    """Raised when the service registry encounters an internal error."""


class AdapterError(ServiceDiscoveryError):
    """Base exception for service discovery adapter errors."""


class AdapterNotReadyError(AdapterError):
    """Raised when a service discovery adapter is not ready for use."""


class AdapterConnectionError(AdapterError):
    """Raised when a service discovery adapter connection fails."""


class ValidationError(ServiceDiscoveryError):
    """Raised when service discovery validation fails."""


class ResolverError(ServiceDiscoveryError):
    """Raised when service resolution fails."""


class DiscoveryTimeoutError(ServiceDiscoveryError):
    """Raised when a service discovery operation times out."""
