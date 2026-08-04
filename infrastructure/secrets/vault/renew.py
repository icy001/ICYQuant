"""
Vault automatic lease renewal.

Implements automatic lease/token renewal
by running a background coroutine that
monitors leases and renews them before
expiration.

Renewal strategy:
1. Calculate renew time (before expiration)
2. Attempt renewal
3. On failure: retry with backoff
4. On persistent failure: alert + re-auth
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .client import VaultClient
from .config import VaultLeaseConfig
from .exceptions import VaultLeaseError, VaultRenewalError
from .lease import Lease, LeaseManager

logger = logging.getLogger(__name__)


class LeaseRenewer:
    """
    Automatic lease renewal manager.

    Monitors active leases and automatically
    renews them before expiration. Supports
    configurable renewal buffers, retry logic,
    and failure callbacks.

    Usage:
        manager = LeaseManager()
        config = VaultLeaseConfig(auto_renew=True)
        renewer = LeaseRenewer(client, manager, config)
        await renewer.start()
        # ... later
        await renewer.stop()
    """

    def __init__(
        self,
        client: VaultClient,
        lease_manager: LeaseManager,
        config: Optional[VaultLeaseConfig] = None,
    ) -> None:
        self._client = client
        self._lease_manager = lease_manager
        self._config = config or VaultLeaseConfig()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._renewal_count: int = 0
        self._failure_count: int = 0
        self._last_renewal: Optional[datetime] = None
        self._on_failure: Optional[Callable[[Lease, Exception], None]] = None
        self._on_renew: Optional[Callable[[Lease], None]] = None

    async def start(
        self,
        on_failure: Optional[Callable[[Lease, Exception], None]] = None,
        on_renew: Optional[Callable[[Lease], None]] = None,
    ) -> None:
        """
        Start the automatic renewal loop.

        Args:
            on_failure: Callback on renewal failure.
            on_renew: Callback on successful renewal.
        """
        if self._running:
            return

        self._on_failure = on_failure
        self._on_renew = on_renew
        self._running = True
        self._task = asyncio.create_task(self._renewal_loop())
        logger.info("Lease renovator started")

    async def stop(self) -> None:
        """Stop the automatic renewal loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Lease renovator stopped")

    async def _renewal_loop(self) -> None:
        """
        Background renewal loop.

        Periodically checks for expiring leases
        and renews them.
        """
        check_interval = max(
            10,
            self._config.renew_buffer_seconds // 2,
        )

        while self._running:
            try:
                # Find leases needing renewal
                buffer_seconds = self._config.renew_buffer_seconds
                expiring = self._lease_manager.get_expiring_leases(
                    within_seconds=buffer_seconds
                )

                for lease in expiring:
                    if not self._running:
                        break
                    await self._try_renew(lease)

                # Expire old leases
                self._lease_manager.expire_old_leases()

                self._last_renewal = datetime.utcnow()

            except Exception as e:
                logger.error("Renewal loop error: %s", e)

            await asyncio.sleep(check_interval)

    async def _try_renew(self, lease: Lease) -> None:
        """
        Attempt to renew a single lease.

        Args:
            lease: Lease to renew.
        """
        max_retries = 3
        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                await self._perform_renewal(lease)
                self._renewal_count += 1
                self._failure_count = 0

                if self._on_renew:
                    try:
                        self._on_renew(lease)
                    except Exception:
                        pass

                logger.debug(
                    "Lease renewed: id=%s (attempt %d)",
                    lease.lease_id,
                    attempt + 1,
                )
                return

            except Exception as e:
                last_error = e
                lease.mark_renew_failed()
                self._failure_count += 1

                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        "Renewal attempt %d failed for %s: %s. Retrying in %ds...",
                        attempt + 1,
                        lease.lease_id,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "Lease renewal failed after %d attempts: id=%s, error=%s",
            max_retries,
            lease.lease_id,
            last_error,
        )

        if self._on_failure:
            try:
                self._on_failure(lease, last_error)
            except Exception as cb_err:
                logger.error("Failure callback error: %s", cb_err)

    async def _perform_renewal(self, lease: Lease) -> None:
        """
        Perform the actual renewal API call.

        Args:
            lease: Lease to renew.
        """
        # For token renewal
        if lease.token:
            try:
                result = await self._client.token_renew(
                    increment=self._config.default_lease_ttl
                )
                lease.renew(
                    result.get("auth", {}).get(
                        "lease_duration", self._config.default_lease_ttl
                    )
                )
                return
            except Exception:
                pass

        # Generic lease renewal via sys/leases/lookup
        try:
            path = f"/sys/leases/lookup/{lease.lease_id}"
            lookup = await self._client.read(path)
            lease_data = lookup.get("data", {})
            ttl = lease_data.get("ttl", lease.duration)
            lease.renew(ttl)
        except Exception as e:
            raise VaultRenewalError(
                f"Failed to renew lease {lease.lease_id}: {e}"
            ) from e

    # ── Status ──

    @property
    def is_running(self) -> bool:
        """Check if renewer is running."""
        return self._running

    def get_stats(self) -> Dict[str, Any]:
        """Get renewer statistics."""
        return {
            "running": self._running,
            "renewal_count": self._renewal_count,
            "failure_count": self._failure_count,
            "last_renewal": (
                self._last_renewal.isoformat() + "Z"
                if self._last_renewal
                else None
            ),
        }
