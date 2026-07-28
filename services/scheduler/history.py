class ExecutionHistory:

    def __init__(self):
        self.records = []

    def add(
        self,
        job
    ):
        self.records.append(job)
