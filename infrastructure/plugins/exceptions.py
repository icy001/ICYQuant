"""Plugin exception hierarchy.

Defines the exception hierarchy used across the ICYQuant plugin
framework, enabling precise error handling for plugin lifecycle,
dependency, validation, and configuration issues.
"""

from __future__ import annotations

from typing import Any, Dict


class PluginError(Exception):
    """Base exception for all plugin errors."""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the error to a dictionary.

        Returns:
            A dictionary with the error type name and message.
        """
        return {
            "error": type(self).__name__,
            "message": str(self),
        }


class PluginNotFoundError(PluginError):
    """Raised when a plugin cannot be found."""


class PluginAlreadyExistsError(PluginError):
    """Raised when a plugin is registered more than once."""


class PluginLoadError(PluginError):
    """Raised when a plugin fails to load."""


class PluginInitError(PluginError):
    """Raised when a plugin fails to initialize."""


class PluginStartError(PluginError):
    """Raised when a plugin fails to start."""


class PluginStopError(PluginError):
    """Raised when a plugin fails to stop."""


class PluginUnloadError(PluginError):
    """Raised when a plugin fails to unload."""


class PluginValidationError(PluginError):
    """Raised when plugin validation fails."""


class PluginDependencyError(PluginError):
    """Base exception for plugin dependency errors."""


class PluginCircularDependencyError(PluginDependencyError):
    """Raised when a circular dependency is detected among plugins."""


class PluginMissingDependencyError(PluginDependencyError):
    """Raised when a required plugin dependency is missing."""


class PluginPermissionError(PluginError):
    """Raised when a plugin lacks the permissions required for an operation."""


class PluginCapabilityError(PluginError):
    """Raised when a plugin does not provide a required capability."""


class PluginManifestError(PluginError):
    """Raised when a plugin manifest is invalid or cannot be parsed."""


class PluginConfigError(PluginError):
    """Raised when plugin configuration is invalid."""


class PluginStateError(PluginError):
    """Raised when a plugin is in an invalid state for an operation."""


class PluginInstallError(PluginError):
    """Raised when a plugin fails to install."""


class PluginReloadError(PluginError):
    """Raised when a plugin fails to reload."""


class PluginSandboxError(PluginError):
    """Base exception for sandbox-related errors."""


class PluginSecurityError(PluginError):
    """Base exception for security-related errors."""


class PluginSignatureError(PluginSecurityError):
    """Raised when plugin signature verification fails."""


class PluginTrustError(PluginSecurityError):
    """Raised when a plugin is not in the trust store."""


class PluginResourceLimitError(PluginSandboxError):
    """Raised when a plugin exceeds its resource limits."""


class PluginIsolationError(PluginSandboxError):
    """Raised when plugin isolation fails."""


class PluginSandboxViolationError(PluginSandboxError):
    """Raised when a plugin violates sandbox constraints."""


class PluginNetworkAccessError(PluginSandboxError):
    """Raised when a plugin violates network policy."""


class PluginFilesystemAccessError(PluginSandboxError):
    """Raised when a plugin violates filesystem policy."""


class PluginSecretAccessError(PluginSecurityError):
    """Raised when a plugin attempts unauthorized secret access."""


class PluginWatchError(PluginError):
    """Raised when a file watch error occurs."""
