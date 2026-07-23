"""
Fund lifecycle manager.
"""


class FundLifecycleManager:

    def __init__(self):
        self.state = "ACTIVE"

    def status(self):
        return self.state