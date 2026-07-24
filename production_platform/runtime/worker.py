class Worker:


    def __init__(self, name):

        self.name = name

        self.running = False


    def start(self):

        self.running = True


    def stop(self):

        self.running = False