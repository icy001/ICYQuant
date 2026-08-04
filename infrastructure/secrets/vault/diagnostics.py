"""
Vault Diagnostics toolkit.

Provides comprehensive diagnostic tools
for troubleshooting Vault integration
issues, including:
- Connection diagnostics
- Authentication diagnostics
- Performance profiling
- Configuration validation
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from .client import VaultClient
from .config import VaultConfig
from .exceptions import VaultError

logger = logging.getLogger(__name__)


class VaultDiagnostics:
    """
    Vault diagnostic toolkit.

    Provides tools for diagnosing and
    troubleshooting Vault integration
    issues in production environments.

    Usage:
        diagnostics = VaultDiagnostics(config)
        report = await diagnostics.run_full_diagnostics()
    """

    def __init__(self, config: VaultConfig) -> None:
        self._config = config
        self._reports: List[Dict[str, Any]] = []

    async def run_full_diagnostics(self) -> Dict[str, Any]:
        """
        Run all diagnostic checks.

        Returns:
            Comprehensive diagnostic report.
        """
        start = time.perf_counter()
        report: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "config": self._sanitize_config(),
            "checks": {},
            "summary": {},
        }

        # Check 1: Configuration validation
        report["checks"]["config"] = self._check_config()

        # Check 2: Connection test
        conn_ok, conn_info = await self._check_connection()
        report["checks"]["connection"] = {
            "passed": conn_ok,
            **conn_info,
        }

        # Check 3: Authentication test
        auth_ok, auth_info = await self._check_authentication()
        report["checks"]["authentication"] = {
            "passed": auth_ok,
            **auth_info,
        }

        # Check 4: KV engine test
        if conn_ok:
            kv_ok, kv_info = await self._check_kv_engine()
            report["checks"]["kv_engine"] = {
                "passed": kv_ok,
                **kv_info,
            }
        else:
            report["checks"]["kv_engine"] = {
                "passed": False,
                "error": "Cannot check KV engine without connection",
            }

        # Check 5: Lease test
        lease_ok, lease_info = await self._check_lease_management()
        report["checks"]["lease"] = {
            "passed": lease_ok,
            **lease_info,
        }

        # Summary
        total_checks = len(report["checks"])
        passed = sum(
            1 for c in report["checks"].values() if c.get("passed", False)
        )
        report["summary"] = {
            "total_checks": total_checks,
            "passed": passed,
            "failed": total_checks - passed,
            "all_passed": passed == total_checks,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        }

        # Store report
        self._reports.append(report)
        if len(self._reports) > 100:
            self._reports = self._reports[-100:]

        return report

    def _sanitize_config(self) -> Dict[str, Any]:
        """Get sanitized configuration (no secrets)."""
        config_dict = self._config.dict()

        # Remove sensitive values
        config_dict["auth"]["token"]["token"] = "***REDACTED***"
        config_dict["auth"]["approle"]["secret_id"] = "***REDACTED***"
        config_dict["auth"]["jwt"]["jwt_token"] = "***REDACTED***"

        return config_dict

    def _check_config(self) -> Dict[str, Any]:
        """Validate configuration."""
        issues: List[str] = []

        if not self._config.address:
            issues.append("Vault address is not configured")

        if not self._config.auth.method:
            issues.append("Authentication method not configured")

        if self._config.auto_renew and not self._config.lease.auto_renew:
            issues.append("Auto-renew enabled but lease auto-renew disabled")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "config_summary": {
                "address": self._config.address,
                "namespace": self._config.namespace,
                "mount": self._config.mount,
                "auth_method": self._config.auth.method,
                "tls_enabled": self._config.tls.enabled,
                "auto_renew": self._config.auto_renew,
            },
        }

    async def _check_connection(self) -> tuple:
        """Test Vault connection."""
        try:
            client = VaultClient(self._config)
            await client.connect()

            start = time.perf_counter()
            health = await client.check_health(standby_ok=True)
            latency_ms = (time.perf_counter() - start) * 1000

            await client.disconnect()

            if health.get("healthy"):
                return True, {
                    "message": "Connection successful",
                    "latency_ms": round(latency_ms, 2),
                    "version": health.get("version", "unknown"),
                    "cluster": health.get("cluster_name", "unknown"),
                    "standby": health.get("standby", False),
                }
            else:
                return False, {
                    "error": health.get("error", "Unknown"),
                    "latency_ms": round(latency_ms, 2),
                }

        except Exception as e:
            return False, {
                "error": str(e),
                "type": type(e).__name__,
            }

    async def _check_authentication(self) -> tuple:
        """Test authentication."""
        auth_method = self._config.auth.method

        if auth_method == "token" and self._config.auth.token:
            from .token import TokenAuthenticator
            try:
                client = VaultClient(self._config)
                await client.connect()
                auth = TokenAuthenticator(self._config.auth.token)
                result = await auth.login(client)
                await client.disconnect()
                return True, {
                    "method": "token",
                    "authenticated": True,
                    "token_renewable": result.get("renewable", False),
                }
            except Exception as e:
                return False, {
                    "method": "token",
                    "error": str(e),
                }
        else:
            return True, {
                "method": auth_method,
                "note": "Configuration check only (no credentials to test)",
            }

    async def _check_kv_engine(self) -> tuple:
        """Test KV secrets engine."""
        test_key = f"_diagnostics/test_{int(time.time())}"
        test_value = f"diagnostic_test_{int(time.time())}"

        try:
            client = VaultClient(self._config)
            await client.connect()

            # Try to write
            write_path = f"/{self._config.mount}/data/{test_key}"
            await client.write(write_path, payload={"data": {"value": test_value}})

            # Try to read
            result = await client.read(write_path)
            read_value = result.get("data", {}).get("data", {}).get("value")

            # Clean up
            await client.delete(write_path)
            await client.disconnect()

            return True, {
                "write_ok": True,
                "read_ok": read_value == test_value,
                "cleanup_ok": True,
                "mount": self._config.mount,
            }
        except Exception as e:
            return False, {
                "error": str(e),
                "mount": self._config.mount,
            }

    async def _check_lease_management(self) -> tuple:
        """Test lease management."""
        from .lease import Lease, LeaseManager

        manager = LeaseManager()
        lease = manager.add_lease(
            lease_id="diag-lease",
            duration=300,
            renewable=True,
        )

        # Test renewal
        original_expire = lease.expire_at
        lease.renew()
        renewed = lease.expire_at > original_expire

        # Test revocation
        lease.revoke()
        revoked = not lease.is_active

        return renewed and revoked, {
            "renew_ok": renewed,
            "revoke_ok": revoked,
            "active_leases": len(manager.get_active_leases()),
        }

    def get_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent diagnostic reports."""
        return self._reports[-limit:]

    def format_report(self, report: Dict[str, Any]) -> str:
        """Format a diagnostic report as readable text."""
        lines = []
        lines.append("=" * 60)
        lines.append("Vault Diagnostic Report")
        lines.append(f"  Generated: {report['timestamp']}")
        lines.append(f"  Duration: {report['summary']['duration_ms']}ms")
        lines.append("")

        for name, check in report["checks"].items():
            status = "PASS" if check.get("passed", False) else "FAIL"
            lines.append(f"  [{status}] {name}:")
            for key, value in check.items():
                if key == "passed":
                    continue
                lines.append(f"    {key}: {value}")
            lines.append("")

        lines.append(f"  Summary: {report['summary']['passed']}/{report['summary']['total_checks']} passed")
        lines.append("=" * 60)
        return "\n".join(lines)
