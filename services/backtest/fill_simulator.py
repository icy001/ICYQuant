"""
Order fill simulator.
"""

from .fill_result import FillResult


class FillSimulator:

    def __init__(
        self,
        slippage_model,
        commission_model,
    ):

        self.slippage_model = slippage_model

        self.commission_model = commission_model


    def execute(
        self,
        order,
        slippage_rate,
        commission_rate,
    ):

        slippage = self.slippage_model.calculate(
            order.price,
            slippage_rate,
        )

        execution_price = (
            order.price +
            slippage
        )

        commission = (
            self.commission_model.calculate(
                execution_price *
                order.quantity,
                commission_rate,
            )
        )

        return FillResult(
            filled_quantity=order.quantity,
            average_price=execution_price,
            commission=commission,
            slippage=slippage,
        )