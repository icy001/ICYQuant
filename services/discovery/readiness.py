class ReadinessProbe:
    def probe(self, instance):
        return instance.healthy
