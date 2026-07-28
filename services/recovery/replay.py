class ReplayEngine:
    def replay(self, events):
        state = {}

        for event in events:
            state.update(event.payload)

        return state