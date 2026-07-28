class BacktestRepository:
    def __init__(self):
        self.results = {}

    def save(self, result):
        self.results[result.get("job_id")] = result

    def get(self, job_id):
        return self.results.get(job_id)