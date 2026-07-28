class BacktestService:

    def __init__(self, replay):

        self.replay = replay

    def run(self):

        results = []

        for event in self.replay.replay():

            results.append(event)

        return results
