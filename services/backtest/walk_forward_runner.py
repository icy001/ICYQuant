"""
Walk-forward runner.
"""


class WalkForwardRunner:

    def __init__(
        self,
        splitter,
        optimizer,
        analyzer,
    ):

        self.splitter = splitter

        self.optimizer = optimizer

        self.analyzer = analyzer


    def run(
        self,
        data,
        train_size,
        optimizer,
        parameter_space,
        performance,
    ):

        train, test = self.splitter.split(
            data,
            train_size,
        )

        candidates = self.optimizer.optimize(
            optimizer,
            parameter_space,
        )

        return self.analyzer.analyze(
            candidates[0],
            {
                "train_size": len(train),
                "test_size": len(test),
                **performance,
            },
        )