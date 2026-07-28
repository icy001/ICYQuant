class AlphaService:

    def __init__(self, repository):

        self.repository = repository

    def register(self, alpha):

        self.repository.save(alpha)

    def query(self, alpha_id):

        return self.repository.get(alpha_id)
