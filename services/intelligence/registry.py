class IntelligenceRegistry:

    def __init__(self):

        self.items = {}

    def register(self, name, obj):

        self.items[name] = obj

    def get(self, name):

        return self.items.get(name)
