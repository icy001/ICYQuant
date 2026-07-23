"""
Environment feature control.
"""


class EnvironmentControl:


    def __init__(self):

        self.environment = "development"



    def set(

        self,

        environment,

    ):

        self.environment = environment



    def get(self):

        return self.environment