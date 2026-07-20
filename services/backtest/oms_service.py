"""
OMS service.
"""

from .virtual_oms import VirtualOMS


class OMSService:
    def __init__(
        self,
        oms: VirtualOMS,
    ):
        self.oms = oms

    def submit(
        self,
        order,
    ):
        return self.oms.submit(order)