"""
Feature flag storage.
"""


class FeatureStorage:


    def __init__(self):

        self.flags = {}



    def save(

        self,

        flag,

    ):

        self.flags[flag.name] = flag



    def get(

        self,

        name,

    ):

        return self.flags.get(name)