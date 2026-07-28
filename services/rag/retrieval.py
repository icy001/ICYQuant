class RetrievalEngine:

    def __init__(self, store):

        self.store = store

    def retrieve(self, key):

        return self.store.search(key)
