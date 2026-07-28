class AlphaRepository:

    def __init__(self):

        self.data = {}

    def save(self, alpha):

        self.data[
            alpha.alpha_id
        ] = alpha

    def get(self, alpha_id):

        return self.data.get(alpha_id)
