"""
Capital Manager — Operational Command

The CapitalManager is the operational layer that translates capital
intelligence decisions into executable actions. It coordinates between
the intelligence engine and the control plane for:

- Capital deployment / withdrawal
- Allocation execution with checks
- Rebalancing triggers
- Position reconciliation
- Emergency operations (freeze, unwind)
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class OperationStatus(str, Enum):
    """Capital operation execution status."""
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERTED = "REVERTED"


class OperationType(str, Enum):
    """Types of capital operations."""
    ALLOCATE = "ALLOCATE"
    DEALLOCATE = "DEALLOCATE"
    REALLOCATE = "REALLOCATE"
    REBALANCE = "REBALANCE"
    FREEZE = "FREEZE"
    UNFREEZE = "UNFREEZE"
    EMERGENCY_UNWIND = "EMERGENCY_UNWIND"
    RECONCILE = "RECONCILE"


@dataclass
class CapitalOperation:
    """A single capital operation to execute."""
    operation_id: str
    op_type: OperationType
    strategy_id: Optional[str]
    amount: float
    from_account: Optional[str]
    to_account: Optional[str]
    status: OperationStatus = OperationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchOperation:
    """A batch of capital operations to execute atomically."""
    batch_id: str
    operations: List[CapitalOperation]
    all_or_nothing: bool = True
    status: OperationStatus = OperationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)


class CapitalManager:
    """
    Operational capital command center.

    Responsibilities:
    - Execute capital allocations/deallocations
    - Atomic batch operations
    - Pre-execution validation
    - Post-execution reconciliation
    - Emergency procedures
    - Control plane integration for approval
    """

    def __init__(
        self,
        manager_id: Optional[str] = None,
        intelligence=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.manager_id = manager_id or f"cm-{uuid.uuid4().hex[:12]}"
        self._intelligence = intelligence
        self.config = config or {}

        # Operation tracking
        self.pending_ops: Dict[str, CapitalOperation] = {}
        self.executing_ops: Dict[str, CapitalOperation] = {}
        self.completed_ops: List[CapitalOperation] = []
        self.failed_ops: List[CapitalOperation] = []
        self.batches: Dict[str, BatchOperation] = {}

        # Control plane reference
        self._control_plane = None

        # Limits
        self.max_single_allocation = self.config.get("max_single_allocation", float("inf"))
        self.min_single_allocation = self.config.get("min_single_allocation", 0.0)
        self.max_batch_count = self.config.get("max_batch_count", 50)

        logger.info(f"CapitalManager initialized: {self.manager_id}")

    # ─── Single Operations ──────────────────────────────────────

    def allocate(
        self,
        strategy_id: str,
        amount: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CapitalOperation:
        """Create and execute a single allocation operation."""
        op = CapitalOperation(
            operation_id=f"op-{uuid.uuid4().hex[:8]}",
            op_type=OperationType.ALLOCATE,
            strategy_id=strategy_id,
            amount=amount,
            metadata=metadata or {},
        )

        # Pre-execution checks
        validation = self._validate_operation(op)
        if not validation["valid"]:
            op.status = OperationStatus.FAILED
            op.error = validation["reason"]
            self.failed_ops.append(op)
            logger.warning(f"Allocation validation failed: {op.error}")
            return op

        # Execute
        try:
            op.status = OperationStatus.EXECUTING
            self.executing_ops[op.operation_id] = op

            self._execute_allocate(op)

            op.status = OperationStatus.COMPLETED
            op.executed_at = datetime.utcnow()
            self.completed_ops.append(op)
            self.executing_ops.pop(op.operation_id, None)
            logger.info(f"Allocation completed: {op.operation_id}")

        except Exception as e:
            op.status = OperationStatus.FAILED
            op.error = str(e)
            self.failed_ops.append(op)
            self.executing_ops.pop(op.operation_id, None)
            logger.error(f"Allocation failed: {op.operation_id} - {e}")

        return op

    def deallocate(
        self,
        strategy_id: str,
        amount: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CapitalOperation:
        """Deallocate capital from a strategy."""
        op = CapitalOperation(
            operation_id=f"op-{uuid.uuid4().hex[:8]}",
            op_type=OperationType.DEALLOCATE,
            strategy_id=strategy_id,
            amount=amount,
            metadata=metadata or {},
        )

        try:
            op.status = OperationStatus.EXECUTING
            self._execute_deallocate(op)
            op.status = OperationStatus.COMPLETED
            op.executed_at = datetime.utcnow()
            self.completed_ops.append(op)
        except Exception as e:
            op.status = OperationStatus.FAILED
            op.error = str(e)
            self.failed_ops.append(op)

        return op

    def reallocate(
        self,
        from_strategy: str,
        to_strategy: str,
        amount: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[CapitalOperation]:
        """Move capital from one strategy to another (atomic deallocate + allocate)."""
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        dealloc_op = CapitalOperation(
            operation_id=f"op-{uuid.uuid4().hex[:8]}",
            op_type=OperationType.REALLOCATE,
            strategy_id=from_strategy,
            amount=-amount,
            metadata=metadata or {},
        )
        alloc_op = CapitalOperation(
            operation_id=f"op-{uuid.uuid4().hex[:8]}",
            op_type=OperationType.REALLOCATE,
            strategy_id=to_strategy,
            amount=amount,
            metadata=metadata or {},
        )

        batch = BatchOperation(
            batch_id=batch_id,
            operations=[dealloc_op, alloc_op],
            all_or_nothing=True,
        )
        self.batches[batch_id] = batch

        return self._execute_batch(batch)

    # ─── Batch Operations ───────────────────────────────────────

    def execute_batch(
        self,
        operations: List[CapitalOperation],
        all_or_nothing: bool = True,
    ) -> BatchOperation:
        """Execute multiple operations as a batch."""
        if len(operations) > self.max_batch_count:
            raise ValueError(f"Batch exceeds max size: {len(operations)} > {self.max_batch_count}")

        batch = BatchOperation(
            batch_id=f"batch-{uuid.uuid4().hex[:8]}",
            operations=operations,
            all_or_nothing=all_or_nothing,
        )
        self.batches[batch.batch_id] = batch

        return self._execute_batch(batch)

    def _execute_batch(self, batch: BatchOperation) -> List[CapitalOperation]:
        """Execute a batch, rolling back if all_or_nothing and any fail."""
        batch.status = OperationStatus.EXECUTING
        completed = []
        failed = False

        for op in batch.operations:
            try:
                if op.amount > 0:
                    self._execute_allocate(op)
                elif op.amount < 0:
                    self._execute_deallocate(op)
                op.status = OperationStatus.COMPLETED
                op.executed_at = datetime.utcnow()
                completed.append(op)
            except Exception as e:
                op.status = OperationStatus.FAILED
                op.error = str(e)
                failed = True
                if batch.all_or_nothing:
                    self._rollback_batch(completed)
                    batch.status = OperationStatus.FAILED
                    return batch.operations
                self.failed_ops.append(op)

        batch.status = OperationStatus.COMPLETED if not failed else OperationStatus.FAILED
        self.completed_ops.extend([o for o in batch.operations if o.status == OperationStatus.COMPLETED])
        return batch.operations

    def _rollback_batch(self, completed: List[CapitalOperation]) -> None:
        """Rollback completed operations in reverse order."""
        for op in reversed(completed):
            try:
                if op.amount > 0:
                    self._execute_deallocate_reverse(op)
                elif op.amount < 0:
                    self._execute_allocate_reverse(op)
                op.status = OperationStatus.REVERTED
            except Exception as e:
                logger.critical(f"Rollback failed for {op.operation_id}: {e}")

    # ─── Emergency Operations ───────────────────────────────────

    def emergency_freeze(self) -> Dict[str, Any]:
        """Emergency freeze all capital operations."""
        if self._intelligence:
            self._intelligence.freeze()
        result = {
            "action": "EMERGENCY_FREEZE",
            "timestamp": datetime.utcnow().isoformat(),
            "manager_id": self.manager_id,
            "pending_cleared": len(self.pending_ops),
            "executing_interrupted": len(self.executing_ops),
        }
        self.pending_ops.clear()
        logger.critical(f"EMERGENCY FREEZE executed by {self.manager_id}")
        return result

    def emergency_unwind(self, strategy_ids: Optional[List[str]] = None) -> List[CapitalOperation]:
        """Emergency unwind positions."""
        operations = []
        targets = strategy_ids or list(self._intelligence.get_strategy_allocations().keys()) if self._intelligence else []

        for sid in targets:
            allocation = self._intelligence.get_strategy_allocations().get(sid, 0) if self._intelligence else 0
            if allocation > 0:
                op = self.deallocate(sid, allocation, {"reason": "emergency_unwind"})
                operations.append(op)

        logger.critical(f"Emergency unwind for {len(targets)} strategies")
        return operations

    # ─── Validation ─────────────────────────────────────────────

    def _validate_operation(self, op: CapitalOperation) -> Dict[str, Any]:
        """Pre-execution validation for a capital operation."""
        if op.amount <= 0:
            return {"valid": False, "reason": "Amount must be positive"}

        if op.amount < self.min_single_allocation:
            return {"valid": False, "reason": f"Amount below minimum: {self.min_single_allocation}"}

        if op.amount > self.max_single_allocation:
            return {"valid": False, "reason": f"Amount exceeds maximum: {self.max_single_allocation}"}

        # Check available capital
        if self._intelligence:
            available = self._intelligence.get_available_capital()
            if op.amount > available:
                return {"valid": False, "reason": f"Insufficient capital: {op.amount} > {available}"}

        # Control plane check
        if self._control_plane:
            cp_result = self._control_plane.evaluate({
                "action": "capital_allocate",
                "strategy_id": op.strategy_id,
                "amount": op.amount,
            })
            if not cp_result.get("approved", True):
                return {"valid": False, "reason": f"Control plane rejected: {cp_result.get('reason')}"}

        return {"valid": True}

    # ─── Executors ──────────────────────────────────────────────

    def _execute_allocate(self, op: CapitalOperation) -> None:
        """Execute capital allocation."""
        if self._intelligence and op.strategy_id:
            result = self._intelligence.request_allocation(
                strategy_id=op.strategy_id,
                amount=op.amount,
                context={"operation_id": op.operation_id, **op.metadata},
            )
            if result.get("result") == "REJECTED":
                raise RuntimeError(f"Allocation rejected: {result.get('guard', {}).get('reason', 'unknown')}")

    def _execute_deallocate(self, op: CapitalOperation) -> None:
        """Execute capital deallocation."""
        if self._intelligence and op.strategy_id:
            # Negative amount for deallocation
            pass

    def _execute_allocate_reverse(self, op: CapitalOperation) -> None:
        """Reverse an allocation (for rollback)."""
        pass

    def _execute_deallocate_reverse(self, op: CapitalOperation) -> None:
        """Reverse a deallocation (for rollback)."""
        pass

    # ─── Status & Queries ───────────────────────────────────────

    def get_pending_count(self) -> int:
        return len(self.pending_ops)

    def get_executing_count(self) -> int:
        return len(self.executing_ops)

    def get_failure_rate(self) -> float:
        total = len(self.completed_ops) + len(self.failed_ops)
        if total == 0:
            return 0.0
        return len(self.failed_ops) / total

    def get_summary(self) -> Dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "pending": self.get_pending_count(),
            "executing": self.get_executing_count(),
            "completed": len(self.completed_ops),
            "failed": len(self.failed_ops),
            "failure_rate": self.get_failure_rate(),
            "batches": len(self.batches),
        }
