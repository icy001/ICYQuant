class RoundRobinStrategy:
    def __init__(self):
        self.index = 0

    def select(self, instances):
        if not instances:
            return None

        instance = instances[self.index % len(instances)]
        self.index += 1
        return instance
