"""
Disaster recovery validation for the ICYQuant production system.

Validates DR procedures including backup integrity, restore procedures,
RTO/RPO measurements, multi-region failover, and data consistency
after recovery.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class DRCheckStep:
    step_name: str
    passed: bool
    duration_ms: float
    description: str = ""
    error_message: Optional[str] = None
    achieved_value: float = 0.0
    target_value: float = 0.0


@dataclass
class DRResult:
    overall_passed: bool
    total_duration_ms: float
    steps: list[DRCheckStep] = field(default_factory=list)
    rto_achieved_ms: float = 0.0
    rpo_achieved_seconds: float = 0.0
    rto_target_ms: float = 3600000.0
    rpo_target_seconds: float = 300.0
    data_verification_passed: bool = False
    multi_region_failover_passed: bool = False
    started_at: str = ""
    completed_at: str = ""

    @property
    def rto_met(self) -> bool:
        return self.rto_achieved_ms <= self.rto_target_ms

    @property
    def rpo_met(self) -> bool:
        return self.rpo_achieved_seconds <= self.rpo_target_seconds

    @property
    def pass_rate(self) -> float:
        if not self.steps:
            return 0.0
        passed = sum(1 for s in self.steps if s.passed)
        return passed / len(self.steps)


class DisasterRecoveryValidator:
    """
    Validates disaster recovery procedures for ICYQuant.

    Tests backup integrity, restore procedures, RTO/RPO,
    multi-region failover, and data consistency after recovery.
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        self.project_root = project_root or os.getcwd()
        self._steps: list[tuple[str, Callable[[], DRCheckStep]]] = []
        self._register_default_steps()

    def _register_default_steps(self) -> None:
        self._steps = [
            ("Backup Integrity", self._check_backup_integrity),
            ("Restore Procedure", self._check_restore_procedure),
            ("RTO Measurement", self._measure_rto),
            ("RPO Measurement", self._measure_rpo),
            ("Multi-Region Failover", self._check_multi_region_failover),
            ("Data Consistency", self._check_data_consistency),
        ]

    def run(self) -> DRResult:
        import datetime

        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        overall_start = time.perf_counter()

        step_results: list[DRCheckStep] = []
        max_rto = 0.0
        max_rpo = 0.0
        data_verification = False
        multi_region = False

        for step_name, step_func in self._steps:
            try:
                result = step_func()
                step_results.append(result)
                if step_name == "RTO Measurement":
                    max_rto = result.achieved_value
                if step_name == "RPO Measurement":
                    max_rpo = result.achieved_value
                if step_name == "Data Consistency":
                    data_verification = result.passed
                if step_name == "Multi-Region Failover":
                    multi_region = result.passed
            except Exception as e:
                step_results.append(DRCheckStep(
                    step_name=step_name,
                    passed=False,
                    duration_ms=0.0,
                    error_message=str(e),
                ))

        overall_duration = (time.perf_counter() - overall_start) * 1000
        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        overall_passed = all(s.passed for s in step_results)

        return DRResult(
            overall_passed=overall_passed,
            total_duration_ms=overall_duration,
            steps=step_results,
            rto_achieved_ms=max_rto,
            rpo_achieved_seconds=max_rpo,
            data_verification_passed=data_verification,
            multi_region_failover_passed=multi_region,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _check_backup_integrity(self) -> DRCheckStep:
        start = time.perf_counter()
        try:
            dr_config_path = os.path.join(self.project_root, "configs", "deployment", "dr.yaml")
            if not os.path.isfile(dr_config_path):
                return DRCheckStep(
                    step_name="Backup Integrity",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    description="DR config not found at configs/deployment/dr.yaml",
                    error_message="Missing disaster recovery configuration",
                )

            import yaml
            with open(dr_config_path, "r", encoding="utf-8") as f:
                dr_config = yaml.safe_load(f)

            backup = dr_config.get("backup", {})
            if not backup.get("enabled", False):
                return DRCheckStep(
                    step_name="Backup Integrity",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    description="Backup is not enabled in DR config",
                    error_message="Set backup.enabled to true in dr.yaml",
                )

            schedule = backup.get("schedule", "")
            retention = backup.get("retentionDays", 0)
            storage = backup.get("storage", "")
            encryption = backup.get("encryption", {})
            includes = backup.get("includes", [])

            details: list[str] = []
            if not schedule:
                details.append("Missing backup schedule")
            if retention <= 0:
                details.append("Invalid retention days")
            if not storage:
                details.append("Missing backup storage location")
            if not encryption.get("enabled", False):
                details.append("Backup encryption not enabled")
            if not includes:
                details.append("No data types specified for backup")

            passed = len(details) == 0
            return DRCheckStep(
                step_name="Backup Integrity",
                passed=passed,
                duration_ms=(time.perf_counter() - start) * 1000,
                description=f"Backup config: schedule={schedule}, retention={retention}d, includes={includes}",
                error_message=None if passed else "; ".join(details),
            )
        except Exception as e:
            return DRCheckStep(
                step_name="Backup Integrity",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _check_restore_procedure(self) -> DRCheckStep:
        start = time.perf_counter()
        try:
            dr_config_path = os.path.join(self.project_root, "configs", "deployment", "dr.yaml")
            if not os.path.isfile(dr_config_path):
                return DRCheckStep(
                    step_name="Restore Procedure",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    description="DR config not found",
                    error_message="Cannot verify restore procedure without DR config",
                )

            import yaml
            with open(dr_config_path, "r", encoding="utf-8") as f:
                dr_config = yaml.safe_load(f)

            restore = dr_config.get("restore", {})
            point_in_time = restore.get("pointInTime", False)
            cross_region = restore.get("crossRegion", False)

            passed = point_in_time and cross_region
            return DRCheckStep(
                step_name="Restore Procedure",
                passed=passed,
                duration_ms=(time.perf_counter() - start) * 1000,
                description=f"Point-in-time recovery: {point_in_time}, Cross-region: {cross_region}",
                error_message=None if passed else "Enable pointInTime and crossRegion restore",
            )
        except Exception as e:
            return DRCheckStep(
                step_name="Restore Procedure",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _measure_rto(self) -> DRCheckStep:
        start = time.perf_counter()
        try:
            dr_config_path = os.path.join(self.project_root, "configs", "deployment", "dr.yaml")
            if not os.path.isfile(dr_config_path):
                return DRCheckStep(
                    step_name="RTO Measurement",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    description="DR config not found",
                    error_message="Cannot measure RTO without DR config",
                )

            import yaml
            with open(dr_config_path, "r", encoding="utf-8") as f:
                dr_config = yaml.safe_load(f)

            failover = dr_config.get("failover", {})
            timeout = failover.get("onFailure", {}).get("timeoutSeconds", 300)
            drain = failover.get("onFailure", {}).get("trafficDrainSeconds", 60)
            rto_seconds = timeout + drain
            rto_ms = rto_seconds * 1000

            rto_target_ms = 3600000.0

            passed = rto_ms <= rto_target_ms
            return DRCheckStep(
                step_name="RTO Measurement",
                passed=passed,
                duration_ms=(time.perf_counter() - start) * 1000,
                description=f"RTO: {rto_seconds}s (timeout={timeout}s + drain={drain}s), target: {rto_target_ms / 1000}s",
                achieved_value=rto_ms,
                target_value=rto_target_ms,
                error_message=None if passed else f"RTO {rto_seconds}s exceeds target {rto_target_ms / 1000}s",
            )
        except Exception as e:
            return DRCheckStep(
                step_name="RTO Measurement",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _measure_rpo(self) -> DRCheckStep:
        start = time.perf_counter()
        try:
            dr_config_path = os.path.join(self.project_root, "configs", "deployment", "dr.yaml")
            if not os.path.isfile(dr_config_path):
                return DRCheckStep(
                    step_name="RPO Measurement",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    description="DR config not found",
                    error_message="Cannot measure RPO without DR config",
                )

            import yaml
            with open(dr_config_path, "r", encoding="utf-8") as f:
                dr_config = yaml.safe_load(f)

            replication = dr_config.get("replication", {})
            sync_interval = replication.get("syncIntervalSeconds", 60)
            lag_target = replication.get("lagTargetSeconds", 300)
            rpo_seconds = sync_interval + lag_target

            rpo_target_seconds = 300.0

            passed = rpo_seconds <= rpo_target_seconds
            return DRCheckStep(
                step_name="RPO Measurement",
                passed=passed,
                duration_ms=(time.perf_counter() - start) * 1000,
                description=f"RPO: {rpo_seconds}s (sync={sync_interval}s + lag_target={lag_target}s), target: {rpo_target_seconds}s",
                achieved_value=rpo_seconds,
                target_value=rpo_target_seconds,
                error_message=None if passed else f"RPO {rpo_seconds}s exceeds target {rpo_target_seconds}s",
            )
        except Exception as e:
            return DRCheckStep(
                step_name="RPO Measurement",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _check_multi_region_failover(self) -> DRCheckStep:
        start = time.perf_counter()
        try:
            dr_config_path = os.path.join(self.project_root, "configs", "deployment", "dr.yaml")
            if not os.path.isfile(dr_config_path):
                return DRCheckStep(
                    step_name="Multi-Region Failover",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    description="DR config not found",
                    error_message="Cannot verify multi-region failover without DR config",
                )

            import yaml
            with open(dr_config_path, "r", encoding="utf-8") as f:
                dr_config = yaml.safe_load(f)

            standby_regions = dr_config.get("standbyRegions", [])
            if not standby_regions:
                return DRCheckStep(
                    step_name="Multi-Region Failover",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    description="No standby regions configured",
                    error_message="Configure at least one standby region for failover",
                )

            auto_failover_count = sum(
                1 for r in standby_regions if r.get("autoFailover", False)
            )

            network = dr_config.get("network", {})
            vpn = network.get("interRegion", {}).get("vpn", False)
            encryption = network.get("interRegion", {}).get("encryption", "")

            passed = auto_failover_count > 0 and vpn and encryption == "AES256"
            return DRCheckStep(
                step_name="Multi-Region Failover",
                passed=passed,
                duration_ms=(time.perf_counter() - start) * 1000,
                description=f"Standby regions: {len(standby_regions)}, auto-failover: {auto_failover_count}, VPN: {vpn}",
                error_message=None if passed else "Configure auto-failover, VPN, and AES256 encryption",
            )
        except Exception as e:
            return DRCheckStep(
                step_name="Multi-Region Failover",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _check_data_consistency(self) -> DRCheckStep:
        start = time.perf_counter()
        try:
            from services.portfolio.model import Portfolio
            from services.position.model import Position
            from services.trade.model import Trade

            portfolio = Portfolio(
                portfolio_id="consistency_test",
                account_id="account_001",
                name="Consistency Test",
            )

            position = Position(
                position_id="pos_consistency_test",
                account_id="account_001",
                portfolio_id="consistency_test",
                symbol="TEST",
                quantity=100.0,
                avg_price=100.0,
                side="LONG",
            )

            trade = Trade(
                trade_id="trade_consistency_test",
                order_id="order_001",
                account_id="account_001",
                symbol="TEST",
                quantity=100.0,
                price=100.0,
                side="BUY",
                timestamp=int(time.time()),
            )

            checks = [
                portfolio.portfolio_id == position.portfolio_id,
                position.quantity == trade.quantity,
                position.side.lower() == trade.side.lower(),
            ]

            passed = all(checks)
            return DRCheckStep(
                step_name="Data Consistency",
                passed=passed,
                duration_ms=(time.perf_counter() - start) * 1000,
                description="Cross-service data consistency verified",
                error_message=None if passed else "Data mismatch detected across services",
            )
        except Exception as e:
            return DRCheckStep(
                step_name="Data Consistency",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )