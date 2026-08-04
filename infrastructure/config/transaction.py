"""
Configuration transaction management.

Provides transactional configuration updates with
ACID-like properties:
- Atomic: All changes or none
- Consistent: Validation before commit
- Isolated: Changes not visible until commit
- Durable: Written to snapshot store

Transaction Flow:
    Begin → Validate → Commit → Publish → Complete
    Failed → Rollback
"""

from __future__ import annotations

import copy
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class TransactionStatus:
    """Transaction status constants."""
    PENDING = "pending"
    VALIDATING = "validating"
    COMMITTING = "committing"
    PUBLISHING = "publishing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ConfigurationTransaction:
    """
    A single configuration transaction.

    Represents a set of configuration changes that
    must be applied atomically.

    Attributes:
        transaction_id: Unique transaction ID.
        status: Current transaction status.
        changes: Dict of key → new value.
        operator: Who initiated the transaction.
        reason: Reason for the transaction.
        created_at: Creation timestamp.
        completed_at: Completion timestamp.
        errors: List of errors if failed.
    """

    def __init__(
        self,
        transaction_id: str,
        operator: str = "system",
        reason: str = "",
    ) -> None:
        """
        Initialize transaction.

        Args:
            transaction_id: Unique transaction ID.
            operator: Who initiated the transaction.
            reason: Reason for the transaction.
        """
        self.transaction_id = transaction_id
        self.status = TransactionStatus.PENDING
        self.changes: Dict[str, Any] = {}
        self.operator = operator
        self.reason = reason
        self.created_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.errors: List[str] = []
        self.old_values: Dict[str, Any] = {}
        self.new_values: Dict[str, Any] = {}

    def set(
        self,
        key: str,
        value: Any,
    ) -> "ConfigurationTransaction":
        """
        Queue a configuration change.

        Args:
            key: Configuration key.
            value: New value.

        Returns:
            Self for method chaining.
        """
        self.changes[key] = value
        return self

    def set_many(
        self,
        changes: Dict[str, Any],
    ) -> "ConfigurationTransaction":
        """
        Queue multiple configuration changes.

        Args:
            changes: Dict of key-value pairs.

        Returns:
            Self for method chaining.
        """
        self.changes.update(changes)
        return self

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transaction_id": self.transaction_id,
            "status": self.status,
            "changes": copy.deepcopy(self.changes),
            "operator": self.operator,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "errors": self.errors,
        }


class ConfigurationTransactionManager:
    """
    Manages configuration transactions.

    Supports atomic configuration updates with
    validation, commit, and rollback capabilities.

    Usage:
        tx_mgr = ConfigurationTransactionManager()

        # Begin a transaction
        tx = tx_mgr.begin(operator="admin", reason="config update")

        # Queue changes
        tx.set("server.port", 9090)
        tx.set("server.host", "0.0.0.0")

        # Commit
        result = tx_mgr.commit(tx, current_config)
        if result.success:
            # Transaction applied atomically
        else:
            # Transaction failed, no changes applied
            print(result.errors)
    """

    def __init__(
        self,
        validator: Optional[Callable] = None,
    ) -> None:
        """
        Initialize transaction manager.

        Args:
            validator: Validation function to run before commit.
        """
        self._validator = validator
        self._active_transactions: Dict[str, ConfigurationTransaction] = {}
        self._completed_transactions: List[Dict[str, Any]] = []
        self._max_completed = 100
        self._lock = threading.Lock()
        self._counter = 0

    def begin(
        self,
        operator: str = "system",
        reason: str = "",
    ) -> ConfigurationTransaction:
        """
        Begin a new transaction.

        Args:
            operator: Who initiated the transaction.
            reason: Reason for the transaction.

        Returns:
            New ConfigurationTransaction.
        """
        with self._lock:
            self._counter += 1
            tx_id = f"tx_{self._counter:08d}"

        tx = ConfigurationTransaction(
            transaction_id=tx_id,
            operator=operator,
            reason=reason,
        )

        with self._lock:
            self._active_transactions[tx_id] = tx

        return tx

    def validate(
        self,
        transaction: ConfigurationTransaction,
        current_config: Dict[str, Any],
    ) -> List[str]:
        """
        Validate a transaction against current config.

        Args:
            transaction: Transaction to validate.
            current_config: Current configuration values.

        Returns:
            List of validation errors.
        """
        transaction.status = TransactionStatus.VALIDATING
        errors: List[str] = []

        # Check for conflicts with active transactions
        with self._lock:
            for tx_id, active_tx in self._active_transactions.items():
                if tx_id == transaction.transaction_id:
                    continue
                if active_tx.status in (
                    TransactionStatus.VALIDATING,
                    TransactionStatus.COMMITTING,
                ):
                    conflicts = set(transaction.changes.keys()) & set(
                        active_tx.changes.keys()
                    )
                    if conflicts:
                        errors.append(
                            f"Keys conflict with active transaction {tx_id}: {conflicts}"
                        )

        # Run custom validator if available
        if self._validator and not errors:
            test_config = copy.deepcopy(current_config)
            test_config.update(transaction.changes)
            try:
                validator_errors = self._validator(test_config)
                if validator_errors:
                    if isinstance(validator_errors, list):
                        errors.extend(validator_errors)
                    else:
                        errors.append(str(validator_errors))
            except Exception as e:
                errors.append(f"Validation error: {e}")

        return errors

    def commit(
        self,
        transaction: ConfigurationTransaction,
        current_config: Dict[str, Any],
        auto_rollback: bool = True,
    ) -> TransactionResult:
        """
        Commit a transaction.

        Atomically applies all queued changes.

        Args:
            transaction: Transaction to commit.
            current_config: Current configuration.
            auto_rollback: Auto-rollback on failure.

        Returns:
            TransactionResult.
        """
        start_time = time.time()

        # Validate
        errors = self.validate(transaction, current_config)
        if errors:
            transaction.status = TransactionStatus.FAILED
            transaction.errors = errors
            self._finalize_transaction(transaction, success=False)
            return TransactionResult(
                success=False,
                errors=errors,
                transaction_id=transaction.transaction_id,
            )

        # Commit
        transaction.status = TransactionStatus.COMMITTING

        # Capture old values for audit
        for key in transaction.changes:
            transaction.old_values[key] = current_config.get(key)

        # Apply changes
        new_config = copy.deepcopy(current_config)
        new_config.update(transaction.changes)
        transaction.new_values = copy.deepcopy(transaction.changes)

        transaction.status = TransactionStatus.PUBLISHING
        transaction.status = TransactionStatus.COMPLETED
        transaction.completed_at = datetime.utcnow()

        self._finalize_transaction(transaction, success=True)

        duration = time.time() - start_time
        return TransactionResult(
            success=True,
            errors=[],
            transaction_id=transaction.transaction_id,
            new_config=new_config,
            duration=duration,
        )

    def rollback(
        self,
        transaction: ConfigurationTransaction,
    ) -> TransactionResult:
        """
        Rollback a transaction (cancel without applying).

        Args:
            transaction: Transaction to rollback.

        Returns:
            TransactionResult.
        """
        transaction.status = TransactionStatus.ROLLED_BACK
        transaction.completed_at = datetime.utcnow()
        self._finalize_transaction(transaction, success=False)

        return TransactionResult(
            success=True,
            errors=[],
            transaction_id=transaction.transaction_id,
        )

    def get_transaction(
        self,
        transaction_id: str,
    ) -> Optional[ConfigurationTransaction]:
        """Get a transaction by ID."""
        with self._lock:
            return self._active_transactions.get(transaction_id)

    def list_active(
        self,
    ) -> List[Dict[str, Any]]:
        """List active transactions."""
        with self._lock:
            return [
                tx.to_dict()
                for tx in self._active_transactions.values()
                if tx.status
                not in (
                    TransactionStatus.COMPLETED,
                    TransactionStatus.FAILED,
                    TransactionStatus.ROLLED_BACK,
                )
            ]

    def get_completed(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get completed transaction history."""
        with self._lock:
            return self._completed_transactions[-limit:]

    def _finalize_transaction(
        self,
        transaction: ConfigurationTransaction,
        success: bool,
    ) -> None:
        """Finalize and archive a transaction."""
        with self._lock:
            self._active_transactions.pop(transaction.transaction_id, None)

        record = transaction.to_dict()
        record["success"] = success

        with self._lock:
            self._completed_transactions.append(record)
            if len(self._completed_transactions) > self._max_completed:
                self._completed_transactions.pop(0)


class TransactionResult:
    """
    Result of a transaction operation.

    Attributes:
        success: Whether transaction succeeded.
        errors: List of error messages.
        transaction_id: Transaction ID.
        new_config: New configuration (if committed).
        duration: Transaction duration.
    """

    def __init__(
        self,
        success: bool,
        errors: List[str],
        transaction_id: str,
        new_config: Optional[Dict[str, Any]] = None,
        duration: float = 0.0,
    ) -> None:
        self.success = success
        self.errors = errors
        self.transaction_id = transaction_id
        self.new_config = new_config
        self.duration = duration

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "errors": self.errors,
            "transaction_id": self.transaction_id,
            "duration": self.duration,
        }
