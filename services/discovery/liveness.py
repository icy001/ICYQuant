class LivenessProbe:
    def probe(self, instance):
        return instance.healthy
