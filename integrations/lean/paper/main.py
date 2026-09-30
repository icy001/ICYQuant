"""ICYQuant → LEAN paper bridge (P0-01).

LEAN owns execution here: securities, market data, orders, fills,
portfolio and the paper brokerage.  This algorithm only *consumes* the
contract ICYQuant wrote and reports what LEAN did with it.

Deliberately a skeleton: P0-01 proves the pipe is connected, not that
the execution policy is good.  Turning an intent into a target position,
order type, limit/stop and execution policy is P0-02.

Every event the suite needs to grade is emitted as a single-line
``ICYQUANT_*`` message, so the acceptance report can be built from LEAN's
own log rather than from ICYQuant's hopes about it.
"""
from AlgorithmImports import *  # noqa: F401,F403 - LEAN injects this module

import json
from pathlib import Path


CONTRACT_FILENAME = "strategy_contract.json"

#: LEAN requires an explicit start date even for a live deployment.
DEFAULT_START = (2013, 10, 7)
FALLBACK_CASH = 1_000_000.0


class ICYQuantPaperAlgorithm(QCAlgorithm):
    """Minimal ICYQuant → LEAN paper bridge."""

    def Initialize(self):
        self.contract = self._load_contract()

        self.SetStartDate(*DEFAULT_START)
        self.SetCash(float(self.contract.get("initial_cash") or FALLBACK_CASH))

        self.symbols = {}

        for ticker in self.contract["symbols"]:
            security = self.AddEquity(ticker, Resolution.Minute)
            self.symbols[ticker] = security.Symbol

        self.intents = list(self.contract.get("orders", []))
        # K01: signal_ids staged before MarketOrder() so the synchronous
        # OnOrderEvent callback can claim them on first sight of the id.
        self._pending_signals = []
        self.signal_by_order = {}
        self.executed = False

        self.Debug(
            "ICYQUANT_CONTRACT "
            f"contract_version={self.contract.get('contract_version')} "
            f"strategy_id={self.contract.get('strategy_id')} "
            f"mode={self.contract.get('mode')} "
            f"symbols={','.join(self.contract['symbols'])} "
            f"intents={len(self.intents)}"
        )

    def _load_contract(self):
        """Find the contract LEAN was handed, wherever the CLI put it.

        Three locations are tried in descending order of trust: the
        ObjectStore (when the CLI injected the file), the algorithm's own
        directory (the CLI copies the whole project), and finally the
        process working directory.
        """
        candidates = []

        try:
            if self.ObjectStore.ContainsKey(CONTRACT_FILENAME):
                candidates.append(
                    Path(self.ObjectStore.GetFilePath(CONTRACT_FILENAME))
                )
        except Exception:
            # ObjectStore is best-effort; a miss is not an error.
            pass

        try:
            candidates.append(
                Path(__file__).resolve().parent / CONTRACT_FILENAME
            )
        except NameError:
            pass

        candidates.append(Path(CONTRACT_FILENAME))

        for path in candidates:
            if path.exists():
                with path.open("r", encoding="utf-8") as fh:
                    self.Debug(f"ICYQUANT_CONTRACT_FILE path={path}")
                    return json.load(fh)

        raise RuntimeError(
            f"{CONTRACT_FILENAME} not found; looked in "
            + ", ".join(str(path) for path in candidates)
        )

    def OnData(self, data):
        if self.executed:
            return

        for intent in self.intents:
            symbol = self.symbols.get(intent["symbol"])

            if symbol is None:
                self.Error(f"ICYQUANT_UNKNOWN_SYMBOL symbol={intent['symbol']}")
                continue

            quantity = int(intent["quantity"])

            if str(intent["side"]).upper() == "SELL":
                quantity = -quantity

            # K01: stage the signal_id BEFORE submitting.  LEAN fires
            # OnOrderEvent synchronously inside MarketOrder(), before the
            # ticket (and its OrderId) is returned to us.
            self._pending_signals.append(intent["signal_id"])
            ticket = self.MarketOrder(symbol, quantity)
            order_id = str(ticket.OrderId)
            if order_id not in self.signal_by_order:
                # No callback claimed it; do it here so the mapping is
                # always complete regardless of callback timing.
                self.signal_by_order[order_id] = self._pending_signals.pop(0)

            self.Debug(
                "ICYQUANT_ORDER "
                f"signal_id={intent['signal_id']} "
                f"order_id={ticket.OrderId} "
                f"symbol={intent['symbol']} "
                f"side={intent['side']} "
                f"quantity={abs(quantity)}"
            )

        self.executed = True

    def OnOrderEvent(self, order_event):
        order_id = str(order_event.OrderId)

        if order_id not in self.signal_by_order and self._pending_signals:
            # K01: MarketOrder() triggers this callback synchronously before
            # it returns; claim the staged signal_id for the new order.
            self.signal_by_order[order_id] = self._pending_signals.pop(0)

        symbol = getattr(order_event, "Symbol", None)

        self.Debug(
            "ICYQUANT_ORDER_EVENT "
            f"order_id={order_event.OrderId} "
            f"signal_id={self.signal_by_order.get(order_id, '')} "
            f"symbol={getattr(symbol, 'Value', '')} "
            f"status={order_event.Status} "
            f"quantity={order_event.Quantity} "
            f"fill_qty={order_event.FillQuantity} "
            f"fill_price={order_event.FillPrice}"
        )

    def OnEndOfAlgorithm(self):
        self.Debug(
            "ICYQUANT_END "
            f"strategy_id={self.contract.get('strategy_id')} "
            f"orders={len(self.signal_by_order)} "
            f"cash={self.Portfolio.Cash} "
            f"invested={self.Portfolio.Invested}"
        )
