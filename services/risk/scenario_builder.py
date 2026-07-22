"""
Scenario builder.
"""


class ScenarioBuilder:

    def build(
        self,
        name,
        factors,
    ):

        from uuid import uuid4

        return {
            "scenario_id":
                str(uuid4()),
            "name":
                name,
            "factors":
                factors,
        }