"""
Incident tracking.
"""


class Incident:

    def __init__(self):
        self.status = "OPEN"



    def resolve(self):
        self.status = "RESOLVED"