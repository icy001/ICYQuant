class Router:
    def __init__(self):
        self.routes = {}

    def add(self, route):
        self.routes[route.path] = route

    def match(self, path):
        return self.routes.get(path)
