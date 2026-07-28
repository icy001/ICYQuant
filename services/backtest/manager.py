class BacktestManager:
    def __init__(self, replay, simulator, repository):
        self.replay = replay
        self.simulator = simulator
        self.repository = repository

    def run(self, job, data):
        trades = 0

        for bar in self.replay.replay(data):
            self.simulator.execute(bar)
            trades += 1

        result = {
            "job_id": job.job_id,
            "trades": trades
        }

        self.repository.save(result)

        return result