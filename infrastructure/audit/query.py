"""
Audit query service.
"""


class AuditQuery:


    def find_by_actor(

        self,

        records,

        actor,

    ):

        return [

            r for r in records

            if r.actor == actor

        ]