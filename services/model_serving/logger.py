class PredictionLogger:

    def __init__(self):

        self.logs = []

    def record(self, prediction):

        self.logs.append(prediction)

    def all(self):

        return self.logs
