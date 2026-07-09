from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SafetyCheck:
    name: str
    passed: bool = False
    message: str = ""


@dataclass
class SafetyReport:
    checks: List[SafetyCheck] = field(default_factory=list)
    allowed: bool = False


class LiveSafetyGuard:
    def __init__(self, gateway, risk_monitor, portfolio, reconciler=None):
        self.gateway = gateway
        self.risk_monitor = risk_monitor
        self.portfolio = portfolio
        self.reconciler = reconciler
        self.report = SafetyReport()

    def perform_checks(self) -> SafetyReport:
        checks = [
            self._check_account(),
            self._check_risk(),
            self._check_position_sync(),
            self._check_reconciliation(),
            self._check_allow_trading(),
        ]

        self.report = SafetyReport(
            checks=checks,
            allowed=all(check.passed for check in checks),
        )

        return self.report

    def _check_account(self) -> SafetyCheck:
        try:
            account = self.gateway.get_account()
            if account and account.get("cash", 0) >= 0:
                return SafetyCheck("Account Check", True, "Account balance valid")
            return SafetyCheck("Account Check", False, "Invalid account data")
        except Exception as e:
            return SafetyCheck("Account Check", False, str(e))

    def _check_risk(self) -> SafetyCheck:
        try:
            account = self.gateway.get_account()
            if self.risk_monitor.allow_trade(account):
                return SafetyCheck("Risk Check", True, "Risk limits within bounds")
            return SafetyCheck("Risk Check", False, "Risk limits exceeded")
        except Exception as e:
            return SafetyCheck("Risk Check", False, str(e))

    def _check_position_sync(self) -> SafetyCheck:
        try:
            gateway_positions = self.gateway.get_positions()
            portfolio_positions = self.portfolio.positions

            if gateway_positions == portfolio_positions:
                return SafetyCheck("Position Sync", True, "Positions in sync")
            return SafetyCheck("Position Sync", False, "Position mismatch detected")
        except Exception as e:
            return SafetyCheck("Position Sync", False, str(e))

    def _check_reconciliation(self) -> SafetyCheck:
        try:
            if self.reconciler:
                report = self.reconciler.run()
                if report.is_healthy:
                    return SafetyCheck("Reconciliation", True, "Reconciliation passed")
                return SafetyCheck("Reconciliation", False, "Reconciliation failed")
            return SafetyCheck("Reconciliation", True, "Reconciler not configured")
        except Exception as e:
            return SafetyCheck("Reconciliation", False, str(e))

    def _check_allow_trading(self) -> SafetyCheck:
        return SafetyCheck("Allow Trading", True, "Trading enabled")