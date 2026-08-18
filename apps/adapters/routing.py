"""Order routing - decides which account receives an OrderIntent.

Routing criteria: strategy, market, symbol, account, broker and the
account's risk policy (buying power). The router returns the exact
(broker_id, account_id) pair to execute against.
"""

from __future__ import annotations

from apps.adapters.domain import AccountStatus, Capability, OrderIntent
from apps.adapters.interface import AdapterError


class RoutingError(AdapterError):
    """Raised when no eligible account can receive an OrderIntent."""


class OrderRouter:
    """Market-aware account router."""

    def route(self, intent: OrderIntent, registry) -> tuple:
        """Return (broker_id, account_id) for the given OrderIntent.

        An explicit ``intent.account_id`` is honoured after validation;
        otherwise the best eligible account for ``intent.market`` is
        selected (highest buying power that can cover the notional).
        """
        if intent.account_id:
            account = registry.get_account(intent.account_id)
            if account.market != intent.market:
                raise RoutingError(
                    f"Account {intent.account_id} is {account.market}, "
                    f"not {intent.market}"
                )
            if account.status != AccountStatus.ACTIVE:
                raise RoutingError(f"Account {intent.account_id} is not active")
            self._check_symbol(registry, account, intent.symbol)
            return account.broker_id, account.account_id

        notional = intent.quantity * intent.price
        candidates = []
        for account in registry.accounts():
            if account.status != AccountStatus.ACTIVE:
                continue
            if account.market != intent.market:
                continue
            if Capability.SUBMIT_ORDER not in account.capabilities:
                continue
            if not self._check_symbol(registry, account, intent.symbol):
                continue
            if account.buying_power >= notional:
                candidates.append(account)

        if not candidates:
            raise RoutingError(
                f"No eligible account for {intent.side} {intent.symbol} "
                f"({intent.market}, notional={notional:,.2f})"
            )
        best = max(candidates, key=lambda a: a.buying_power)
        return best.broker_id, best.account_id

    @staticmethod
    def _check_symbol(registry, account, symbol) -> bool:
        """A strategy cannot route a symbol to the wrong market.

        Only enforced when the adapter declares a tradable universe
        (``symbols()``); real adapters without a fixed universe skip it.
        """
        adapter = registry.adapter_for(account.broker_id)
        universe_fn = getattr(adapter, "symbols", None)
        if not callable(universe_fn):
            return True
        universe = universe_fn()
        if not universe:
            return True
        return symbol in universe
