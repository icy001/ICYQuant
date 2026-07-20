"""
Walk forward engine.
"""


class WalkForwardEngine:
    def __init__(
        self,
        splitter,
        trainer,
        validator,
    ):
        self.splitter = splitter
        self.trainer = trainer
        self.validator = validator

    def run(
        self,
        strategy,
        dataset,
    ):
        train, test = self.splitter.split(dataset, len(dataset)//2)

        model = self.trainer.train(strategy, train)

        return self.validator.validate(model, test)