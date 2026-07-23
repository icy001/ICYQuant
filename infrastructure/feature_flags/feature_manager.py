"""
Central feature flag manager.
"""


class FeatureManager:


    def __init__(

        self,

        storage,

        evaluator,

    ):

        self.storage = storage

        self.evaluator = evaluator



    def enabled(

        self,

        name,

    ):

        flag = self.storage.get(

            name

        )


        if not flag:

            return False


        return self.evaluator.evaluate(

            flag

        )