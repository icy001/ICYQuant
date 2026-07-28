class TaskExecutor:

    def execute(
        self,
        task
    ):
        task.status = "COMPLETED"

        return task
