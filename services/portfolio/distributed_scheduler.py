"""
Distributed scheduler engine.
"""


class DistributedScheduler:

    def __init__(
        self,
        queue,
        balancer,
        dispatcher,
    ):

        self.queue = queue

        self.balancer = balancer

        self.dispatcher = dispatcher

    def schedule(
        self,
        nodes,
    ):

        job = self.queue.next_job()

        if job is None:

            return None

        node = self.balancer.select_node(
            nodes,
        )

        return self.dispatcher.dispatch(
            job,
            node,
        )