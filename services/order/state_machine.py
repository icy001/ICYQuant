class OrderStateMachine:

    transitions = {

        "CREATED": [
            "SUBMITTED"
        ],

        "SUBMITTED": [
            "ACCEPTED",
            "REJECTED"
        ],

        "ACCEPTED": [
            "PARTIAL_FILLED",
            "FILLED"
        ],

        "PARTIAL_FILLED": [
            "FILLED",
            "CANCELLED"
        ]

    }

    def can_transition(
        self,
        current,
        target,
    ):
        return target in self.transitions.get(
            current,
            []
        )