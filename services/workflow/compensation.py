class CompensationHandler:

    def compensate(
        self,
        task
    ):
        task.status = "COMPENSATED"

        return task
