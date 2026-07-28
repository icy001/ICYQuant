class VectorStore:

    def __init__(self):

        self.data = {}

    def save(self, key, vector):

        self.data[key] = vector

    def search(self, key):

        return self.data.get(key)
