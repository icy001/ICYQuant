class MarketReplay:

    def __init__(self, events):

        self.events = events

    def replay(self):

        for event in self.events:

            yield event
