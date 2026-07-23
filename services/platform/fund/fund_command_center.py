"""
Hedge fund command center.
"""


class FundCommandCenter:

    def __init__(
        self,
        cio,
        governance,
        allocator,
    ):
        self.cio = cio
        self.governance = governance
        self.allocator = allocator

    def operate(
        self,
        market,
    ):
        decision = self.cio.decide(
            market
        )
        approval = self.governance.review(
            decision
        )
        allocation = self.allocator.allocate(
            approval
        )
        return allocation