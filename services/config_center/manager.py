class VersionManager:

    def __init__(self):
        self.current = 1

    def next_version(self):
        self.current += 1

        return self.current
