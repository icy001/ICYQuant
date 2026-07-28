class HealthFilter:
    def filter(self, instances):
        return [i for i in instances if i.healthy]
