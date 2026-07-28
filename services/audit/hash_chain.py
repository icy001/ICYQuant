import hashlib


class AuditHashChain:
    def __init__(self):
        self.previous_hash = ""

    def generate(self, data):
        value = (
            self.previous_hash
            + str(data)
        )

        current = hashlib.sha256(
            value.encode()
        ).hexdigest()

        self.previous_hash = current

        return current
