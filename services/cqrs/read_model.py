class ReadModel:
    def __init__(self):
        self.views = {}

    def update(self, key, value):
        self.views[key] = value
