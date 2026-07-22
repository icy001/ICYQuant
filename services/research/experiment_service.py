"""
Experiment management service.
"""


class ExperimentService:

    def __init__(
        self,
        tracker,
        registry,
    ):

        self.tracker = tracker

        self.registry = registry

    def register_model(
        self,
        model,
    ):

        self.registry.register(
            model
        )

    def log_experiment(
        self,
        experiment,
        metrics,
    ):

        self.tracker.log(
            experiment,
            metrics,
        )